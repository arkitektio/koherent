# Koherent

[![codecov](https://codecov.io/gh/jhnnsrs/koherent/branch/master/graph/badge.svg?token=UGXEA2THBV)](https://codecov.io/gh/jhnnsrs/koherent)
[![PyPI version](https://badge.fury.io/py/koherent.svg)](https://pypi.org/project/koherent/)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://pypi.org/project/koherent/)
![Maintainer](https://img.shields.io/badge/maintainer-jhnnsrs-blue)
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/koherent.svg)](https://pypi.python.org/pypi/koherent/)
[![PyPI status](https://img.shields.io/pypi/status/koherent.svg)](https://pypi.python.org/pypi/koherent/)
[![PyPI download month](https://img.shields.io/pypi/dm/koherent.svg)](https://pypi.python.org/pypi/koherent/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Checked with mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/jhnnsrs/koherent)

## What is Koherent?

Koherent adds **provenance-aware audit logging** to Django applications that expose a
[Strawberry](https://strawberry.rocks/) GraphQL API. It is a thin layer over
[django-simple-history](https://django-simple-history.readthedocs.io/): every change to a
tracked model is recorded as a history row, and each row is attributed to *who* changed it,
*which client/app* they used, and — crucially — the verified **task** (assignation) it
happened under.

It answers questions like *"which automated run touched this record, on whose authority, and
what exactly did it change?"* and exposes those answers directly in your GraphQL schema as a
queryable, filterable `provenance` field.


## Installation

```bash
pip install koherent   # pulls in django-simple-history, authentikate, kante
```

Koherent is a Django app. Add it to `INSTALLED_APPS` **after** `authentikate` (it relies on
the authentikate user/client/organization context):

```python
INSTALLED_APPS = [
    # ...
    "authentikate",
    "koherent",
    "your_app",
]

AUTH_USER_MODEL = "authentikate.User"
```

### Scope

Koherent is responsible for three things and nothing else:

1. **Recording** — a `ProvenanceField` on your model captures every create/update/delete as a
   history row (via django-simple-history).
2. **Attributing** — a signal stamps each history row with the acting `user`, the `client`
   (app), and a `Task` resolved from the request's verified provenance token.
3. **Exposing** — Strawberry types (`ProvenanceEntry`, `Task`) and a flat, semantic filter
   (`ProvenanceFilterMixin`) surface that history in your GraphQL API.

It does **not** authenticate requests, mint tokens, or define the transport — those belong to
[`authentikate`](https://github.com/jhnnsrs/authentikate) and
[`kante`](https://github.com/jhnnsrs/kante) respectively (see below). Koherent is the piece
that sits between them and turns an authenticated, context-carrying request into a durable,
queryable audit trail.

> **Note:** Koherent is built for the Arkitekt / Rekuest ecosystem. The "task" it tracks is a
> Rekuest assignation, attested by a signed provenance token.

### What gets tracked

Every history row (a `ProvenanceEntry`) carries:

| Field               | Meaning                                                            |
|---------------------|--------------------------------------------------------------------|
| `user`              | The user who made the change (`history_user`).                     |
| `client`            | The OAuth client / app that made the change, if any.               |
| `task`              | The verified assignation the change ran under, if any.             |
| `kind`              | `CREATE` / `UPDATE` / `DELETE`.                                     |
| `date`              | When the change happened.                                          |
| `effective_changes` | The per-field old→new diff for that row.                           |

The `task` is a `Task` row built once per assignation from the provenance token's claims
(assignation id and its parent/root, the root human causer, the executing agent, the issuer,
the single-use token id, and an args hash).

#### What is an assignation?

An assignation id (a.k.a. `correlation_id` / `context_id`) groups together every change made
during one logical run. In Arkitekt, when a user calls an app through a Rekuest, all of that
app's mutations carry the same assignation id — so you can later find, audit, or revert every
change a single run produced.

## How it fits together

```
        Rekuest provenance token (signed, EdDSA)
                       │
        ┌──────────────▼───────────────┐
 kante  │  HttpContext / WsContext      │   ← GraphQL transport + context
        └──────────────┬───────────────┘
                       │  request
        ┌──────────────▼───────────────┐
 authn. │  AuthentikateExtension        │   ← verifies token, sets user/client/
        │  → user, client, organization │     organization + provenance on request
        │  → verified ProvenanceToken   │
        └──────────────┬───────────────┘
                       │
        ┌──────────────▼───────────────┐
 koher. │  KoherentExtension            │   ← reads provenance token into a contextvar
        └──────────────┬───────────────┘
                       │  model.save()
        ┌──────────────▼───────────────┐
        │  simple_history signal        │   ← stamps history row with user/client/Task
        │  → ProvenanceEntry rows        │
        └───────────────────────────────┘
```

## On the agent: one token, many mutations

This is the heart of *why* provenance groups changes. The grouping is not done by Koherent —
it falls out of how a [rekuest-next](https://github.com/jhnnsrs/rekuest-next) agent runs a task.

When a user calls a registered function on an agent:

```python
from rekuest_next import register
from service.api import create_model, update_model  # generated GraphQL clients


@register
def do_some_transactions(name: str) -> Model:
    """Every GraphQL call below is grouped under one assignation."""
    z = create_model(name=name)             # mutation #1
    f = update_model(id=z.id, name="renamed")  # mutation #2
    return f
```

the agent receives an `Assign` message carrying an opaque, server-signed **provenance token**
for that single assignation. While the function runs, rekuest-next holds that token in an
`AssignmentHelper` stored in a `contextvar` (`current_assignation_helper`), and a GraphQL link
in its client chain — `ContextLink` — transparently stamps the token onto **every** outgoing
operation:

So `create_model` and `update_model` above — and any other call the function makes — all leave
the agent carrying the **same** `Rekuest-Task` header. The token is set once per task execution
and reused for the lifetime of that execution (Python's `contextvars` propagate it to every
coroutine the function spawns); the application code does nothing special.

On the server side, `AuthentikateExtension` verifies that `Rekuest-Task` token and Koherent's
`get_or_create_task()` resolves it to a `Task` row, **deduplicating by the assignation id
(`tsk`)**: the first mutation creates the row, every later mutation with the same token reuses
it (a warm `Task.objects.filter(...).first()` lookup, cached in a contextvar per request). The
result: every history row produced anywhere in that one `@register` execution links back to a
single `Task`, and you can later query *"show me everything assignation X changed."*

> Long-running assignations span many separate HTTP requests over time; because the `Task` is
> keyed by the token's assignation id rather than by request, they all still collapse onto the
> same row.



## Model setup

Add a `ProvenanceField` to any model you want to audit. Importing the field also registers the
history signal that does the attribution.

```python
from django.db import models
from koherent.fields import ProvenanceField


class MyModel(models.Model):
    your_field = models.CharField(max_length=1000, null=True, blank=True)
    provenance = ProvenanceField()  # records & attributes every change
```

`ProvenanceField` is a `simple_history.HistoricalRecords` whose generated history model mixes
in `koherent.models.ProvenanceEntryModel` (the `client` / `task` columns). The history rows are
reachable via the reverse relation `provenance_entries` (the default `related_name`).

Run `python manage.py makemigrations && migrate` to create the history table and the `Task`
table.

## Schema setup

Expose the provenance on your Strawberry types and wire up the extension. Order matters:
`AuthentikateExtension` must run **before** `KoherentExtension`.

```python
import strawberry
import strawberry_django
from strawberry_django.optimizer import DjangoOptimizerExtension
from authentikate.strawberry.extension import AuthentikateExtension
from koherent.strawberry.extension import KoherentExtension
from koherent.strawberry import ProvenanceEntry, ProvenanceFilterMixin
from your_app import models


@strawberry_django.filter_type(models.MyModel)
class MyModelFilter(ProvenanceFilterMixin):
    your_field: strawberry_django.filters.FilterLookup[str] | None


@strawberry_django.type(models.MyModel, filters=MyModelFilter)
class MyModel:
    id: strawberry.ID
    your_field: str
    # The reverse relation is `provenance_entries`; expose it as `provenance`.
    provenance: list[ProvenanceEntry] = strawberry_django.field(
        field_name="provenance_entries"
    )


# authentikate's types carry Apollo Federation @key directives, so use a federation schema.
schema = strawberry.federation.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[AuthentikateExtension, KoherentExtension, DjangoOptimizerExtension],
)
```

Any mutation that calls `model.save()` now produces an attributed history row automatically — no
explicit logging call needed.

### Querying provenance

```graphql
query {
  myModel(id: "1") {
    id
    provenance {
      kind
      date
      user { sub }
      task { assignationId agentClientId }
      effectiveChanges { field oldValue newValue }
    }
  }
}
```

`effectiveChanges` is batched through a DataLoader, so selecting it across many instances stays
a constant number of queries.

### Filtering by provenance

`ProvenanceFilterMixin` adds a flat, **exact-match** `provenance` filter to a model's filter
type — no nested traversal required:

```graphql
query {
  myModels(filters: { provenance: { assignationId: "task-a", kind: CREATE } }) { id }
}
```

Available predicates: `assignationId`, `agentClientId`, `issuer`, `changedBy` (user sub),
`kind`, `changedSince`, and `changedBefore`.

## Interaction with `authentikate`

[`authentikate`](https://github.com/jhnnsrs/authentikate) owns identity; Koherent consumes it.

- **Models** — `AUTH_USER_MODEL` is `authentikate.User`, and Koherent's `Task.assigner` /
  `ProvenanceEntry.client` point at authentikate's `User` and `Client`. Tasks are scoped to an
  authentikate `Organization`.
- **The verified provenance token** — `AuthentikateExtension` validates the incoming Rekuest
  provenance token (`authentikate.provenance.ProvenanceToken`, a separate EdDSA trust domain
  configured under `AUTHENTIKATE["provenance"]`) and attaches it to the request. There is no
  static-token bypass for provenance — the signature is always checked.
- **The auth context** — Koherent's history signal reads `authentikate.vars.get_user()`,
  `get_client()`, `get_organization()`, and `get_token()` to stamp each row and to build the
  `Task` from the token's claims (`tsk`, `ptk`, `rtk`, `rcb`, `sub`, `act.sub`, `act.cid`,
  `iss`, `jti`, `ahs`, `aha`). The root human causer (`rcb`) is resolved to a local `User` when
  one exists; otherwise the task is recorded with a null assigner but the raw sub is kept.

Because of this dependency, `AuthentikateExtension` must precede `KoherentExtension` in the
schema's extension list — Koherent reads what authentikate has already put on the request.

## Interaction with `kante`

[`kante`](https://github.com/jhnnsrs/kante) provides the GraphQL transport (ASGI app) and the
request context that both extensions build on.

- **Context types** — `KoherentExtension` switches on kante's `HttpContext` and `WsContext`.
  For HTTP requests it sets the request's provenance token into a context variable for the
  duration of the operation; for websockets it does not (the connection — and its headers — is
  shared across operations, so there is no reliable per-operation provenance).
- **Mutations over websockets are rejected.** Since the task context can't be tracked per
  operation on a persistent socket, Koherent raises rather than record an unattributed change.
- **`Info`** — resolvers use kante's `Info` type; the `effective_changes` DataLoader is cached
  on the kante request so it lives exactly one request.

## Public API

```python
from koherent.fields import ProvenanceField, HistoricForeignKey, GenericRelation
from koherent.models import Task, ProvenanceEntryModel
from koherent import get_current_provenance, get_current_task
from koherent.strawberry import (
    KoherentExtension,
    ProvenanceEntry,      # the history-row GraphQL type
    Task,                 # the assignation GraphQL type
    ProvenanceFilter,     # the flat provenance filter
    ProvenanceFilterMixin,  # drop-in mixin adding a `provenance` filter
)
```

## Development

```bash
uv sync
uv run pytest        # test_project + testing_module exercise the full stack
```
