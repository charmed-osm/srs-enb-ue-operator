# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Set of utils functions used in charm."""

import shutil
import subprocess
from typing import Dict, List, Optional

import apt  # type: ignore[import]
import netifaces  # type: ignore[import]
from netaddr import IPAddress, IPNetwork  # type: ignore[import]
from netaddr.core import AddrFormatError  # type: ignore[import]


def service_active(service_name: str) -> bool:
    """Returns whether a given service is active."""
    result = subprocess.run(
        ["systemctl", "is-active", service_name],
        stdout=subprocess.PIPE,
        encoding="utf-8",
    )
    return result.stdout == "active\n"


def all_values_set(dictionary: Dict[str, str]) -> bool:
    """Returns whether all values in a dict are set."""
    return not any(v is None for v in dictionary.values())


def install_apt(packages: List[str], update: bool = False) -> None:
    """Installs a given list of packages."""
    cache = apt.cache.Cache()
    if update:
        cache.update()
    cache.open()
    for package in packages:
        pkg = cache[package]
        if not pkg.is_installed:
            pkg.mark_install()
    cache.commit()


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
    subprocess.run(command).check_returncode()


def shell(command: str) -> None:
    """Runs a shell command."""
    subprocess.run(command, shell=True).check_returncode()


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


# Service functions
def _systemctl(action: str, service_name: str) -> None:
    subprocess.run(["systemctl", action, service_name]).check_returncode()


def service_start(service_name: str) -> None:
    """Starts a given service."""
    _systemctl("start", service_name)


def service_restart(service_name: str) -> None:
    """Restarts a given service."""
    _systemctl("restart", service_name)


def service_stop(service_name: str) -> None:
    """Stops a given service."""
    _systemctl("stop", service_name)


def service_enable(service_name: str) -> None:
    """Enables a given service."""
    _systemctl("enable", service_name)


def systemctl_daemon_reload() -> None:
    """Runs `systemctl daemon-reload`."""
    subprocess.run(["systemctl", "daemon-reload"]).check_returncode()


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
