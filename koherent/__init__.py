"""The Koherent package.

Allows to manage Provenance in Django applications, through
simple and easy to use fields.

Model integration lives in `koherent.fields` (ProvenanceField) and
`koherent.models`; those import Django models and must only be imported
once the app registry is ready.
"""

from koherent.vars import get_current_task, get_current_task_payload

__all__ = [
    "get_current_task",
    "get_current_task_payload",
]
