# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Set of utilities related to managing Linux Network Interface."""

import logging
from typing import Optional

import netifaces  # type: ignore[import]

logger = logging.getLogger(__name__)


class Interface:
    """Class for representing a Linux Network Interface."""

    def __init__(self, name: Optional[str] = None):
        """Sets name attribute."""
        self.name = name if name else self._get_default_interface_name()

    def _get_interface(self) -> Optional[dict]:
        """Returns `netifaces.ifaddresses` dict representation object for a given interface."""
        try:
            return netifaces.ifaddresses(self.name)
        except ValueError:
            return None

    @staticmethod
    def _get_default_interface_name() -> str:
        """Returns default interface name based on default gateway."""
        default_gateway = netifaces.gateways()["default"]
        _, default_interface = default_gateway[netifaces.AF_INET]
        return default_interface

    def get_ip_address(self) -> Optional[str]:
        """Returns interface IP address."""
        interface = self._get_interface()
        if interface:
            return interface[netifaces.AF_INET][0]["addr"]
        else:
            return None
