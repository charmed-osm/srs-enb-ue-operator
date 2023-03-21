# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import patch

import netifaces  # type: ignore[import]

from utils import get_iface_ip_address, ip_from_default_iface, shell


class TestUtils(unittest.TestCase):
    @patch("subprocess.run")
    def test_given_command_when_shell_then_subprocess_run(self, patch_run):
        command = "whatever command"

        shell(command=command)

        patch_run.assert_called_with(command, shell=True, stdout=-1, encoding="utf-8")

    @patch("netifaces.ifaddresses")
    @patch("netifaces.gateways")
    def test_given_default_interface_has_ip_when_ip_from_default_iface_then_ip_is_returned(
        self, patch_gateways, patch_addresses
    ):
        default_gateway = "192.168.2.1"
        ip_address = "192.168.2.122"
        interface_name = "eth0"
        patch_gateways.return_value = {
            "default": {netifaces.AF_INET: (default_gateway, interface_name)}
        }
        patch_addresses.return_value = {netifaces.AF_INET: [{"addr": ip_address}]}

        assert ip_from_default_iface() == ip_address

    @patch("netifaces.ifaddresses")
    @patch("netifaces.gateways")
    def test_given_no_default_gateway_ip_when_ip_from_default_iface_then_none_is_returned(  # noqa: E501
        self, patch_gateways, patch_addresses
    ):
        patch_gateways.return_value = {"default": {}}
        patch_addresses.return_value = {}

        assert not ip_from_default_iface()

    @patch("netifaces.ifaddresses")
    @patch("netifaces.gateways")
    def test_given_default_interface_does_not_have_an_ip_when_ip_from_default_iface_then_none_is_returned(  # noqa: E501
        self, patch_gateways, patch_addresses
    ):
        default_gateway = "192.168.2.1"
        interface_name = "eth0"
        patch_gateways.return_value = {
            "default": {netifaces.AF_INET: (default_gateway, interface_name)}
        }
        patch_addresses.return_value = {}

        assert not ip_from_default_iface()

    @patch("netifaces.ifaddresses")
    def test_given_interface_has_ip_address_when_get_iface_ip_address_then_ip_is_returned(
        self, patch_addresses
    ):
        interface = "eth0"
        ip_address = "1.2.3.4"
        patch_addresses.return_value = {netifaces.AF_INET: [{"addr": ip_address}]}

        assert get_iface_ip_address(interface) == ip_address

    @patch("netifaces.ifaddresses")
    def test_given_interface_does_not_exist_when_get_iface_ip_address_then_none_is_returned(
        self, patch_addresses
    ):
        interface = "eth0"
        patch_addresses.side_effect = ValueError()

        assert not get_iface_ip_address(interface)
