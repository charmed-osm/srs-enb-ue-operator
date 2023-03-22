# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Set of utilities related to managing Linux Network Interface."""

from typing import Optional

import netifaces  # type: ignore[import]


class Interface:
    """Class for representing a Linux Network Interface."""

    def __init__(self, name: Optional[str] = None):
        """Sets name attribute."""
        self.name = name if name else self._get_default_interface_name()

    def _get_interface(self) -> dict:
        return netifaces.ifaddresses(self.name)

    @staticmethod
    def _get_default_interface_name() -> str:
        default_gateway = netifaces.gateways()["default"]
        _, default_interface = default_gateway[netifaces.AF_INET]
        return default_interface

    def get_ip_address(self) -> Optional[str]:
        """Returns interface IP address."""
        return self._get_interface()[netifaces.AF_INET][0]["addr"]
