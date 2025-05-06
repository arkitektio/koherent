import strawberry_django 
import strawberry
from testing_module import models
from koherent.strawberry.extension import KoherentExtension
from koherent.strawberry.types import ProvenanceEntry
from strawberry_django.optimizer import DjangoOptimizerExtension
from authentikate.strawberry.extension import AuthentikateExtension
from kante.types import Info



@strawberry_django.type(models.MyModel)
class MyModel:
    """ Model to test the Koherent extension. """
    id: strawberry.ID
    your_field: str
    provenance_entries: list["ProvenanceEntry"]
    
    
    
@strawberry.type
class Query:
    """ Queries for the MyModel model. """
    
    @strawberry_django.field
    def my_models(self, info: Info) -> list[MyModel]:
        """ An example of a query that returns a list of models. """
        return models.MyModel.objects.all()

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
        # bound to the current user and the assignation id

        return model

    @strawberry_django.mutation
    def update_model(self, info: Info, id: strawberry.ID, your_field: str) -> MyModel:
        """ An example of a mutation that updates a model. """
        model = models.MyModel.objects.get(id=id)
        model.your_field = your_field
        model.save()
        # This will create a new history entry (by sending a signal)
        # bound to the current user and the assignation id

        return model



schema = strawberry.Schema(query=Query, mutation=Mutation, extensions=[AuthentikateExtension, KoherentExtension, DjangoOptimizerExtension])