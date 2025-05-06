from ..models import ProvenanceEntryModel
import strawberry_django
import strawberry
from authentikate.strawberry.types import Client, User
from kante.types import Info
from enum import Enum
import datetime


@strawberry.enum(description="The type of change that was made.")
class HistoryKind(str, Enum):
    """ The type of change that was made. """
    CREATE = "+"
    UPDATE = "~"
    DELETE = "-"


@strawberry.type(description="A change made to a model.")
class ModelChange:
    """The change made to a model."""
    field: str = strawberry.field(description="The field that was changed.")
    old_value: str | None = strawberry.field(description="The old value of the field.")
    new_value: str | None = strawberry.field(description="The new value of the field.")


@strawberry_django.type(ProvenanceEntryModel, pagination=True, description="A provenance event for a model.")
class ProvenanceEntry:
    """ A change made to a model."""
    client: Client | None

    @strawberry_django.field(description="User who made the change.")
    def user(self, info: Info) -> User | None:
        """This method returns the user who made the change."""
        return self.history_user # type: ignore

    @strawberry_django.field(description="The type of change that was made.")
    def kind(self, info: Info) -> HistoryKind:
        """This method returns the type of change that was made."""
        return self.history_type

    @strawberry_django.field(description="The date of the change.")
    def date(self, info: Info) -> datetime.datetime:
        """This method returns the date of the change."""
        return self.history_date

    @strawberry_django.field(description="The assignation ID during which the change occurred. If it was happening outside of an assignation, it will be None.")
    def during(self, info: Info) -> str | None:
        """This method returns the assignation ID during which the change occurred."""
        return self.assignation_id

    @strawberry_django.field(description="The ID of the history entry.")
    def id(self, info: Info) -> strawberry.ID:
        """This method returns the ID of the history entry."""
        return self.history_id

    @strawberry_django.field(description="The effective changes made to the model.")
    def effective_changes(self, info: Info) -> list[ModelChange]:
        """This method returns the effective changes made to the model."""
        new_record, old_record = self, self.prev_record

        changes = []
        if old_record is None:
            return changes

        delta = new_record.diff_against(old_record)
        for change in delta.changes:
            changes.append(
                ModelChange(
                    field=change.field, old_value=change.old, new_value=change.new
                )
            )

        return changes



