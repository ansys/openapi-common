# Copyright (C) 2022 - 2025 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Provides a helper to create sessions for use with Ansys OpenAPI clients."""

from importlib import metadata as metadata

__version__ = metadata.version("ansys-openapi-common")

from ._api_client import ApiClient
from ._base import ApiBase, ApiClientBase, ModelBase, Unset, Unset_Type
from ._exceptions import (
    ApiConnectionException,
    ApiException,
    AuthenticationWarning,
    UndefinedObjectWarning,
)
from ._session import ApiClientFactory, AuthenticationScheme, OIDCSessionBuilder
from ._util import SessionConfiguration, generate_user_agent

__all__ = [
    "ApiClient",
    "ApiClientFactory",
    "AuthenticationScheme",
    "SessionConfiguration",
    "ApiException",
    "ApiConnectionException",
    "AuthenticationWarning",
    "generate_user_agent",
    "OIDCSessionBuilder",
    "ApiBase",
    "ApiClientBase",
    "ModelBase",
    "UndefinedObjectWarning",
    "Unset",
    "Unset_Type",
]
