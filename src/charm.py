#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for the SRS RAN simulator."""

import json
import logging
import os
import shutil
from typing import Optional

import netifaces  # type: ignore[import]
from charms.lte_core_interface.v0.lte_core_interface import (
    LTECoreAvailableEvent,
    LTECoreRequires,
)
from jinja2 import Template
from netifaces import AF_INET
from ops.charm import (
    ActionEvent,
    CharmBase,
    ConfigChangedEvent,
    InstallEvent,
    StartEvent,
    StopEvent,
    UpdateStatusEvent,
)
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus

from utils import (
    copy_files,
    get_iface_ip_address,
    git_clone,
    install_apt_packages,
    ip_from_default_iface,
    service_active,
    service_enable,
    service_restart,
    service_start,
    service_stop,
    shell,
    systemctl_daemon_reload,
)

logger = logging.getLogger(__name__)

APT_REQUIREMENTS = [
    "git",
    "libzmq3-dev",
    "cmake",
    "build-essential",
    "libmbedtls-dev",
    "libboost-program-options-dev",
    "libsctp-dev",
    "libconfig++-dev",
    "libfftw3-dev",
    "net-tools",
]

GIT_REPO = "https://github.com/srsLTE/srsLTE.git"
GIT_REPO_TAG = "release_20_10"

SRC_PATH = "/srsLTE"
BUILD_PATH = "/build"
CONFIG_PATH = "/config"
SERVICE_PATH = "/service"

CONFIG_PATHS = {
    "drb": f"{CONFIG_PATH}/drb.conf",
    "rr": f"{CONFIG_PATH}/rr.conf",
    "sib": f"{CONFIG_PATH}/sib.conf",
    "sib.mbsfn": f"{CONFIG_PATH}/sib.mbsfn.conf",
    "ue": f"{CONFIG_PATH}/ue.conf",
}

CONFIG_ORIGIN_PATHS = {
    "drb": f"{SRC_PATH}/srsenb/drb.conf.example",
    "rr": f"{SRC_PATH}/srsenb/rr.conf.example",
    "sib": f"{SRC_PATH}/srsenb/sib.conf.example",
    "sib.mbsfn": f"{SRC_PATH}/srsenb/sib.conf.mbsfn.example",
    "ue": f"{SRC_PATH}/srsue/ue.conf.example",
}

SRS_ENB_SERVICE = "srsenb"
SRS_ENB_BINARY = f"{BUILD_PATH}/srsenb/src/srsenb"
SRS_ENB_SERVICE_TEMPLATE = "./templates/srsenb.service"
SRS_ENB_SERVICE_PATH = "/etc/systemd/system/srsenb.service"

SRS_UE_SERVICE = "srsue"
SRS_UE_BINARY = f"{BUILD_PATH}/srsue/src/srsue"
SRS_UE_SERVICE_TEMPLATE = "./templates/srsue.service"
SRS_UE_SERVICE_PATH = "/etc/systemd/system/srsue.service"

SRS_ENB_UE_BUILD_COMMAND = f"cd {BUILD_PATH} && cmake {SRC_PATH} && make -j `nproc` srsenb srsue"


