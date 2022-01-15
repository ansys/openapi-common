import pytest

# Create a dict of markers.
# The key is used as option, so --with-{key} will run all tests marked with key.
# The value must be a dict that specifies:
# 1. 'help': the command line help text
# 2. 'marker-descr': a description of the marker
# 3. 'skip-reason': displayed reason whenever a test with this marker is skipped.
optional_markers = {
    "kerberos": {
        "help": "Run the optional kerberos integration tests",
        "marker-descr": "Tests rely on a working kerberos setup on linux",
        "skip-reason": "Test only runs with the --with-kerberos option.",
    },
}


def pytest_addoption(parser):
    for marker, info in optional_markers.items():
        parser.addoption(
            f"--with-{marker}", action="store_true", default=False, help=info["help"]
        )


def pytest_configure(config):
    for marker, info in optional_markers.items():
        config.addinivalue_line("markers", f"{marker}: {info['marker-descr']}")


def pytest_collection_modifyitems(config, items):
    for marker, info in optional_markers.items():
        if not config.getoption(f"--with-{marker}"):
            skip_test = pytest.mark.skip(reason=info["skip-reason"])
            for item in items:
                if marker in item.keywords:
                    item.add_marker(skip_test)
