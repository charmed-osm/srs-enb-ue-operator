#!/usr/bin/env python3
# Copyright 2020 David Garcia
# See LICENSE file for licensing details.

import logging
import os
import shutil

from ops.charm import CharmBase
from ops.main import main
from ops.framework import StoredState
from ops.model import MaintenanceStatus, ActiveStatus, BlockedStatus

from typing import Dict, Any

from utils import (
    service_active,
    service_start,
    service_stop,
    service_restart,
    service_enable,
    install_apt,
    git_clone,
    shell,
    copy_files,
    is_ipv4,
    ip_from_default_iface,
    ip_from_iface,
)

logger = logging.getLogger(__name__)

ENVIRONMENT_VARS = "/srsLTE.env"

SRS_ENB_SERVICE = "srsenb"
SRS_UE_SERVICE = "srsue"
GIT_REPO = "https://github.com/srsLTE/srsLTE.git"
SRC_PATH = "/srsLTE"
BUILD_PATH = "/build"


CONFIG_PATH = "/config"
SERVICE_PATH = "/service"

CONFIG_PATHS = {
    "enb": f"{CONFIG_PATH}/enb.conf",
    "drb": f"{CONFIG_PATH}/drb.conf",
    "rr": f"{CONFIG_PATH}/rr.conf",
    "sib": f"{CONFIG_PATH}/sib.conf",
    "sib.mbsfn": f"{CONFIG_PATH}/sib.mbsfn.conf",
    "ue": f"{CONFIG_PATH}/ue.conf",
}

CONFIG_ORIGIN_PATHS = {
    "enb": f"{SRC_PATH}/srsenb/enb.conf.example",
    "drb": f"{SRC_PATH}/srsenb/drb.conf.example",
    "rr": f"{SRC_PATH}/srsenb/rr.conf.example",
    "sib": f"{SRC_PATH}/srsenb/sib.conf.example",
    "sib.mbsfn": f"{SRC_PATH}/srsenb/sib.conf.mbsfn.example",
    "ue": f"{SRC_PATH}/srsue/ue.conf.example",
}

SERVICE_PATHS = {"srsenb": "/service/srsenb", "srsue": "/service/srsue"}
SERVICE_ORIGIN_PATHS = {"srsenb": "./files/srsenb", "srsue": "./files/srsue"}

SYSTEMD_PATHS = {
    "srsenb": "/etc/systemd/system/srsenb.service",
    "srsue": "/etc/systemd/system/srsue.service",
}
SYSTEMD_ORIGIN_PATHS = {
    "srsenb": "./files/srsenb.service",
    "srsue": "./files/srsue.service",
}

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

BUILD_COMMAND = f"cd {BUILD_PATH} && cmake {SRC_PATH} && make -j `nproc` srsenb srsue"


