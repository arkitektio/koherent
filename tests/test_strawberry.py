""" Test that a Http request receives a broadcast from an HTTP mutation."""

import pytest
import asyncio
from uuid import uuid4

from test_project.asgi import application
from kante.testing import GraphQLHttpTestClient, GraphQLWebSocketTestClient
from django.conf import settings

@pytest.mark.asyncio
async def test_can_create_models(db, valid_auth_headers, key_pair_str) -> None:
    """ Test that a WebSocket subscription receives a broadcast from an HTTP mutation."""
    # Initialize both clients
    
    
    
    # Set the public key in settings
    settings.AUTHENTIKATE["PUBLIC_KEY"] = key_pair_str.public_key
    
    
    
    http_client = GraphQLHttpTestClient(application=application,
                                        headers=valid_auth_headers)
    
    
    # Send the mutation via HTTP
    answer = await http_client.execute(
        query="""
        mutation {
            createModel(yourField: "test") {
                id
            }
        }
        """,
    )
    
    

    assert answer["data"] is not None, f"Expected data to be present {answer}"
    assert answer["data"]["createModel"] is not None
    assert answer["data"]["createModel"]["id"] is not None

    # Send the mutation via HTTP
    answer = await http_client.execute(
        query="""
        query {
            myModels {
                id
            }
        }
        """,
    )
    
    assert answer["data"] is not None, f"Expected data to be present {answer}"
    
    assert answer["data"]["myModels"] is not None
    assert len(answer["data"]["myModels"]) > 0, "Expected at least one model"
    assert answer["data"]["myModels"][0]["id"] is not None
    
    
    
@pytest.mark.asyncio
async def test_can_track_provenance(db, valid_auth_headers, key_pair_str) -> None:
    """ Test that a WebSocket subscription receives a broadcast from an HTTP mutation."""
    # Initialize both clients
    
    
    
    # Set the public key in settings
    settings.AUTHENTIKATE["PUBLIC_KEY"] = key_pair_str.public_key
    
    
    
    http_client = GraphQLHttpTestClient(application=application,
                                        headers=valid_auth_headers)
    
    
    # Send the mutation via HTTP
    answer = await http_client.execute(
        query="""
        mutation {
            createModel(yourField: "test") {
                id
                provenanceEntries {
                    id
                }
            }
        }
        """,
    )
    
    
    
    
    

    assert answer["data"] is not None, f"Expected data to be present {answer}"
    assert answer["data"]["createModel"] is not None
    assert answer["data"]["createModel"]["id"] is not None
    
    
    
    answer = await http_client.execute(
        query="""
        mutation($yourField: String!, $id: ID!) {
            updateModel(yourField: $yourField, id: $id) {
                id
                provenanceEntries {
                    id
                    user {
                        sub
                    }
                    kind
                    during
                }
            }
        }
        """,
        variables={
            "id": answer["data"]["createModel"]["id"],
            "yourField": "test updated",
        },
    )

    assert answer["data"] is not None, f"Expected data to be present {answer}"
    assert answer["data"]["updateModel"] is not None
    assert answer["data"]["updateModel"]["id"] is not None
    assert len(answer["data"]["updateModel"]["provenanceEntries"]) > 1, "Expected at least one provenance entry {answer}"

    # Send the mutation via HTTP
    answer = await http_client.execute(
        query="""
        query {
            myModels {
                id
            }
        }
        """,
    )
    
    assert answer["data"] is not None, f"Expected data to be present {answer}"
    
    assert answer["data"]["myModels"] is not None
    assert len(answer["data"]["myModels"]) > 0, "Expected at least one model"
    assert answer["data"]["myModels"][0]["id"] is not None
    
    
    
@pytest.mark.asyncio
async def test_can_track_provenance(db, valid_auth_and_assignation_headers, key_pair_str) -> None:
    """ Test that a WebSocket subscription receives a broadcast from an HTTP mutation."""
    # Initialize both clients
    
    
    
    # Set the public key in settings
    settings.AUTHENTIKATE["PUBLIC_KEY"] = key_pair_str.public_key
    
    
    
    http_client = GraphQLHttpTestClient(application=application,
                                        headers=valid_auth_and_assignation_headers)
    
    
    # Send the mutation via HTTP
    answer = await http_client.execute(
        query="""
        mutation {
            createModel(yourField: "test") {
                id
                provenanceEntries {
                    id
                }
            }
        }
        """,
    )
    
    
    
    
    

    assert answer["data"] is not None, f"Expected data to be present {answer}"
    assert answer["data"]["createModel"] is not None
    assert answer["data"]["createModel"]["id"] is not None
    
    
    
    answer = await http_client.execute(
        query="""
        mutation($yourField: String!, $id: ID!) {
            updateModel(yourField: $yourField, id: $id) {
                id
                provenanceEntries {
                    id
                    user {
                        sub
                    }
                    kind
                    date
                    during
                    
                }
            }
        }
        """,
        variables={
            "id": answer["data"]["createModel"]["id"],
            "yourField": "test updated",
        },
    )

    assert answer["data"] is not None, f"Expected data to be present {answer}"
    assert answer["data"]["updateModel"] is not None
    assert answer["data"]["updateModel"]["id"] is not None
    
    for i in answer["data"]["updateModel"]["provenanceEntries"]:
        assert i["user"] is not None
        assert i["user"]["sub"] is not None
        assert i["during"] is not None, "Expected during to be present because"
        assert i["kind"] is not None

    # Send the mutation via HTTP
    answer = await http_client.execute(
        query="""
        query {
            myModels {
                id
            }
        }
        """,
    )
    
    assert answer["data"] is not None, f"Expected data to be present {answer}"
    
    assert answer["data"]["myModels"] is not None
    assert len(answer["data"]["myModels"]) > 0, "Expected at least one model"
    assert answer["data"]["myModels"][0]["id"] is not None