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
from ops.charm import (
    ActionEvent,
    CharmBase,
    ConfigChangedEvent,
    InstallEvent,
    StopEvent,
)
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus

from linux_service import Service
from utils import get_iface_ip_address, ip_from_default_iface, shell, wait_for_condition

logger = logging.getLogger(__name__)

CONFIG_PATH = "/snap/srsran/current/config"
WAIT_FOR_UE_IP_TIMEOUT = 20


class SrsRANCharm(CharmBase):
    """srsRAN charm."""

    def __init__(self, *args):
        """Observes various events."""
        super().__init__(*args)
        self.ue_service = Service("srsue")
        self.enb_service = Service("srsenb")

        # Basic hooks
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.stop, self._on_stop)
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

    def _on_stop(self, _: StopEvent) -> None:
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
        self.enb_service.create(
            command=self._get_srsenb_command(),
            user="root",
            description="SRS eNodeB Emulator Service",
        )
        self.enb_service.enable()
        self.enb_service.restart()
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
        if not self.enb_service.is_active():
            event.fail("Failed to attach. The EnodeB is not running.")
            return
        if self.ue_service.is_active():
            event.fail("Failed to attach. UE already running, please detach first.")
            return
        self.ue_service.create(
            command=self._get_srsue_command(
                ue_usim_imsi=event.params["usim-imsi"],
                ue_usim_k=event.params["usim-k"],
                ue_usim_opc=event.params["usim-opc"],
            ),
            user="ubuntu",
            description="SRS UE Emulator Service",
            exec_stop_post="service srsenb restart",
        )
        self.ue_service.restart()
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
        self.ue_service.stop()
        self.ue_service.delete()
        self.unit.status = ActiveStatus("ue detached")
        event.set_results({"status": "ok", "message": "Detached successfully"})

    def _on_remove_default_gw_action(self, event: ActionEvent) -> None:
        """Triggered on remove_default_gw action."""
        shell("route del default")
        event.set_results({"status": "ok", "message": "Default route removed!"})

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

    def _get_srsenb_command(self) -> str:
        """Returns srs enb command."""
        srsenb_command = ["/snap/bin/srsran.srsenb"]
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
                f"--enb_files.rr_config={CONFIG_PATH}/rr.conf",
                f"--enb_files.sib_config={CONFIG_PATH}/sib.conf",
                f"{CONFIG_PATH}/enb.conf",
                f'--rf.device_name={self.config.get("enb-rf-device-name")}',
                f'--rf.device_args={self.config.get("enb-rf-device-args")}',
            )
        )
        return " ".join(srsenb_command)

    def _get_srsue_command(self, ue_usim_imsi: str, ue_usim_k: str, ue_usim_opc: str) -> str:
        """Returns srs ue command."""
        srsue_command = ["sudo", "/snap/bin/srsran.srsue"]
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
                f"{CONFIG_PATH}/ue.conf",
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
        bind_interface = self.model.config.get("bind-interface")
        if not bind_interface:
            return ip_from_default_iface()
        else:
            return get_iface_ip_address(iface=bind_interface)


if __name__ == "__main__":
    main(SrsRANCharm)
