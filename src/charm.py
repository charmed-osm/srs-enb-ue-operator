#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for the srsRAN simulator."""

import logging
from typing import Optional, Union

from charms.lte_core_interface.v0.lte_core_interface import (
    LTECoreAvailableEvent,
    LTECoreRequires,
)
from jinja2 import Template
from ops.charm import (
    ActionEvent,
    CharmBase,
    ConfigChangedEvent,
    InstallEvent,
    RemoveEvent,
)
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus

from utils import (
    get_iface_ip_address,
    ip_from_default_iface,
    service_active,
    service_enable,
    service_restart,
    service_stop,
    shell,
    systemctl_daemon_reload,
    wait_for_condition,
)

logger = logging.getLogger(__name__)
#
#
# CONFIG_PATHS = {
#     "enb": f"{CONFIG_PATH}/enb.conf",
#     "drb": f"{CONFIG_PATH}/drb.conf",
#     "rr": f"{CONFIG_PATH}/rr.conf",
#     "sib": f"{CONFIG_PATH}/sib.conf",
#     "sib.mbsfn": f"{CONFIG_PATH}/sib.mbsfn.conf",
#     "ue": f"{CONFIG_PATH}/ue.conf",
# }
#
# CONFIG_ORIGIN_PATHS = {
#     "enb": f"{SRC_PATH}/srsenb/enb.conf.example",
#     "drb": f"{SRC_PATH}/srsenb/drb.conf.example",
#     "rr": f"{SRC_PATH}/srsenb/rr.conf.example",
#     "sib": f"{SRC_PATH}/srsenb/sib.conf.example",
#     "sib.mbsfn": f"{SRC_PATH}/srsenb/sib.conf.mbsfn.example",
#     "ue": f"{SRC_PATH}/srsue/ue.conf.example",
# }

SRS_ENB_SERVICE = "srsenb"
SRS_ENB_BINARY = f"{BUILD_PATH}/srsenb/src/srsenb"
SRS_ENB_SERVICE_TEMPLATE = "./templates/srsenb.service"
SRS_ENB_SERVICE_PATH = "/etc/systemd/system/srsenb.service"

SRS_UE_SERVICE = "srsue"
SRS_UE_BINARY = f"{BUILD_PATH}/srsue/src/srsue"
SRS_UE_SERVICE_TEMPLATE = "./templates/srsue.service"
SRS_UE_SERVICE_PATH = "/etc/systemd/system/srsue.service"

WAIT_FOR_UE_IP_TIMEOUT = 10


