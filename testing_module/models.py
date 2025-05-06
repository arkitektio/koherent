from django.db import models
from authentikate.models import Client, User
from koherent.fields import ProvenanceField

# Create your models here.


class MyModel(models.Model):
    """
    Model to test the Koherent extension.
    """
    your_field = models.CharField(max_length=1000, null=True, blank=True)
    provenance = ProvenanceField()

    class Meta:
        ordering = ["-id"]