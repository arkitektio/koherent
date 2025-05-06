from typing import AsyncIterator, Iterator, Union
from strawberry.extensions import SchemaExtension
from kante.context import WsContext, HttpContext
from koherent.vars import  current_assignation_id
from koherent.utils import get_assignation_id_or_none
class KoherentExtension(SchemaExtension):
    """ This is the extension class for the kohrerent extension """
    
    
    async def on_operation(self) -> Union[AsyncIterator[None], Iterator[None]]:
        """ Set the token in the context variable """
        
        context = self.execution_context.context
        
        reset_assignation_id = None
        
        if isinstance(context, WsContext):
            # WebSocket context
            # Do something with the WebSocket context
            # We cannot get the assignation id, from a websocket context
            # because its persistent throughout the connection,
            # mutations are never allowed in a websocket context
            
            if self.execution_context.operation_name == "mutation":
                raise ValueError("Mutations are not allowed in a websocket context. Because we cannot track the assignation id.")
            
            
            
        
        elif isinstance(context, HttpContext):
            # HTTP context
            # Do something with the HTTP context
            assignation_id = get_assignation_id_or_none(
                context.headers,
            )
            if assignation_id is not None:
                
                # Set the assignation id in the context variable
                reset_assignation_id = current_assignation_id.set(assignation_id)
                context.request.set_extension("assignation_id", assignation_id)
            
        else:
            raise ValueError("Unknown context type. Cannot determine if it's WebSocket or HTTP.")
           
        
        yield 
        
        
        # Cleanup
        if reset_assignation_id:
            current_assignation_id.reset(reset_assignation_id)
        
        return 
        
       
       

        