class SrsLteCharm(CharmBase):
    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        self._stored.set_default(
            mme_addr=None,
            bind_addr=None,
            ue_usim_imsi=None,
            ue_usim_k=None,
            ue_usim_opc=None,
            installed=False,
            started=False,
            ue_attached=False,
        )

        # Basic hooks
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.stop, self._on_stop)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.update_status, self._on_update_status)

        # Actions hooks
        self.framework.observe(self.on.attach_ue_action, self._on_attach_ue_action)
        self.framework.observe(self.on.detach_ue_action, self._on_detach_ue_action)
        self.framework.observe(
            self.on.remove_default_gw_action, self._on_remove_default_gw_action
        )

        # Relations hooks
        self.framework.observe(self.on.mme_relation_changed, self._mme_relation_changed)

    # Basic hooks
    def _on_install(self, _):
        self.unit.status = MaintenanceStatus("Installing apt packages")
        install_apt(packages=APT_REQUIREMENTS, update=True)

        self.unit.status = MaintenanceStatus("Preparing the environment")
        self._reset_environment()

        self.unit.status = MaintenanceStatus("Downloading srsLTE from Github")
        git_clone(GIT_REPO, output_folder=SRC_PATH, branch="release_20_10", depth=1)

        self.unit.status = MaintenanceStatus("Building srsLTE")
        shell(BUILD_COMMAND)

        self.unit.status = MaintenanceStatus("Generating configuration files")
        copy_files(origin=CONFIG_ORIGIN_PATHS, destination=CONFIG_PATHS)

        self.unit.status = MaintenanceStatus("Generating services files")
        copy_files(origin=SERVICE_ORIGIN_PATHS, destination=SERVICE_PATHS)

        self.unit.status = MaintenanceStatus("Generating systemd files")
        copy_files(origin=SYSTEMD_ORIGIN_PATHS, destination=SYSTEMD_PATHS)

        service_enable(SRS_ENB_SERVICE)
        self._stored.installed = True

    def _on_start(self, _):
        self.unit.status = MaintenanceStatus("Starting srsenb")
        service_start(SRS_ENB_SERVICE)
        self._stored.started = True
        self.unit.status = self._get_current_status()

    def _on_stop(self, _):
        self._reset_environment()
        service_stop(SRS_ENB_SERVICE)
        self._stored.started = False
        self.unit.status = self._get_current_status()

    def _on_config_changed(self, _):
        self._stored.bind_addr = self._get_bind_address()
        if service_active(SRS_ENB_SERVICE):
            self.unit.status = MaintenanceStatus("Reloading srsenb")
        _environment_vars = self.environment_vars
        # TODO: Validate the ENV variables
        self._populate_environment_vars(_environment_vars)
        # Restart the service only if it is running
        if service_active(SRS_ENB_SERVICE):
            service_restart(SRS_ENB_SERVICE)
        self.unit.status = self._get_current_status()

    def _on_update_status(self, _):
        self.unit.status = self._get_current_status()

    # Action hooks
    def _on_attach_ue_action(self, event):
        self._stored.ue_usim_imsi = event.params["usim-imsi"]
        self._stored.ue_usim_k = event.params["usim-k"]
        self._stored.ue_usim_opc = event.params["usim-opc"]
        _environment_vars = self.environment_vars
        # TODO: Validate the ENV variables
        self._populate_environment_vars(_environment_vars)
        service_restart(SRS_UE_SERVICE)
        self._stored.ue_attached = True
        self.unit.status = self._get_current_status()
        event.set_results({"status": "ok", "message": "Attached successfully"})

    def _on_detach_ue_action(self, event):
        self._stored.ue_usim_imsi = None
        self._stored.ue_usim_k = None
        self._stored.ue_usim_opc = None
        service_stop(SRS_UE_SERVICE)
        self._stored.ue_attached = False
        self.unit.status = self._get_current_status()
        event.set_results({"status": "ok", "message": "Detached successfully"})

    def _on_remove_default_gw_action(self, event):
        shell("sudo route del default")
        event.set_results({"status": "ok", "message": "Default route removed!"})

    # Relation hooks
    def _mme_relation_changed(self, event):
        # Get mme address from relation
        if event.unit in event.relation.data:
            mme_addr = event.relation.data[event.unit].get("mme-addr")
            if not is_ipv4(mme_addr):
                return
            self._stored.mme_addr = mme_addr
            _environment_vars = self.environment_vars
            # TODO: Validate the ENV variables
            self._populate_environment_vars(_environment_vars)
            # Restart the service only if it is running
            if service_active(SRS_ENB_SERVICE):
                self.unit.status = MaintenanceStatus("Reloading srsenb")
                service_restart(SRS_ENB_SERVICE)
        self.unit.status = self._get_current_status()

    # Properties
    @property
    def relation_state(self) -> Dict[str, Any]:
        """Collects relation state configuration for pod spec assembly.

        Returns:
            Dict[str, Any]: relation state information.
        """
        relation_state = {
            "mme-addr": self._stored.mme_addr,
        }

        return relation_state

    @property
    def environment_vars(self) -> Dict[str, str]:
        mme_addr_opt = ""
        gtp_bind_addr_opt = ""
        s1c_bind_addr_opt = ""
        usim_opts = ""

        if self.relation_state["mme-addr"]:
            mme_addr_opt += f'--enb.mme_addr={self.relation_state["mme-addr"]}'

        if self._stored.bind_addr:
            gtp_bind_addr_opt += f"--enb.gtp_bind_addr={self._stored.bind_addr}"
            s1c_bind_addr_opt += f"--enb.s1c_bind_addr={self._stored.bind_addr}"

        if self._stored.ue_usim_imsi:
            usim_opts += "'"
            usim_opts += f"--usim.imsi={self._stored.ue_usim_imsi} "
            usim_opts += f"--usim.k={self._stored.ue_usim_k} "
            usim_opts += f"--usim.opc={self._stored.ue_usim_opc} "
            usim_opts += "'"

        return {
            "SRS_ENB_BINARY": f"{BUILD_PATH}/srsenb/src/srsenb",
            "SRS_ENB_NAME": "dummyENB01",
            "SRS_ENB_MCC": "901",
            "SRS_ENB_MNC": "70",
            "SRS_ENB_MME_ADDR_OPT": mme_addr_opt,
            "SRS_ENB_GTP_BIND_ADDR_OPT": gtp_bind_addr_opt,
            "SRS_ENB_S1C_BIND_ADDR_OPT": s1c_bind_addr_opt,
            "SRS_ENB_RR_CONFIG": CONFIG_PATHS["rr"],
            "SRS_ENB_SIB_CONFIG": CONFIG_PATHS["sib"],
            "SRS_ENB_DRB_CONFIG": CONFIG_PATHS["drb"],
            "SRS_ENB_CONFIG": CONFIG_PATHS["enb"],
            "SRS_ENB_DEVICE_NAME": "zmq",
            "SRS_ENB_DEVICE_ARGS": "fail_on_disconnect=true,tx_port=tcp://*:2000,rx_port=tcp://localhost:2001,id=enb,base_srate=23.04e6",
            "SRS_UE_BINARY": f"{BUILD_PATH}/srsue/src/srsue",
            "SRS_UE_USIM_OPTS": usim_opts,
            "SRS_UE_USIM_ALGO": "milenage",
            "SRS_UE_NAS_APN": "oai.ipv4",
            "SRS_UE_DEVICE_NAME": "zmq",
            "SRS_UE_DEVICE_ARGS": "tx_port=tcp://*:2001,rx_port=tcp://localhost:2000,id=ue,base_srate=23.04e6",
            "SRS_UE_CONFIG": CONFIG_PATHS["ue"],
        }

    # Private functions
    def _reset_environment(self):
        # Remove old folders (if they exist)
        shutil.rmtree(SRC_PATH, ignore_errors=True)
        shutil.rmtree(BUILD_PATH, ignore_errors=True)
        shutil.rmtree(CONFIG_PATH, ignore_errors=True)
        shutil.rmtree(SERVICE_PATH, ignore_errors=True)
        # Create needed folders
        os.mkdir(SRC_PATH)
        os.mkdir(BUILD_PATH)
        os.mkdir(CONFIG_PATH)
        os.mkdir(SERVICE_PATH)

    def _populate_environment_vars(self, environment_vars: Dict[str, str]):
        srsenb_env_content = ""
        for key, value in environment_vars.items():
            srsenb_env_content += f"{key}={value}\n"
        with open(ENVIRONMENT_VARS, "w") as f:
            f.write(srsenb_env_content)

    def _get_bind_address(self):
        bind_addr = None
        bind_address_subnet = self.model.config.get("bind-address-subnet")
        if bind_address_subnet:
            bind_addr = ip_from_iface(bind_address_subnet)
        else:
            bind_addr = ip_from_default_iface()
        return bind_addr

    def _get_current_status(self):
        status_type = ActiveStatus
        status_msg = ""
        if self._stored.installed:
            status_msg = "SW installed."
        if self._stored.started and service_active(SRS_ENB_SERVICE):
            status_msg = "srsenb started. "
            if mme_addr := self._stored.mme_addr:
                status_msg += f"mme: {mme_addr}. "
            if ue_attached := self._stored.ue_attached and service_active(SRS_UE_SERVICE):
                status_msg += f"ue attached. "
        return status_type(status_msg)


if __name__ == "__main__":
    main(SrsLteCharm)
