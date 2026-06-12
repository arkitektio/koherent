from typing import Any

from django.dispatch import receiver
from simple_history.signals import (
    pre_create_historical_record,
)

from authentikate.vars import get_client, get_user
from koherent.utils import get_or_create_task


@receiver(pre_create_historical_record)
def add_history_app(sender: Any, **kwargs: Any) -> None:
    """Add the auth and task context to the history instance"""

    history_instance = kwargs["history_instance"]
    history_instance.client = get_client()
    history_instance.history_user = get_user()
    # No-op without a task; cached, so at most one query per request.
    history_instance.task = get_or_create_task()
