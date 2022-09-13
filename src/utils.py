# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Set of utils functions used in charm."""

import logging
import shutil
import subprocess
from typing import Dict, List, Optional, Union

import netifaces  # type: ignore[import]
from netaddr import IPAddress, IPNetwork  # type: ignore[import]
from netaddr.core import AddrFormatError  # type: ignore[import]

logger = logging.getLogger(__name__)


def service_active(service_name: str) -> bool:
    """Returns whether a given service is active."""
    response = shell(["systemctl", "is-active", service_name])
    return response == "active\n"


def update_apt_cache() -> None:
    """Updates apt cache."""
    logger.info("Updating apt cache...")
    shell(["apt", "-qq", "update"])


def install_apt_package(package_name: str) -> None:
    """Install apt package ca-certificates package."""
    shell(["apt", "install", package_name])
    logger.info(f"Install package {package_name}")


def git_clone(
    repo: str,
    output_folder: str = None,
    branch: str = None,
    depth: int = None,
) -> None:
    """Runs git clone of a given repo."""
    command = ["git", "clone"]
    if branch:
        command.append(f"--branch={branch}")
    if depth:
        command.append(f"--depth={depth}")
    command.append(repo)
    if output_folder:
        command.append(output_folder)
    shell(command)
    logger.info("Cloned git repository")


def shell(command: Union[str, List[str]]) -> str:
    """Runs a shell command."""
    response = subprocess.run(command, shell=True, stdout=subprocess.PIPE, encoding="utf-8")
    response.check_returncode()
    return response.stdout


def copy_files(origin: Dict[str, str], destination: Dict[str, str]) -> None:
    """Copy files from source to destination."""
    for config, origin_path in origin.items():
        destination_path = destination[config]
        shutil.copy(origin_path, destination_path)


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
    shell(["systemctl", action, service_name])


def service_start(service_name: str) -> None:
    """Starts a given service."""
    _systemctl("start", service_name)
    logger.info(f"Service {service_name} started")


def service_restart(service_name: str) -> None:
    """Restarts a given service."""
    _systemctl("restart", service_name)
    logger.info(f"Service {service_name} restarted")


def service_stop(service_name: str) -> None:
    """Stops a given service."""
    _systemctl("stop", service_name)
    logger.info(f"Service {service_name} stopped")


def service_enable(service_name: str) -> None:
    """Enables a given service."""
    _systemctl("enable", service_name)
    logger.info(f"Service {service_name} enabled")


def systemctl_daemon_reload() -> None:
    """Runs `systemctl daemon-reload`."""
    shell(["systemctl", "daemon-reload"])
    logger.info("Systemd manager configuration reloeaded")


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
        for network in networks:
            if network.ip in target_network:
                return network.ip.format()
        return None
    except AddrFormatError:
        return None
