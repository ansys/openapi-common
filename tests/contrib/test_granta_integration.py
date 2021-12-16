import pytest

from ansys.openapi.common import create_session_from_granta_stk
from ansys.openapi.common import ApiClientFactory
from unittest.mock import patch, MagicMock


def test_basic_session():
    user_name = "USER"
    password = "PASSWORD"
    stk_basic_config = {
        "api_url": "http://localhost/mi_servicelayer",
        "authentication": {
            "mode": "credential",
            "user_name": user_name,
            "password": password,
            "domain": None,
        },
    }
    with patch.object(
        ApiClientFactory, "with_credentials", return_value=MagicMock()
    ) as mock_method:
        _ = create_session_from_granta_stk(stk_basic_config)
    mock_method.assert_called_once_with(user_name, password, None)


def test_missing_basic_parameter_throws():
    user_name = "USER"
    password = "PASSWORD"
    stk_basic_config = {
        "api_url": "http://localhost/mi_servicelayer",
        "authentication": {
            "mode": "credential",
            "user_name": user_name,
            "password": password,
        },
    }
    with pytest.raises(KeyError) as excinfo:
        _ = create_session_from_granta_stk(stk_basic_config)
    assert "domain" in str(excinfo.value)


def test_autologon_session():
    stk_autologon_config = {
        "api_url": "http://localhost/mi_servicelayer",
        "authentication": {"mode": "autologon"},
    }
    with patch.object(
        ApiClientFactory, "with_autologon", return_value=MagicMock()
    ) as mock_method:
        _ = create_session_from_granta_stk(stk_autologon_config)
    mock_method.assert_called_once_with()


def test_provided_token_session():
    refresh_token = "dGhpcyBpcyBhIHRva2VuLCBob25lc3Qh"
    stk_token_config = {
        "api_url": "http://localhost/mi_servicelayer",
        "authentication": {"mode": "oidc_token", "refresh_token": refresh_token},
    }
    builder = MagicMock()
    builder.with_token.return_value = MagicMock()

    with patch.object(
        ApiClientFactory, "with_oidc", return_value=builder
    ) as mock_method:
        _ = create_session_from_granta_stk(stk_token_config)
    mock_method.assert_called_once_with(None)
    builder.with_token.assert_called_once_with(refresh_token)


def test_stored_token_session():
    token_key = "token_key"
    stk_token_config = {
        "api_url": "http://localhost/mi_servicelayer",
        "authentication": {"mode": "oidc_stored_token", "token_key": token_key},
    }
    builder = MagicMock()
    builder.with_stored_token.return_value = MagicMock()

    with patch.object(
        ApiClientFactory, "with_oidc", return_value=builder
    ) as mock_method:
        _ = create_session_from_granta_stk(stk_token_config)
    mock_method.assert_called_once_with(None)
    builder.with_stored_token.assert_called_once_with(token_key)


def test_invalid_mode_throws():
    invalid_mode = "invalid_mode"
    stk_invalid_token = {
        "api_url": "http://localhost/mi_servicelayer",
        "authentication": {"mode": "invalid_mode"},
    }
    with pytest.raises(KeyError) as excinfo:
        _ = create_session_from_granta_stk(stk_invalid_token)

    assert invalid_mode in str(excinfo.value)
