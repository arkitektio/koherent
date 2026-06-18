"""Unit tests for KoherentExtension's provenance-context lifecycle."""

from types import SimpleNamespace

import pytest
from strawberry.http.temporal_response import TemporalResponse
from strawberry.types.graphql import OperationType

from authentikate.provenance import ProvenanceToken
from kante.context import HttpContext, UniversalRequest, WsContext
from koherent.strawberry.extension import KoherentExtension
from koherent.vars import current_provenance, current_task
from tests.conftest import provenance_obj


def _extension(context, operation_type=OperationType.QUERY) -> KoherentExtension:
    ext = KoherentExtension()
    ext.execution_context = SimpleNamespace(
        context=context, operation_type=operation_type
    )
    return ext


def _http_context(provenance: ProvenanceToken | None) -> HttpContext:
    extensions = {} if provenance is None else {"provenance": provenance}
    return HttpContext(
        request=UniversalRequest(_extensions=extensions),
        response=TemporalResponse(),
        headers={},
    )


def _ws_context() -> WsContext:
    return WsContext(
        request=UniversalRequest(_extensions={}),
        response=TemporalResponse(),
        connection_params={},
        consumer=object(),
    )


def _payload() -> ProvenanceToken:
    return provenance_obj(tsk="task-e")


async def _finish(gen) -> None:
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()


@pytest.mark.asyncio
async def test_http_provenance_set_during_operation_and_reset() -> None:
    """The verified provenance token is exposed during the operation and reset after."""
    payload = _payload()
    gen = _extension(_http_context(payload)).on_operation()

    await gen.__anext__()
    assert current_provenance.get() == payload

    await _finish(gen)
    assert current_provenance.get() is None


@pytest.mark.asyncio
async def test_http_task_cache_cleared_during_operation_and_restored() -> None:
    """A Task row cached by a previous operation is never reused."""
    stale = SimpleNamespace(task_id="task-stale")
    reset = current_task.set(stale)  # type: ignore[arg-type]
    try:
        gen = _extension(_http_context(_payload())).on_operation()

        await gen.__anext__()
        assert current_task.get() is None

        await _finish(gen)
        assert current_task.get() is stale
    finally:
        current_task.reset(reset)


@pytest.mark.asyncio
async def test_http_without_provenance_leaves_context_unset() -> None:
    """A request without a provenance token sets no provenance context."""
    gen = _extension(_http_context(None)).on_operation()

    await gen.__anext__()
    assert current_provenance.get() is None
    await _finish(gen)


@pytest.mark.asyncio
async def test_ws_operation_sets_no_provenance_context() -> None:
    """Websocket operations have no per-operation provenance context."""
    gen = _extension(_ws_context()).on_operation()

    await gen.__anext__()
    assert current_provenance.get() is None
    await _finish(gen)


@pytest.mark.asyncio
async def test_ws_mutation_rejected() -> None:
    """Mutations over websockets are rejected."""
    gen = _extension(_ws_context(), OperationType.MUTATION).on_execute()

    with pytest.raises(ValueError, match="not allowed"):
        await gen.__anext__()


@pytest.mark.asyncio
async def test_ws_query_allowed() -> None:
    """Queries over websockets pass through."""
    gen = _extension(_ws_context(), OperationType.QUERY).on_execute()

    await gen.__anext__()
    await _finish(gen)


@pytest.mark.asyncio
async def test_unknown_context_rejected() -> None:
    """An unrecognized context type is an error."""
    gen = _extension(object()).on_operation()

    with pytest.raises(ValueError, match="Unknown context"):
        await gen.__anext__()