class SrsRANCharm(CharmBase):
    """srsRAN charm."""

    def __init__(self, *args):
        """Observes various events."""
        super().__init__(*args)

        # Basic hooks
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.remove, self._on_remove)
        self.framework.observe(self.on.config_changed, self._on_config_changed)

        # Actions hooks
        self.framework.observe(self.on.attach_ue_action, self._on_attach_ue_action)
        self.framework.observe(self.on.detach_ue_action, self._on_detach_ue_action)
        self.framework.observe(self.on.remove_default_gw_action, self._on_remove_default_gw_action)

        self.lte_core_requirer = LTECoreRequires(self, "lte-core")
        self.framework.observe(
            self.lte_core_requirer.on.lte_core_available,
            self._on_config_changed,
        )

    def _on_install(self, _: InstallEvent) -> None:
        """Triggered on install event."""
        if not self.unit.is_leader():
            return
        self.unit.status = MaintenanceStatus("Installing srsRAN")
        self._install_srsran()

    def _on_remove(self, _: RemoveEvent) -> None:
        """Triggered on stop event."""
        if not self.unit.is_leader():
            return
        self._uninstall_srsran()

    def _on_config_changed(self, _: Union[ConfigChangedEvent, LTECoreAvailableEvent]) -> None:
        """Triggered on config changed event."""
        if not self.unit.is_leader():
            return
        if not self._lte_core_relation_is_created:
            self.unit.status = BlockedStatus("Waiting for LTE Core relation to be created")
            return
        if not self._lte_core_mme_address_is_available:
            self.unit.status = WaitingStatus("Waiting for MME address to be available")
            return
        self.unit.status = MaintenanceStatus("Configuring srsenb")
        self._configure_srsenb_service()
        service_enable(SRS_ENB_SERVICE)
        service_restart(SRS_ENB_SERVICE)
        self.unit.status = ActiveStatus("srsenb started")

    def _on_attach_ue_action(self, event: ActionEvent) -> None:
        """Triggered on attach_ue action."""
        if not self.unit.is_leader():
            event.fail("Only leader can attach UE")
            return
        if not self._lte_core_relation_is_created:
            event.fail("LTE Core relation is not created")
            return
        if not self._lte_core_mme_address_is_available:
            event.fail("MME address is not available")
            return
        if not service_active(SRS_ENB_SERVICE):
            event.fail("Failed to attach. The EnodeB is not running.")
            return
        if service_active(SRS_UE_SERVICE):
            event.fail("Failed to attach. UE already running, please detach first.")
            return
        self._configure_srsue_service(
            ue_usim_imsi=event.params["usim-imsi"],
            ue_usim_k=event.params["usim-k"],
            ue_usim_opc=event.params["usim-opc"],
        )
        service_restart(SRS_UE_SERVICE)
        if not wait_for_condition(
            lambda: get_iface_ip_address("tun_srsue"), timeout=WAIT_FOR_UE_IP_TIMEOUT
        ):
            event.fail(
                "Failed to attach UE. Please, check if you have provided the right parameters."
            )
            return
        event.set_results(
            {
                "status": "UE attached successfully.",
                "ue-ipv4-address": get_iface_ip_address("tun_srsue"),
            }
        )
        self.unit.status = ActiveStatus("ue attached.")

    def _on_detach_ue_action(self, event: ActionEvent) -> None:
        """Triggered on detach_ue action."""
        service_stop(SRS_UE_SERVICE)
        self._configure_srsue_service(None, None, None)  # type: ignore[arg-type]
        self.unit.status = ActiveStatus("ue detached")
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

    @staticmethod
    def _install_srsran() -> None:
        """Installs srsRAN snap."""
        shell("snap install srsran --edge --devmode")
        logger.info("Installed srsRAN snap")

    @staticmethod
    def _uninstall_srsran() -> None:
        """Removes srsRAN snap."""
        shell("snap remove srsran --purge")
        logger.info("Removed srsRAN snap")

    def _configure_srsue_service(
        self, ue_usim_imsi: str, ue_usim_k: str, ue_usim_opc: str
    ) -> None:
        """Configures srs ue service."""
        self._configure_service(
            command=self._get_srsue_command(ue_usim_imsi, ue_usim_k, ue_usim_opc),
            service_template=SRS_UE_SERVICE_TEMPLATE,
            service_path=SRS_UE_SERVICE_PATH,
        )

    @property
    def _lte_core_relation_is_created(self) -> bool:
        """Checks if the relation with the LTE core is created."""
        return self._relation_is_created("lte-core")

    def _relation_is_created(self, relation_name: str) -> bool:
        """Checks if the relation with the given name is created."""
        try:
            if self.model.get_relation(relation_name):
                return True
            return False
        except KeyError:
            return False

    @property
    def _lte_core_mme_address_is_available(self) -> bool:
        """Checks if the MME address is available."""
        return self._mme_address is not None

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
        srsenb_command.extend(
            (
                f"--enb.mme_addr={self._mme_address}",
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
                CONFIG_PATHS["enb"],
                f'--rf.device_name={self.config.get("enb-rf-device-name")}',
                f'--rf.device_args={self.config.get("enb-rf-device-args")}',
            )
        )
        return " ".join(srsenb_command)

    def _get_srsue_command(self, ue_usim_imsi: str, ue_usim_k: str, ue_usim_opc: str) -> str:
        """Returns srs ue command."""
        srsue_command = [SRS_UE_BINARY]
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

    @property
    def _mme_address(self) -> Optional[str]:
        """Returns the ipv4 address of the mme interface.

        Returns:
            str: MME Address
        """
        if not self.unit.is_leader():
            return None
        mme_relation = self.model.get_relation(relation_name="lte-core")
        if not mme_relation:
            return None
        if not mme_relation.app:
            return None
        return mme_relation.data[mme_relation.app].get("mme_ipv4_address")

    @property
    def _bind_address(self) -> Optional[str]:
        """Returns bind address."""
        return (
            bind_address
            if (bind_address := self.model.config.get("bind-address"))
            else ip_from_default_iface()
        )


if __name__ == "__main__":
    main(SrsRANCharm)
