import contextvars
from typing import TYPE_CHECKING

from authentikate.provenance import ProvenanceToken

if TYPE_CHECKING:
    from koherent.models import Task


current_provenance: contextvars.ContextVar["ProvenanceToken | None"] = (
    contextvars.ContextVar("current_provenance", default=None)
)
current_task: contextvars.ContextVar["Task | None"] = contextvars.ContextVar(
    "current_task", default=None
)


def get_current_provenance() -> "ProvenanceToken | None":
    """
    Get the current verified provenance token from the context variable

    Returns
    -------
    ProvenanceToken | None
        The current provenance token
    """
    return current_provenance.get()


def get_current_task() -> "Task | None":
    """
    Get the Task row resolved for the current context, if any

    Returns
    -------
    Task | None
        The cached task row, set by `koherent.utils.get_or_create_task`
    """
    return current_task.get()


__all__ = [
    "current_provenance",
    "current_task",
    "get_current_provenance",
    "get_current_task",
]
