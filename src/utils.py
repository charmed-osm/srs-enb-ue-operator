# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Set of utils functions used in charm."""

import subprocess
import time
from typing import Callable


def shell(command: str) -> str:
    """Runs a shell command."""
    response = subprocess.run(command, shell=True, stdout=subprocess.PIPE, encoding="utf-8")
    response.check_returncode()
    return response.stdout


def wait_for_condition(condition: Callable, timeout: int) -> bool:
    """Wait for given condition to be met.

    Args:
        condition: A function that returns a boolean.
        timeout: Timeout in seconds.

    Returns:
        bool: Whether condition is met.
    """
    start = time.time()
    while time.time() - start < timeout:
        if condition():
            return True
        time.sleep(0.5)
    return False
