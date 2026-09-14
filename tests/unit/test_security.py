from __future__ import annotations

import pytest

from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_round_trip():
    hashed = hash_password("ChangeMe123!")
    assert hashed != "ChangeMe123!"
    assert verify_password("ChangeMe123!", hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_carries_role_and_email():
    token = create_access_token("abc", role="admin", email="a@b.c")
    claims = decode_token(token)
    assert claims["sub"] == "abc"
    assert claims["role"] == "admin"
    assert claims["email"] == "a@b.c"


def test_refresh_token_rejected_as_access_token():
    token = create_refresh_token("abc")
    with pytest.raises(AuthenticationError):
        decode_token(token, expected_type="access")
    assert decode_token(token, expected_type="refresh")["sub"] == "abc"


def test_tampered_token_rejected():
    token = create_access_token("abc", role="admin", email="a@b.c")
    with pytest.raises(AuthenticationError):
        decode_token(token[:-2] + "xx")
