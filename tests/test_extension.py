"""Unit tests for KoherentExtension's task-context lifecycle."""

from types import SimpleNamespace

import pytest
from strawberry.http.temporal_response import TemporalResponse
from strawberry.types.graphql import OperationType

from authentikate.base_models import Task as TaskPayload
from kante.context import HttpContext, UniversalRequest, WsContext
from koherent.strawberry.extension import KoherentExtension
from koherent.vars import current_task_payload


def _extension(context, operation_type=OperationType.QUERY) -> KoherentExtension:
    ext = KoherentExtension()
    ext.execution_context = SimpleNamespace(
        context=context, operation_type=operation_type
    )
    return ext


def _http_context(task: TaskPayload | None) -> HttpContext:
    return HttpContext(
        request=UniversalRequest(_extensions={}, _task=task),
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


def _payload() -> TaskPayload:
    return TaskPayload(id="task-e", args={}, user="1", app="testapp", action="hash")


async def _finish(gen) -> None:
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()


@pytest.mark.asyncio
async def test_http_task_payload_set_during_operation_and_reset() -> None:
    """The validated task is exposed during the operation and reset afterwards."""
    payload = _payload()
    gen = _extension(_http_context(payload)).on_operation()

    await gen.__anext__()
    assert current_task_payload.get() == payload

    await _finish(gen)
    assert current_task_payload.get() is None


@pytest.mark.asyncio
async def test_http_without_task_leaves_payload_unset() -> None:
    """A request without a task header sets no task context."""
    gen = _extension(_http_context(None)).on_operation()

    await gen.__anext__()
    assert current_task_payload.get() is None
    await _finish(gen)


@pytest.mark.asyncio
async def test_ws_operation_sets_no_task_context() -> None:
    """Websocket operations have no per-operation task context."""
    gen = _extension(_ws_context()).on_operation()

    await gen.__anext__()
    assert current_task_payload.get() is None
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
