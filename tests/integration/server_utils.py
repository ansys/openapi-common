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

"""Process-spawn helpers for integration tests that need a real uvicorn server."""

# PEP 563 postponed annotations — safe to drop when the project's minimum Python
# evaluates annotations lazily by default; confirm PEP 649 / release notes before
# removing ``from __future__ import annotations``.
from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from multiprocessing import Process
from time import sleep


@contextmanager
def spawn_uvicorn_subprocess(target: Callable[[], None]) -> Generator[None, None, None]:
    """Run ``target`` (a no-arg entrypoint that calls ``uvicorn.run``) in a daemon process."""
    proc = Process(target=target, daemon=True)
    proc.start()
    try:
        yield
    finally:
        proc.terminate()
        while proc.is_alive():
            sleep(1)


@contextmanager
def spawn_uvicorn_with_optional_context(
    target: Callable[[], None],
    outer: AbstractContextManager[None] | None = None,
) -> Generator[None, None, None]:
    """Like :func:`spawn_uvicorn_subprocess`, optionally wrapped in another context (e.g. header env)."""
    if outer is None:
        with spawn_uvicorn_subprocess(target):
            yield
    else:
        with outer:
            with spawn_uvicorn_subprocess(target):
                yield
