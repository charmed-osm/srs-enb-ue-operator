# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Set of utilities related to managing Linux services."""

import logging
import os
from subprocess import CalledProcessError
from typing import Optional

from jinja2 import Template

from utils import shell

SERVICE_TEMPLATE = "./templates/service.j2"

logger = logging.getLogger(__name__)


class Service:
    """Class for representing a Linux Service."""

    def __init__(self, name: str):
        """Sets service name."""
        self.name = name

    def is_active(self) -> bool:
        """Returns whether service is active."""
        try:
            response = shell(f"systemctl is-active {self.name}")
            return response == "active\n"
        except CalledProcessError:
            return False

    def create(
        self, command: str, user: str, description: str, exec_stop_post: Optional[str] = None
    ) -> None:
        """Creates a linux service."""
        with open(SERVICE_TEMPLATE, "r") as template:
            service_content = Template(template.read()).render(
                command=command, user=user, description=description, exec_stop_post=exec_stop_post
            )
        with open(f"/etc/systemd/system/{self.name}.service", "w") as service:
            service.write(service_content)
        self._systemctl_daemon_reload()

    def delete(self) -> None:
        """Deletes a linux service."""
        os.remove(f"/etc/systemd/system/{self.name}.service")

    def restart(self) -> None:
        """Restarts a linux service."""
        self._systemctl("restart", self.name)
        logger.info("Service %s restarted", self.name)

    def stop(self) -> None:
        """Stops a linux service."""
        self._systemctl("stop", self.name)
        logger.info("Service %s stopped", self.name)

    def enable(self) -> None:
        """Enables a linux service."""
        self._systemctl("enable", self.name)
        logger.info("Service %s enabled", self.name)

    def _systemctl(self, action: str, service_name: str) -> None:
        shell(f"systemctl {action} {service_name}")

    def _systemctl_daemon_reload(self) -> None:
        """Runs `systemctl daemon-reload`."""
        shell("systemctl daemon-reload")
        logger.info("Systemd manager configuration reloaded")