class SrsLteCharm(CharmBase):
    """srsRAN LTE charm."""

    def __init__(self, *args):
        """Observes various events."""
        super().__init__(*args)

        # Basic hooks
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.stop, self._on_stop)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.update_status, self._on_update_status)

        # Actions hooks
        self.framework.observe(self.on.attach_ue_action, self._on_attach_ue_action)
        self.framework.observe(self.on.detach_ue_action, self._on_detach_ue_action)
        self.framework.observe(self.on.remove_default_gw_action, self._on_remove_default_gw_action)

        self.lte_core_requirer = LTECoreRequires(self, "lte-core")
        self.framework.observe(
            self.lte_core_requirer.on.lte_core_available,
            self._on_lte_core_available,
        )

    def _on_install(self, _: InstallEvent) -> None:
        """Triggered on install event."""
        self.unit.status = MaintenanceStatus("Installing apt packages")
        install_apt_packages(APT_REQUIREMENTS)

        self.unit.status = MaintenanceStatus("Preparing the environment")
        self._reset_environment()

        self.unit.status = MaintenanceStatus("Downloading srsLTE from Github")
        git_clone(GIT_REPO, output_folder=SRC_PATH, branch=GIT_REPO_TAG, depth=1)

        self.unit.status = MaintenanceStatus("Building srsLTE")
        shell(SRS_ENB_UE_BUILD_COMMAND)

        self.unit.status = MaintenanceStatus("Copying example configuration files")
        copy_files(origin=CONFIG_ORIGIN_PATHS, destination=CONFIG_PATHS)

        self.unit.status = MaintenanceStatus("Configuring srs env service")
        self._configure_srsenb_service()

        service_enable(SRS_ENB_SERVICE)

    def _on_start(self, _: StartEvent) -> None:
        """Triggered on start event."""
        self.unit.status = MaintenanceStatus("Starting srsenb")
        service_start(SRS_ENB_SERVICE)
        self.unit.status = ActiveStatus("srsenb started.")

    def _on_stop(self, _: StopEvent) -> None:
        """Triggered on stop event."""
        self._reset_environment()
        service_stop(SRS_ENB_SERVICE)
        self.unit.status = BlockedStatus("Unit is down, service has stopped")

    def _on_config_changed(self, _: ConfigChangedEvent) -> None:
        """Triggered on config changed event."""
        self._configure_srsenb_service()
        if service_active(SRS_ENB_SERVICE):
            self.unit.status = MaintenanceStatus("Reloading srsenb")
            service_restart(SRS_ENB_SERVICE)
        self.unit.status = ActiveStatus(self._active_status_msg)

    def _on_update_status(self, _: UpdateStatusEvent) -> None:
        """Triggered on update status event."""
        self.unit.status = ActiveStatus(self._active_status_msg)

    def _on_lte_core_available(self, event: LTECoreAvailableEvent) -> None:
        """Triggered on lte_core_available.

        Retrieves MME address from relation, configures the srs enb service and restarts it.
        """
        if not self.unit.is_leader():
            return
        if not self.model.get_relation("replicas"):
            event.fail("Peer relation not created yet")  # type: ignore[attr-defined]
            return
        self.model.get_relation("replicas").data[self.app]["mme_ipv4_address"] = json.dumps(event.mme_ipv4_address)  # type: ignore[union-attr]  # noqa: E501
        logging.info(f"MME IPv4 address from LTE core: {event.mme_ipv4_address}")
        self._configure_srsenb_service()
        if service_active(SRS_ENB_SERVICE):
            self.unit.status = MaintenanceStatus("Reloading srsenb.")
            service_restart(SRS_ENB_SERVICE)
            logging.info(
                f"Restarting EnodeB after MME IP address change. MME address: {self._mme_addr}"
            )
        self.unit.status = ActiveStatus(self._active_status_msg)

    def _on_attach_ue_action(self, event: ActionEvent) -> None:
        """Triggered on attach_ue action."""
        if not service_active(SRS_ENB_SERVICE):
            event.fail("Failed to attach. The EnodeB is not running.")
            return
        if service_active(SRS_UE_SERVICE):
            event.fail("Failed to attach. UE already running, please detach first.")
            return
        self._configure_srsue_service(
            event.params["usim-imsi"],
            event.params["usim-k"],
            event.params["usim-opc"],
        )
        service_restart(SRS_UE_SERVICE)
        if ue_ip := get_iface_ip_address("tun_srsue"):
            event.set_results({"message": "Attached successfully.", "ue-ipv4": ue_ip})
            self.unit.status = ActiveStatus(self._active_status_msg)
        else:
            event.fail("Failed to attach. Make sure you have provided the right configuration.")

    def _on_detach_ue_action(self, event: ActionEvent) -> None:
        """Triggered on detach_ue action."""
        service_stop(SRS_UE_SERVICE)
        self._configure_srsue_service(None, None, None)  # type: ignore[arg-type]
        self.unit.status = ActiveStatus(self._active_status_msg)
        event.set_results({"status": "ok", "message": "Detached successfully"})

    def _on_remove_default_gw_action(self, event: ActionEvent) -> None:
        """Triggered on remove_default_gw action."""
        shell("route del default")
        event.set_results({"status": "ok", "message": "Default route removed!"})

    def _configure_srsenb_service(self) -> None:
        """Configures srs enb service."""
        self._configure_service(
            command=self._get_srsenb_command(),
            service_template=SRS_ENB_SERVICE_TEMPLATE,
            service_path=SRS_ENB_SERVICE_PATH,
        )

    def _configure_srsue_service(
        self, ue_usim_imsi: str, ue_usim_k: str, ue_usim_opc: str
    ) -> None:
        """Configures srs ue service."""
        self._configure_service(
            command=self._get_srsue_command(ue_usim_imsi, ue_usim_k, ue_usim_opc),
            service_template=SRS_UE_SERVICE_TEMPLATE,
            service_path=SRS_UE_SERVICE_PATH,
        )

    @staticmethod
    def _configure_service(
        command: str,
        service_template: str,
        service_path: str,
    ) -> None:
        """Renders service template and reload daemon service."""
        with open(service_template, "r") as template:
            service_content = Template(template.read()).render(command=command)
            with open(service_path, "w") as service:
                service.write(service_content)
            systemctl_daemon_reload()

    def _get_srsenb_command(self) -> str:
        """Returns srs enb command."""
        srsenb_command = [SRS_ENB_BINARY]
        if self._mme_addr:
            srsenb_command.append(f"--enb.mme_addr={self._mme_addr}")
        srsenb_command.extend(
            (
                f"--enb.gtp_bind_addr={self._bind_address}",
                f"--enb.s1c_bind_addr={self._bind_address}",
            )
        )
        srsenb_command.extend(
            (
                f'--enb.name={self.config.get("enb-name")}',
                f'--enb.mcc={self.config.get("enb-mcc")}',
                f'--enb.mnc={self.config.get("enb-mnc")}',
                f'--enb_files.rr_config={CONFIG_PATHS["rr"]}',
                f'--enb_files.sib_config={CONFIG_PATHS["sib"]}',
                f'--enb_files.drb_config={CONFIG_PATHS["drb"]}',
                f'--rf.device_name={self.config.get("enb-rf-device-name")}',
                f'--rf.device_args={self.config.get("enb-rf-device-args")}',
            )
        )
        return " ".join(srsenb_command)

    def _get_srsue_command(self, ue_usim_imsi: str, ue_usim_k: str, ue_usim_opc: str) -> str:
        """Returns srs ue command."""
        srsue_command = [SRS_UE_BINARY]
        if ue_usim_imsi:
            srsue_command.extend(
                (
                    f"--usim.imsi={ue_usim_imsi}",
                    f"--usim.k={ue_usim_k}",
                    f"--usim.opc={ue_usim_opc}",
                )
            )
        srsue_command.extend(
            (
                f'--usim.algo={self.config.get("ue-usim-algo")}',
                f'--nas.apn={self.config.get("ue-nas-apn")}',
                f'--rf.device_name={self.config.get("ue-device-name")}',
                f'--rf.device_args={self.config.get("ue-device-args")}',
                CONFIG_PATHS["ue"],
            )
        )
        return " ".join(srsue_command)

    @staticmethod
    def _reset_environment() -> None:
        """Resets environment.

        Remove old folders (if they exist) and create needed ones.
        """
        shutil.rmtree(SRC_PATH, ignore_errors=True)
        shutil.rmtree(BUILD_PATH, ignore_errors=True)
        shutil.rmtree(CONFIG_PATH, ignore_errors=True)
        shutil.rmtree(SERVICE_PATH, ignore_errors=True)
        os.mkdir(SRC_PATH)
        os.mkdir(BUILD_PATH)
        os.mkdir(CONFIG_PATH)
        os.mkdir(SERVICE_PATH)

    @property
    def _active_status_msg(self) -> str:
        """Returns msg of current status."""
        status_msg = ""
        if service_active(SRS_ENB_SERVICE):
            status_msg = "srsenb started. "
            if mme_addr := self._mme_addr:
                status_msg += f"mme: {mme_addr}. "
            if self._ue_attached and service_active(SRS_UE_SERVICE):
                status_msg += "ue attached. "
        return status_msg

    @property
    def _ue_attached(self) -> bool:
        if get_iface_ip_address("tun_srsue"):
            return True
        return False

    @property
    def _mme_addr(self) -> Optional[str]:
        """Returns the ipv4 address of the mme interface.

        Returns:
            str: mme_addr
        """
        if not self.model.get_relation("replicas"):
            return None
        data = self.model.get_relation("replicas").data[self.app].get("mme_ipv4_address", "")  # type: ignore[union-attr]  # noqa: E501
        return json.loads(data) if data else None

    @property
    def _bind_address(self) -> Optional[str]:
        """Returns bind address."""
        return (
            bind_address
            if (bind_address := self.model.config.get("bind-address"))
            else ip_from_default_iface()
        )


if __name__ == "__main__":
    main(SrsLteCharm)
