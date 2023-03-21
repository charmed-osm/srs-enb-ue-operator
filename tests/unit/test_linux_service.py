# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.


from unittest.mock import patch

from linux_service import Service


class TestService:
    @patch("subprocess.run")
    def test_given_service_when_enable_then_systemctl_enable_is_called(self, patch_run):
        service_name = "banana"
        service = Service(name="banana")

        service.enable()

        patch_run.assert_called_with(
            f"systemctl enable {service_name}", shell=True, stdout=-1, encoding="utf-8"
        )
