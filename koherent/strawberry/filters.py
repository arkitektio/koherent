from strawberry import auto
from koherent import models
from koherent.types import Info
import strawberry_django
from authentikate.strawberry.filters import UserFilter
from django.db.models.query import QuerySet


@strawberry_django.order(models.AppHistoryModel)
class ProvenanceOrder:
    """Ordering options for the Provenance model."""

    history_date: auto


@strawberry_django.filter(models.AppHistoryModel)
class ProvenanceFilter:
    """Filtering options for the Provenance model."""

    user: UserFilter | None
    during: str | None

    def filter_during(
        self, queryset: QuerySet[models.AppHistoryModel], info: Info
    ) -> QuerySet[models.AppHistoryModel]:
        queryset

        if self.during is None:
            return queryset

        return queryset.filter(provenance__assignation_id=self.during).distinct()
