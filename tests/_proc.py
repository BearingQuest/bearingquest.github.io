"""The one place the tests start a process."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

import pytest


def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[Any]:
    """Run a fixed test command with its executable resolved to an absolute path.

    The executable is looked up on the PATH of kwargs["env"] when one is given,
    so a test's restricted PATH applies to the lookup as well.
    """
    env = kwargs.get("env")
    executable = shutil.which(args[0], path=env.get("PATH") if env else None)
    if executable is None:
        pytest.fail(f"{args[0]} not found on PATH")
    return subprocess.run([executable, *args[1:]], **kwargs)  # noqa: S603  # fixed test commands; arguments come from the test, never from outside input
