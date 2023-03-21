# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Set of utils functions used in charm."""

import logging
import subprocess
import time
from subprocess import CalledProcessError
from typing import Callable, List, Optional

import netifaces  # type: ignore[import]
from netaddr import IPAddress, IPNetwork  # type: ignore[import]
from netaddr.core import AddrFormatError  # type: ignore[import]

logger = logging.getLogger(__name__)


def service_active(service_name: str) -> bool:
    """Returns whether a given service is active."""
    try:
        response = shell(f"systemctl is-active {service_name}")
        return response == "active\n"
    except CalledProcessError:
        return False


def shell(command: str) -> str:
    """Runs a shell command."""
    response = subprocess.run(command, shell=True, stdout=subprocess.PIPE, encoding="utf-8")
    response.check_returncode()
    return response.stdout


def get_local_ipv4_networks() -> List[IPNetwork]:
    """Returns list of IPv4 networks."""
    networks = []
    interfaces = netifaces.interfaces()
    for interface in interfaces:
        addresses = netifaces.ifaddresses(interface)
        if netifaces.AF_INET in addresses:
            ipv4_addr = addresses[netifaces.AF_INET][0]
            network = IPNetwork(f'{ipv4_addr["addr"]}/{ipv4_addr["netmask"]}')
            networks.append(network)
    return networks


def is_ipv4(ip: str) -> bool:
    """Returns whether an IP address is IPv4."""
    try:
        if not isinstance(ip, str) or len(ip.split(".")) != 4:
            return False
        IPAddress(ip)
        return True
    except AddrFormatError:
        return False


def _systemctl(action: str, service_name: str) -> None:
    shell(f"systemctl {action} {service_name}")


def service_restart(service_name: str) -> None:
    """Restarts a given service."""
    _systemctl("restart", service_name)
    logger.info("Service %s restarted", service_name)


def service_stop(service_name: str) -> None:
    """Stops a given service."""
    _systemctl("stop", service_name)
    logger.info("Service %s stopped", service_name)


def service_enable(service_name: str) -> None:
    """Enables a given service."""
    _systemctl("enable", service_name)
    logger.info("Service %s enabled", service_name)


def systemctl_daemon_reload() -> None:
    """Runs `systemctl daemon-reload`."""
    shell("systemctl daemon-reload")
    logger.info("Systemd manager configuration reloaded")


def ip_from_default_iface() -> Optional[str]:
    """Returns a Ip address from the default interface."""
    default_gateway = netifaces.gateways()["default"]
    if netifaces.AF_INET in default_gateway:
        _, iface = netifaces.gateways()["default"][netifaces.AF_INET]
        default_interface = netifaces.ifaddresses(iface)
        if netifaces.AF_INET in default_interface:
            return netifaces.ifaddresses(iface)[netifaces.AF_INET][0].get("addr")
    return None


def ip_from_iface(subnet: str) -> Optional[str]:
    """Returns Ip address from a given subnet."""
    try:
        target_network = IPNetwork(subnet)
        networks = get_local_ipv4_networks()
        return next(
            (network.ip.format() for network in networks if network.ip in target_network), None
        )

    except AddrFormatError:
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
