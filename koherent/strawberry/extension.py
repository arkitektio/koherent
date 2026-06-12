import logging
from typing import AsyncIterator

from strawberry.extensions import SchemaExtension
from strawberry.types.graphql import OperationType

from kante.context import HttpContext, WsContext
from koherent.vars import current_task, current_task_payload

logger = logging.getLogger(__name__)


class KoherentExtension(SchemaExtension):
    """Makes the request's task context available to provenance tracking.

    Reads the validated Rekuest task that AuthentikateExtension set on the
    request (AuthentikateExtension must run before this extension) and exposes
    it through a context variable, so history signals and helpers like
    `koherent.utils.get_or_create_task` can attribute changes to the task.
    """

    async def on_operation(self) -> AsyncIterator[None]:
        """Set the task payload context variable for the operation."""

        context = self.execution_context.context

        reset_task_payload = None
        reset_task = None

        if isinstance(context, WsContext):
            # A websocket connection (and its headers) is persistent across
            # operations, so there is no per-operation task context.
            # Mutations over websockets are rejected in on_execute.
            pass

        elif isinstance(context, HttpContext):
            # Validated by authentikate against the token.
            task = context.request._task  # the `task` property raises when unset
            if task is not None:
                reset_task_payload = current_task_payload.set(task)
                # Never reuse a Task row resolved during a previous operation.
                reset_task = current_task.set(None)

        else:
            raise ValueError(
                "Unknown context type. Cannot determine if it's WebSocket or HTTP."
            )

        try:
            yield
        finally:
            if reset_task is not None:
                current_task.reset(reset_task)
            if reset_task_payload is not None:
                current_task_payload.reset(reset_task_payload)

    async def on_execute(self) -> AsyncIterator[None]:
        """Reject mutations over websockets (no per-operation task context)."""

        context = self.execution_context.context

        if (
            isinstance(context, WsContext)
            and self.execution_context.operation_type == OperationType.MUTATION
        ):
            raise ValueError(
                "Mutations are not allowed in a websocket context, "
                "because the task context cannot be tracked."
            )

        yield
