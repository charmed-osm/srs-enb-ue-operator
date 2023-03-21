# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Set of utils functions used in charm."""

import logging
import subprocess
import time
from typing import Callable, Optional

import netifaces  # type: ignore[import]

logger = logging.getLogger(__name__)


def shell(command: str) -> str:
    """Runs a shell command."""
    response = subprocess.run(command, shell=True, stdout=subprocess.PIPE, encoding="utf-8")
    response.check_returncode()
    return response.stdout


def ip_from_default_iface() -> Optional[str]:
    """Returns the default interface's IP address."""
    default_gateway = netifaces.gateways()["default"]
    if netifaces.AF_INET in default_gateway:
        _, iface = default_gateway[netifaces.AF_INET]
        default_interface = netifaces.ifaddresses(iface)
        if netifaces.AF_INET in default_interface:
            return default_interface[netifaces.AF_INET][0].get("addr")
    return None


def get_iface_ip_address(iface: str) -> Optional[str]:
    """Get the IP address of the given interface.

    Args:
        iface: The interface name.

    Returns:
        str: UE's IP address.
    """
    try:
        return netifaces.ifaddresses(iface)[netifaces.AF_INET][0]["addr"]
    except ValueError:
        logging.error(f"Could not get IP address. {iface} is not a valid interface.")
        return None


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
