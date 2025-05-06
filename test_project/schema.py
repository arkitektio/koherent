import strawberry_django 
import strawberry
from testing_module import models
from koherent.strawberry.extension import KoherentExtension
from koherent.strawberry.types import ProvenanceEntry
from strawberry_django.optimizer import DjangoOptimizerExtension
from authentikate.strawberry.extension import AuthentikateExtension

@strawberry_django.type(models.MyModel)
class MyModel:
    id: strawberry.ID
    your_field: str
    provenance_entries: list["ProvenanceEntry"]
    
    
    
@strawberry.type
class Query:
    
    
    @strawberry_django.field
    def my_models(self, info) -> list[MyModel]:
        return models.MyModel.objects.all()

    @strawberry_django.field
    def my_model(self, info, id: strawberry.ID) -> MyModel:
        return models.MyModel.objects.get(id=id)

@strawberry.type
class Mutation:

    @strawberry_django.mutation
    def create_model(self, info, your_field: str) -> MyModel:
        model = models.MyModel.objects.create(your_field=your_field)
        # This will create a new history entry (by sending a signal)
        # bound to the current user and the assignation id

        return model

    @strawberry_django.mutation
    def update_model(self, info, id: strawberry.ID, your_field: str) -> MyModel:
        model = models.MyModel.objects.get(id=id)
        model.your_field = your_field
        model.save()
        # This will create a new history entry (by sending a signal)
        # bound to the current user and the assignation id

        return model



schema = strawberry.Schema(query=Query, mutation=Mutation, extensions=[AuthentikateExtension, KoherentExtension, DjangoOptimizerExtension])