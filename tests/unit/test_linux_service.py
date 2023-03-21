# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.


import unittest
from subprocess import CalledProcessError
from unittest.mock import Mock, mock_open, patch

from linux_service import Service


class MockOpen:
    def __init__(self, read_data: str = ""):
        """Init."""
        self.read_data = read_data
        self.written_data = None

    def __enter__(self):
        """Enter."""
        return self

    def read(self) -> str:
        """Read."""
        return self.read_data

    def write(self, data: str):
        """Write."""
        self.written_data = data

    def __exit__(self, *args):
        """Exit."""
        pass


class TestService(unittest.TestCase):
    @patch("linux_service.shell")
    def test_given_service_when_enable_then_systemctl_enable_is_called(self, patch_shell):
        service_name = "banana"
        service = Service(name=service_name)

        service.enable()

        patch_shell.assert_called_with(f"systemctl enable {service_name}")

    @patch("linux_service.shell")
    def test_given_service_when_stop_then_systemctl_stop_is_called(self, patch_shell):
        service_name = "banana"
        service = Service(name=service_name)

        service.stop()

        patch_shell.assert_called_with(f"systemctl stop {service_name}")

    @patch("linux_service.shell")
    def test_given_service_when_restart_then_systemctl_stop_is_called(self, patch_shell):
        service_name = "banana"
        service = Service(name=service_name)

        service.restart()

        patch_shell.assert_called_with(f"systemctl restart {service_name}")

    @patch("linux_service.shell", new=Mock)
    def test_given_template_when_create_then_service_file_is_created(self):
        service_name = "banana"
        service = Service(name=service_name)
        service_command = "whatever command"
        service_user = "whatever_user"
        service_description = "whatever description"

        with open("templates/service.j2", "r") as f:
            service_template_content = f.read()

        with patch("builtins.open") as patch_open:
            mock_open_read_service_template = MockOpen(read_data=service_template_content)
            mock_open_write_service = MockOpen()
            patch_open.side_effect = [
                mock_open_read_service_template,
                mock_open_write_service,
            ]

            service.create(
                command=service_command, user=service_user, description=service_description
            )

        expected_service = (
            "[Unit]\n"
            f"Description={service_description}\n"
            "After=network.target\n"
            "StartLimitIntervalSec=0\n"
            "[Service]\n"
            "Type=simple\n"
            "Restart=always\n"
            "RestartSec=1\n"
            f"User={service_user}\n"
            f"ExecStart={service_command}\n"
            "KillSignal=SIGINT\n"
            "TimeoutStopSec=10\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target"
        )

        self.assertEqual(mock_open_write_service.written_data, expected_service)

    @patch("builtins.open", new_callable=mock_open)
    @patch("linux_service.shell")
    def test_given_service_when_create_then_systemctl_daemon_is_reloaded(self, patch_shell, _):
        service_name = "banana"
        service = Service(name=service_name)
        service_command = "whatever command"
        service_user = "whatever_user"
        service_description = "whatever description"

        service.create(command=service_command, user=service_user, description=service_description)

        patch_shell.assert_called_with("systemctl daemon-reload")

    @patch("linux_service.shell")
    def test_given_service_when_is_active_then_return_true(self, patch_shell):
        service_name = "banana"
        patch_shell.return_value = "active\n"
        service = Service(name=service_name)

        assert service.is_active()

    @patch("linux_service.shell")
    def test_given_service_when_is_not_active_then_return_false(self, patch_shell):
        service_name = "banana"
        patch_shell.return_value = "inactive\n"
        service = Service(name=service_name)

        assert not service.is_active()

    @patch("linux_service.shell")
    def test_given_calledprocesserror_when_is_not_active_then_return_false(self, patch_shell):
        service_name = "banana"
        patch_shell.side_effect = CalledProcessError(cmd="whatever", returncode=1)
        service = Service(name=service_name)

        assert not service.is_active()

    @patch("os.remove")
    def test_given_service_when_delete_then_service_file_is_removed(self, patch_os_remove):
        service_name = "banana"
        service = Service(name=service_name)

        service.delete()

        patch_os_remove.assert_called_with(f"/etc/systemd/system/{service_name}.service")
