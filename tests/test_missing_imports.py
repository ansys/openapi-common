import copy
import os

import pytest
import sys

init_modules = []


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
        self.blocked_import = "requests_oauthlib"
        mocker.patch("builtins.__import__", side_effect=self.mocked_import)

        from ansys.openapi.common import ApiClientFactory

        with pytest.raises(ImportError) as excinfo:
            _ = ApiClientFactory("http://www.my-api.com/v1.svc").with_oidc()

        assert "`pip install openapi-client-common[oidc]`" in str(excinfo.value)

    @pytest.mark.skipif(os.name == 'nt', reason="Test only applies to linux")
    def test_create_autologon_on_linux_with_no_extra_throws(self, mocker):
        self.blocked_import = "requests_kerberos"
        mocker.patch("builtins.__import__", side_effect=self.mocked_import)

        from ansys.openapi.common import ApiClientFactory

        with pytest.raises(ImportError) as excinfo:
            _ = ApiClientFactory("http://www.my-api.com/v1.svc").with_autologon()

        assert "`pip install openapi-client-common[linux-kerberos]`" in str(excinfo.value)
