from .._util import SessionConfiguration
from .._session import ApiClient, ApiClientFactory
from typing import Dict, Any, Optional


def create_session_from_granta_stk(
    stk_configuration: Dict[str, Any],
    api_session_configuration: Optional[SessionConfiguration] = None,
    idp_session_configuration: Optional[SessionConfiguration] = None,
) -> "ApiClient":
    """Set up the client authentication using the configured authentication from a Granta MI Scripting Toolkit session.

    Parameters
    ----------
    stk_configuration : Dict
        Configuration dictionary provided by the Granta MI Scripting Toolkit session.
    api_session_configuration : Optional[SessionConfiguration]
        Additional configuration settings for the requests Session when connected to the Granta MI Service Layer.
    idp_session_configuration : Optional[SessionConfiguration]
        Additional configuration settings for the requests Session when connected to the OpenID Identity Provider.

    Notes
    -----
    Requires the user to have the Granta MI Scripting Toolkit installed with at least version 2.4,
    otherwise use the appropriate class method to configure the ``requests`` session.
    """
    sl_url = stk_configuration["api_url"]
    auth_settings = stk_configuration["authentication"]
    mode = auth_settings["mode"]
    if mode == "autologon":
        return (
            ApiClientFactory(sl_url, api_session_configuration)
            .with_autologon()
            .connect()
        )
    elif mode == "credential":
        username = auth_settings["user_name"]
        password = auth_settings["password"]
        domain = auth_settings["domain"]
        return (
            ApiClientFactory(sl_url, api_session_configuration)
            .with_credentials(username, password, domain)
            .connect()
        )
    elif mode == "oidc_stored_token":
        cached_token_key = auth_settings["token_key"]
        return (
            ApiClientFactory(sl_url, api_session_configuration)
            .with_oidc(idp_session_configuration)
            .with_stored_token(cached_token_key)
            .connect()
        )
    elif mode == "oidc_token":
        refresh_token = auth_settings["refresh_token"]
        return (
            ApiClientFactory(sl_url, api_session_configuration)
            .with_oidc(idp_session_configuration)
            .with_token(refresh_token)
            .connect()
        )
    else:
        raise KeyError(f"Invalid mode: {mode}")
