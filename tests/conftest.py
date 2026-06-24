import datetime
import uuid

import pytest
from joserfc import jwt
from joserfc.jwk import OKPKey

from authentikate.provenance import CANONICALIZATION_VERSION, ProvenanceToken

# The Ed25519 private key whose public half is published in test_project.settings
# (PROVENANCE_TEST_PUBLIC_JWK). Provenance tokens carry no static-token bypass, so
# tests mint a genuinely signed EdDSA token here and authentikate verifies it.
_PROVENANCE_TEST_PRIVATE_JWK = {
    "kty": "OKP",
    "crv": "Ed25519",
    "x": "Q5ERwdSKvHLDx8swyRJzrofI4W567dx71oeH_uDH4g4",
    "d": "PQ_Y54LpnaQZ24wKvkroJ3feOo4FJ2YcvKRmv8l9C5E",
    "kid": "koherent-test-key",
}
_PROVENANCE_TEST_KEY = OKPKey.import_key(_PROVENANCE_TEST_PRIVATE_JWK)


def provenance_token(
    tsk: str = "task-1",
    rcb: str = "1",
    parent: str | None = None,
    sub: str | None = None,
    root: str | None = None,
    agent_sub: str = "1",
    agent_cid: str = "static",
    audience: str = "koherent",
    args_hash: str = "deadbeef",
) -> str:
    """Mint a signed EdDSA provenance token for the Rekuest-Task header.

    Defaults describe a root task caused by the static "test" identity
    (sub "1") and executed by the static agent (sub "1", client_id "static").
    """
    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    claims = {
        "iss": "rekuest",
        "aud": [audience],
        "sub": sub if sub is not None else rcb,
        "act": {"sub": agent_sub, "cid": agent_cid},
        "iat": now,
        "exp": now + 3600,
        "jti": uuid.uuid4().hex,
        "tsk": tsk,
        "ptk": parent,
        "rtk": root if root is not None else tsk,
        "rcb": rcb,
        "ahs": args_hash,
        "aha": CANONICALIZATION_VERSION,
    }
    return jwt.encode(
        {"alg": "EdDSA", "kid": "koherent-test-key"},
        claims,
        _PROVENANCE_TEST_KEY,
        algorithms=["EdDSA"],
    )


def provenance_obj(
    tsk: str = "task-x",
    rcb: str = "1",
    parent: str | None = None,
    sub: str | None = None,
    root: str | None = None,
    agent_sub: str = "1",
    agent_cid: str = "static",
    args_hash: str = "deadbeef",
) -> ProvenanceToken:
    """Build a decoded ProvenanceToken for unit tests that set the context var."""
    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    return ProvenanceToken(
        iss="rekuest",
        aud=["koherent"],
        sub=sub if sub is not None else rcb,
        act={"sub": agent_sub, "cid": agent_cid},
        iat=now,
        exp=now + 3600,
        jti=uuid.uuid4().hex,
        tsk=tsk,
        ptk=parent,
        rtk=root if root is not None else tsk,
        rcb=rcb,
        ahs=args_hash,
        aha=CANONICALIZATION_VERSION,
        raw="",
    )


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Headers for the static "test" token (sub "1", org "static_org")."""
    return {"Authorization": "Bearer test"}


@pytest.fixture
def task_headers(auth_headers: dict[str, str]) -> dict[str, str]:
    """Auth headers plus a provenance token caused by the requesting user."""
    return {**auth_headers, "Rekuest-Task": provenance_token()}
