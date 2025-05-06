import contextvars

current_assignation_id = contextvars.ContextVar("current_assignation_id", default=None)
  
    
def get_current_assignation_id() -> str | None:
    """
    Get the current assignation id from the context variable
    Returns
    -------
    str | None
        The current assignation id
    """
    return current_assignation_id.get()