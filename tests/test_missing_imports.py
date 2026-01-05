# Copyright (C) 2022 - 2026 ANSYS, Inc. and/or its affiliates.
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

import copy
import os
import sys

import pytest

init_modules = []


def get_package_name() -> str:
    import ansys.openapi.common

    try:
        from importlib.metadata import metadata
    except ImportError:  # Python 3.7
        from importlib_metadata import metadata
    return metadata(ansys.openapi.common.__name__)["Name"]


class TestMissingExtras:
    real_import = __import__
    blocked_import = ""
    base_module_list = ["ansys.openapi.common._session", "ansys.openapi.common"]

    @pytest.fixture(autouse=True)
    def module_clearing_fixture(self):
        initial_modules = copy.copy(list(sys.modules.keys()))
        for m in initial_modules:
            if m in self.base_module_list:
                sys.modules.pop(m)

    def mocked_import(self, name, *args):
        if name == self.blocked_import:
            raise ImportError
        else:
            return self.real_import(name, *args)

    def test_create_oidc_with_no_extra_throws(self, mocker):
        self.blocked_import = "requests_auth"
        mocker.patch("builtins.__import__", side_effect=self.mocked_import)

        from ansys.openapi.common import ApiClientFactory

        with pytest.raises(ImportError) as excinfo:
            _ = ApiClientFactory("http://www.my-api.com/v1.svc").with_oidc()

        package_name = get_package_name()
        assert f"`pip install {package_name}[oidc]`" in str(excinfo.value)

    @pytest.mark.skipif(os.name == "nt", reason="Test only applies to linux")
    def test_create_autologon_on_linux_with_no_extra_throws(self, mocker):
        self.blocked_import = "requests_kerberos"
        mocker.patch("builtins.__import__", side_effect=self.mocked_import)

        from ansys.openapi.common import ApiClientFactory

        with pytest.raises(ImportError) as excinfo:
            _ = ApiClientFactory("http://www.my-api.com/v1.svc").with_autologon()

        package_name = get_package_name()
        assert f"`pip install {package_name}[linux-kerberos]`" in str(excinfo.value)
