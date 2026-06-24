import strawberry_django
import strawberry
from testing_module import models
from koherent.strawberry.extension import KoherentExtension
from koherent.strawberry.types import ProvenanceEntry
from koherent.strawberry.filters import ProvenanceFilterMixin
from strawberry_django.filters import FilterLookup, filter_type
from strawberry_django.optimizer import DjangoOptimizerExtension
from authentikate.strawberry.extension import AuthentikateExtension
from kante.types import Info



@filter_type(models.MyModel, description="Filter MyModel, including by provenance.")
class MyModelFilter(ProvenanceFilterMixin):
    """Filter for MyModel. Inherits the drop-in provenance filter."""

    your_field: FilterLookup[str] | None


@strawberry_django.type(models.MyModel, filters=MyModelFilter)
class MyModel:
    """ Model to test the Koherent extension. """
    id: strawberry.ID
    your_field: str
    provenance: list["ProvenanceEntry"] = strawberry_django.field(
        field_name="provenance_entries"
    )



@strawberry.type
class Query:
    """ Queries for the MyModel model. """

    # Auto-generated list field so the MyModelFilter (and its drop-in provenance
    # filter) is exposed as a `filters` argument and applied to the queryset.
    my_models: list[MyModel] = strawberry_django.field(
        description="An example of a query that returns a list of models."
    )

    @strawberry_django.field
    def my_model(self, info: Info, id: strawberry.ID) -> MyModel:
        """ An example of a query that returns a model. """
        return models.MyModel.objects.get(id=id)

@strawberry.type
class Mutation:
    """ Mutations for the MyModel model. """

    @strawberry_django.mutation
    def create_model(self, info: Info, your_field: str) -> MyModel:
        """ An example of a mutation that creates a model. """
        model = models.MyModel.objects.create(your_field=your_field)
        # This will create a new history entry (by sending a signal)
        # bound to the current user and the task id

        return model

    @strawberry_django.mutation
    def update_model(self, info: Info, id: strawberry.ID, your_field: str) -> MyModel:
        """ An example of a mutation that updates a model. """
        model = models.MyModel.objects.get(id=id)
        model.your_field = your_field
        model.save()
        # This will create a new history entry (by sending a signal)
        # bound to the current user and the task id

        return model



# authentikate's strawberry types carry Apollo Federation @key directives, so
# the schema must be a federation schema to serialize them.
schema = strawberry.federation.Schema(query=Query, mutation=Mutation, extensions=[AuthentikateExtension, KoherentExtension, DjangoOptimizerExtension])