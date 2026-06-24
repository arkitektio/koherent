import logging
from typing import AsyncIterator

from strawberry.extensions import SchemaExtension
from strawberry.types.graphql import OperationType

from kante.context import HttpContext, WsContext
from koherent.vars import current_provenance, current_task

logger = logging.getLogger(__name__)


class KoherentExtension(SchemaExtension):
    """Makes the request's provenance token available to provenance tracking.

    Reads the verified provenance token that AuthentikateExtension set on the
    request (AuthentikateExtension must run before this extension) and exposes
    it through a context variable, so history signals and helpers like
    `koherent.utils.get_or_create_task` can attribute changes to the task.
    """

    async def on_operation(self) -> AsyncIterator[None]:
        """Set the provenance context variable for the operation."""

        context = self.execution_context.context

        reset_provenance = None
        reset_task = None

        if isinstance(context, WsContext):
            # A websocket connection (and its headers) is persistent across
            # operations, so there is no per-operation provenance context.
            # Mutations over websockets are rejected in on_execute.
            pass

        elif isinstance(context, HttpContext):
            # AuthentikateExtension attaches a verified provenance token when one
            # was presented; the extension getter raises when it is unset.
            try:
                provenance = context.request.get_extension("provenance")
            except ValueError:
                provenance = None

            if provenance is not None:
                reset_provenance = current_provenance.set(provenance)
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
            if reset_provenance is not None:
                current_provenance.reset(reset_provenance)

    async def on_execute(self) -> AsyncIterator[None]:
        """Reject mutations over websockets (no per-operation provenance context)."""

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
