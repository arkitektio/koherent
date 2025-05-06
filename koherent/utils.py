from typing import Mapping


def get_assignation_id_or_none(headers: Mapping[str, str]) -> str | None:
    """ Retrieves the assignation ID from the headers, if present. """
    return headers.get("x-assignation-id", None)
