from django.db import models
from koherent.fields import ProvenanceField

# Create your models here.


class MyModel(models.Model):
    """
    Model to test the Koherent extension.
    """
    your_field = models.CharField(max_length=1000, null=True, blank=True)
    provenance = ProvenanceField()

    class Meta:
        """ Model to test the Koherent extension. """
        ordering = ["-id"]