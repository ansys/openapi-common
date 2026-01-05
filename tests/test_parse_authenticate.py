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

import itertools

import pytest

from ansys.openapi.common._util import CaseInsensitiveOrderedDict, parse_authenticate

negotiate_challenges_with_tokens = (
    ("Negotiate abcdef", {"negotiate": "abcdef"}),
    ("Negotiate abcdef=", {"negotiate": "abcdef="}),
    ("Negotiate abcdef==", {"negotiate": "abcdef=="}),
)

challenges = (
    ("Negotiate", {"negotiate": None}),
    ('Bearer realm="example.com"', {"bearer": {"realm": "example.com"}}),
    (
        'Bearer error="invalid_token", url="localhost:2314"',
        {"bearer": {"error": "invalid_token", "url": "localhost:2314"}},
    ),
    (
        'Digest realm="example.com", qop="auth,auth-int", nonce="abcdef", opaque="ghijkl"',
        {
            "digest": {
                "realm": "example.com",
                "qop": "auth,auth-int",
                "nonce": "abcdef",
                "opaque": "ghijkl",
            }
        },
    ),
)

test_challenges = []
test_outcomes = []
for test_length in range(1, 4):
    combinations = itertools.combinations(challenges, test_length)
    for combination in combinations:
        test_challenges.extend([", ".join(component[0] for component in combination)])
        outcomes = {}  # type: ignore
        for component in combination:
            outcomes.update(**component[1])  # type: ignore
        test_outcomes.append(CaseInsensitiveOrderedDict(outcomes))


@pytest.mark.parametrize("test_input, expected", negotiate_challenges_with_tokens)
def test_negotiate_with_token(test_input, expected):
    obtained = parse_authenticate(test_input)
    assert obtained == CaseInsensitiveOrderedDict(expected)


@pytest.mark.parametrize("test_input, expected", zip(test_challenges, test_outcomes))
def test_multiple_challenges(test_input, expected):
    obtained = parse_authenticate(test_input)
    assert obtained == expected


def test_invalid_header_character():
    with pytest.raises(ValueError) as exception_info:
        _ = parse_authenticate("Bearer cost=(£35)")
    assert "Failed to parse value" in str(exception_info)


@pytest.mark.skip(reason="Do we want this to throw?")
def test_invalid_header_malformed():
    with pytest.raises(ValueError) as exception_info:
        _ = parse_authenticate("Bearer cost=35=12")
    assert "Failed to parse value" in str(exception_info)
