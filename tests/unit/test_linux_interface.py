# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.


import unittest
from unittest.mock import patch

import netifaces

from linux_interface import Interface


class TestLinuxInterface(unittest.TestCase):
    @patch("netifaces.ifaddresses")
    @patch("netifaces.gateways")
    def test_given_no_name_when_ip_address_then_default_interface_ip_address_is_returned(
        self, patch_gateways, patch_addresses
    ):
        default_gateway = "192.168.2.1"
        ip_address = "192.168.2.122"
        interface_name = "eth0"
        patch_gateways.return_value = {
            "default": {netifaces.AF_INET: (default_gateway, interface_name)}
        }
        patch_addresses.return_value = {netifaces.AF_INET: [{"addr": ip_address}]}

        interface = Interface()

        assert interface.get_ip_address() == ip_address

    @patch("netifaces.ifaddresses")
    def test_given_name_when_ip_address_then_interface_ip_address_is_returned(
        self, patch_addresses
    ):
        ip_address = "1.2.3.4"
        interface_name = "eth1"
        patch_addresses.return_value = {netifaces.AF_INET: [{"addr": ip_address}]}

        interface = Interface(name=interface_name)

        assert interface.get_ip_address() == ip_address

    @patch("netifaces.ifaddresses")
    def test_given_interface_doesnt_exist_when_ip_address_then_none_is_returned(
        self, patch_addresses
    ):
        interface_name = "eth1"
        patch_addresses.side_effect = ValueError

        interface = Interface(name=interface_name)

        assert not interface.get_ip_address()
