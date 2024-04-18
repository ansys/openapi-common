# Copyright (C) 2022 - 2024 ANSYS, Inc. and/or its affiliates.
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

import logging
import sys

import pytest

log_format = "%(levelname)s %(asctime)s - %(message)s"
logging.basicConfig(stream=sys.stdout, format=log_format, level=logging.DEBUG)


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
        parser.addoption(f"--with-{marker}", action="store_true", default=False, help=info["help"])


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
