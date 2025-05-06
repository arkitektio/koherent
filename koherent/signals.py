from django.dispatch import receiver
from simple_history.signals import (
    pre_create_historical_record,
)
from authentikate.vars import get_user, get_client
from koherent.vars import get_current_assignation_id
from typing import Any


@receiver(pre_create_historical_record)
def add_history_app(sender: Any, **kwargs: Any) -> None:
    """Add some context to the history instance"""

    history_instance = kwargs["history_instance"]
    history_instance.client = get_client()
    history_instance.assignation_id = get_current_assignation_id()
    history_instance.history_user = get_user()

    # context.request for use only when the simple_history middleware is on and enabled
