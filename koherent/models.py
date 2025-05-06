from django.db import models
from authentikate.models import Client


# in models.py
class ProvenanceEntryModel(models.Model):
    """
    Abstract model for history models tracking the IP address.
    """

    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True)
    assignation_id = models.CharField(max_length=1000, null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ["-history_date"]
        

from .signals import add_history_app

__all__ = [
    add_history_app
]