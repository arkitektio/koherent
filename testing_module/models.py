from typing import ClassVar

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
        """Model to test the Koherent extension."""

        ordering = ["-id"]  # noqa: RUF012 -- Django Meta, read not mutated


class Cached(models.Model):
    """An abstract base with a derived column, kept out of provenance like arkitekt's Described."""

    cache = models.CharField(max_length=1000, default="", blank=True)
    provenance_excluded_fields: ClassVar[tuple[str, ...]] = ("cache",)

    class Meta:
        """Abstract: only its subclasses have tables."""

        abstract = True


class CachedModel(Cached):
    """A model whose derived column and one given column are kept out of provenance."""

    name = models.CharField(max_length=1000, default="", blank=True)
    note = models.CharField(max_length=1000, default="", blank=True)
    provenance = ProvenanceField(excluded_fields=["note"])


class StampedModel(models.Model):
    """A model stamping the task that created it, like mikro's datasets."""

    name = models.CharField(max_length=1000, default="", blank=True)
    created_through = models.ForeignKey(
        "koherent.Task", on_delete=models.SET_NULL, null=True, blank=True
    )


class PlainModel(models.Model):
    """A model recording nothing about what created it."""

    name = models.CharField(max_length=1000, default="", blank=True)
