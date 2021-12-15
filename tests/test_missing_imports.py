import pytest
import sys

init_modules = []


class TestMissingExtras:
    init_modules = None
    real_import = __import__

    @pytest.fixture(autouse=True)
    def module_clearing_fixture(self):
        if self.init_modules is not None:
            # second or subsequent run: remove all but initially loaded modules
            for m in sys.modules.keys():
                if m not in self.init_modules:
                    del sys.modules[m]
        else:
            # first run: find out which modules were initially loaded
            self.init_modules = sys.modules.keys()

    def mocked_import(self, name, *args):
        if name == "requests_oauthlib":
            raise ImportError
        else:
            return self.real_import(name, *args)

    def test_create_oidc_with_no_extra_throws(self, mocker):
        with mocker.patch("builtins.__import__", side_effect=self.mocked_import):
            from ansys.openapi.common import ApiClientFactory

            with pytest.raises(ImportError) as excinfo:
                _ = ApiClientFactory("http://www.my-api.com/v1.svc").with_oidc()

            assert "`pip install openapi-client-common[oidc]`" in str(excinfo.value)

    def test_create_autologon_with_no_extra_on_linux_throws(self, mocker):
        with mocker.patch("builtins.__import__", side_effect=self.mocked_import):
            mocker.patch("os.name", "linux")
            from ansys.openapi.common import ApiClientFactory

            with pytest.raises(ImportError) as excinfo:
                _ = ApiClientFactory("http://www.my-api.com/v1.svc").with_autologon()

            assert "`pip install openapi-client-common[linux-kerberos]`" in str(
                excinfo.value
            )
