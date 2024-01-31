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

Koherent is a python library that allows you to integrated based audit logging into your application.
It thinly wraps the [django-simple-history](https://django-simple-history.readthedocs.io/en/latest/) library,
and provides a simple interface for logging and reverting changes to your models.


> **Note:** This library is still heavily tied to the Arkitekt Framework. We are working on making it more generic.


### What do we track?


By default (soon to be configurable), we track the following parameters:

- `user` - The user who made the change
- `app` - The application that made the change (if present)
- `assignation_id` - In which context the change was made (if present)
- `action` - The action that was performed (create, update, delete)
- `model` - The model that was changed

#### What is an assignation?

An assignation ID (or more commonly known as a `context_id` or `correlation_id`) is a unique identifier that is used to group
changes together. FOr example, if you have a `Task` model, and you want to track all changes to a specific task, you would
use the `Task`'s ID as the assignation ID. This allows you to easily track all changes to a specific task, and revert them
if necessary.



## How do I use it?

Koherent is a Django Libary, so you will have to add it to your `INSTALLED_APPS` in your `settings.py` file.

```python
INSTALLED_APPS = [
    ...
    'koherent',
    ...
]
```


### Model Setup

Then in your models, you will need to add the `KoherentHistoryModel` mixin to your model.

```python
from koherent.fields import HistoryField, HistoricForeignKey
import koherent.signal # This is required to register the signal handlers

class MyModel(KoherentHistoryModel):
    your_field = models.CharField(max_length=255)
    history = HistoryField()
    ...


```

### Strawberry Setup

Koherent is designed to work with [Strawberry](https://strawberry.rocks/), so you will need to add its extension to your
schema.

```python

import strawberry_django
from koherent.strawberry.extension import KoherentExtension
from app import models

@strawberry_django.type(models.MyModel)
class MyModel:
    id: strawberry.ID
    name: str

@strawberry.type
class Query:

    @strawberry_django.field
    def create_model(self, info, your_field: str) -> MyModel:
        model = models.MyModel.objects.create(your_field=your_field)
        # This will create a new history entry (by sending a signal)
        # bound to the current user and the assignation id

        return model

    @strawberry_django.field
    def update_model(self, info, id: strawberry.ID, your_field: str) -> MyModel:
        model = models.MyModel.objects.get(id=id)
        model.your_field = your_field
        model.save()
        # This will create a new history entry (by sending a signal)
        # bound to the current user and the assignation id

        return model



schema = strawberry.Schema(query=Query, extensions=[KoherentExtension])

```


### GraphQL Setup

Currently we require that you use the [`Kante`](https://github.com/jhnnsrs/kante) GraphQL library, as it provides the `assignation_id` and `user` context
required for the audit logging. We are soon going to make this more generic.


##### ASSIGNATION_ID in the Arkitekt Framework

In the Arkitekt Framework, we use the `assignation_id` to track changes that are done by an app when a user is calling that
app through an Arkitekt Rekuest. This allows us to track all changes that are done by a specific Rekuest, and revert them
if necessary.

```python
from arkitekt import register
from service.generated_api import create_model, update_model, delete_model, MyModel


@register
def do_some_transactions(name: str) -> MyModel:
    """ Do some transactions """
    # Within this function, all api requests will have the assignatio-id header
    # set to the same value. This allows us to track all changes that are done

    z = create_model(name=name)

    f = update_model(id=z.id, name="New Name") # tracked with the same assignation_id
    
    return f



```

