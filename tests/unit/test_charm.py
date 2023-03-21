# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import Mock, call, patch

from ops import testing
from ops.model import ActiveStatus, MaintenanceStatus

from charm import SrsRANCharm

testing.SIMULATE_CAN_CONNECT = True


class TestCharm(unittest.TestCase):
    ATTACH_ACTION_PARAMS = {
        "usim-imsi": "whatever-imsi",
        "usim-opc": "whatever-opc",
        "usim-k": "whatever-k",
    }
    DETACH_ACTION_PARAMS = {"usim-imsi": None, "usim-opc": None, "usim-k": None}

    def setUp(self) -> None:
        self.harness = testing.Harness(SrsRANCharm)
        self.addCleanup(self.harness.cleanup)
        self.maxDiff = None
        self.harness.begin()

    def create_lte_core_relation(self) -> int:
        relation_name = "lte-core"
        remote_app_name = "magma-access-gateway-operator"
        mme_ipv4_address = "1.2.3.4"
        relation_data = {"mme_ipv4_address": mme_ipv4_address}
        relation_id = self.harness.add_relation(
            relation_name=relation_name, remote_app=remote_app_name
        )
        self.harness.update_relation_data(
            relation_id=relation_id,
            app_or_unit=remote_app_name,
            key_values=relation_data,
        )
        return relation_id

    @patch("charm.shell")
    def test_given_unit_is_leader_when_on_install_then_srsran_snap_is_installed(self, patch_shell):
        self.harness.set_leader(is_leader=True)

        self.harness.charm.on.install.emit()

        patch_shell.assert_called_with("snap install srsran --edge --devmode")

    @patch("charm.shell", new=Mock())
    def test_given_unit_is_leader_when_install_then_status_is_maintenance(self):
        self.harness.set_leader(True)

        self.harness.charm.on.install.emit()

        self.assertEqual(self.harness.model.unit.status, MaintenanceStatus("Installing srsRAN"))

    @patch("linux_service.Service.restart", new=Mock)
    @patch("linux_service.Service.enable", new=Mock)
    @patch("linux_service.Service.create")
    @patch("charm.ip_from_default_iface")
    def test_given_lte_core_relation_when_mme_address_is_available_then_srsenb_service_is_created(
        self, patch_ip_from_default_iface, patch_service_create
    ):
        bind_address = "1.1.1.1"
        patch_ip_from_default_iface.return_value = bind_address
        self.harness.set_leader(True)

        self.create_lte_core_relation()

        patch_service_create.assert_called_with(
            command=f"/snap/bin/srsran.srsenb --enb.mme_addr=1.2.3.4 --enb.gtp_bind_addr={bind_address} --enb.s1c_bind_addr={bind_address} --enb.name=dummyENB01 --enb.mcc=001 --enb.mnc=01 --enb_files.rr_config=/snap/srsran/current/config/rr.conf --enb_files.sib_config=/snap/srsran/current/config/sib.conf /snap/srsran/current/config/enb.conf --rf.device_name=zmq --rf.device_args=fail_on_disconnect=true,tx_port=tcp://*:2000,rx_port=tcp://localhost:2001,id=enb,base_srate=23.04e6",  # noqa: E501
            user="root",
            description="SRS eNodeB Emulator Service",
        )

    @patch("charm.ip_from_default_iface", new=Mock)
    @patch("linux_service.Service.restart")
    @patch("linux_service.Service.enable", new=Mock)
    @patch("linux_service.Service.create", new=Mock)
    def test_given_mme_address_is_available_when_on_config_changed_then_srsenb_service_is_restarted(  # noqa: E501
        self, patch_service_restart
    ):
        self.harness.set_leader(True)
        self.create_lte_core_relation()

        self.harness.update_config(key_values={})

        patch_service_restart.assert_called()

    @patch("shutil.rmtree")
    @patch("charm.shell")
    def test_given_srsenb_service_is_running_when_on_stop_then_service_is_stopped(
        self,
        patch_shell,
        _,
    ):
        self.harness.set_leader(True)

        self.harness.charm.on.stop.emit()

        patch_shell.assert_called_with("snap remove srsran --purge")

    @patch("charm.ip_from_default_iface", new=Mock)
    @patch("linux_service.Service.restart", new=Mock)
    @patch("linux_service.Service.enable", new=Mock)
    @patch("linux_service.Service.create", new=Mock)
    def test_given_any_config_and_installed_when_on_config_changed_then_status_is_active(  # noqa: E501
        self,
    ):
        self.harness.set_leader(True)
        self.create_lte_core_relation()

        self.harness.update_config(key_values={})

        self.assertEqual(self.harness.charm.unit.status, ActiveStatus("srsenb started"))

    @patch("charm.ip_from_default_iface", new=Mock)
    @patch("linux_service.Service.restart", new=Mock)
    @patch("linux_service.Service.enable", new=Mock)
    @patch("linux_service.Service.create", new=Mock)
    def test_given_any_config_and_not_installed_when_on_config_changed_then_status_is_active(  # noqa: E501
        self,
    ):
        self.harness.set_leader(True)
        self.create_lte_core_relation()

        self.harness.update_config(key_values={})

        self.assertEqual(self.harness.charm.unit.status, ActiveStatus("srsenb started"))

    @patch("charm.ip_from_default_iface", new=Mock)
    @patch("linux_service.Service.restart")
    @patch("linux_service.Service.enable", new=Mock)
    @patch("linux_service.Service.create", new=Mock)
    @patch("linux_service.Service.is_active", new=Mock)
    def test_given_any_config_and_started_is_true_when_on_config_changed_then_srsenb_service_is_restarted(  # noqa: E501
        self, patch_service_restart
    ):
        self.harness.set_leader(True)
        self.create_lte_core_relation()

        self.harness.update_config(key_values={})

        patch_service_restart.assert_called()

    @patch("charm.ip_from_default_iface", new=Mock)
    @patch("linux_service.Service.restart")
    def test_given_any_config_and_started_is_false_when_on_config_changed_then_srsenb_service_is_not_restarted(  # noqa: E501
        self, patch_service_restart
    ):
        self.create_lte_core_relation()

        self.harness.update_config(key_values={})

        patch_service_restart.assert_not_called()

    @patch("charm.ip_from_default_iface", new=Mock)
    @patch("charm.get_iface_ip_address", new=Mock)
    @patch("linux_service.Service.restart", new=Mock)
    @patch("linux_service.Service.enable", new=Mock)
    @patch("linux_service.Service.create")
    @patch("charm.wait_for_condition", new=Mock)
    @patch("linux_service.Service.is_active", side_effect=[True, False])
    def test_given_lte_core_relation_when_ue_attach_then_srsue_service_file_is_rendered(
        self,
        _,
        patch_service_create,
    ):
        self.harness.set_leader(True)

        self.create_lte_core_relation()

        mock_event = Mock()
        mock_event.params = self.ATTACH_ACTION_PARAMS
        self.harness.charm._on_attach_ue_action(event=mock_event)

        patch_service_create.assert_called_with(
            command="sudo /snap/bin/srsran.srsue --usim.imsi=whatever-imsi --usim.k=whatever-k --usim.opc=whatever-opc --usim.algo=milenage --nas.apn=default --rf.device_name=zmq --rf.device_args=tx_port=tcp://*:2001,rx_port=tcp://localhost:2000,id=ue,base_srate=23.04e6 /snap/srsran/current/config/ue.conf",  # noqa: E501
            user="ubuntu",
            description="SRS UE Emulator Service",
            exec_stop_post="service srsenb restart",
        )

    @patch("charm.ip_from_default_iface", new=Mock)
    @patch("charm.get_iface_ip_address")
    @patch("linux_service.Service.restart")
    @patch("linux_service.Service.enable", new=Mock)
    @patch("linux_service.Service.create", new=Mock)
    @patch("linux_service.Service.is_active", side_effect=[True, False])
    @patch("charm.wait_for_condition", new=Mock)
    def test_given_imsi_k_opc_when_attach_ue_action_then_srsue_service_is_restarted(  # noqa: E501
        self, _, patch_service_restart, patch_get_iface_ip_address
    ):
        self.harness.set_leader(True)
        mock_event = Mock()
        mock_event.params = self.ATTACH_ACTION_PARAMS
        self.create_lte_core_relation()
        dummy_tun_srsue_ipv4_address = "0.0.0.0"
        patch_get_iface_ip_address.return_value = dummy_tun_srsue_ipv4_address

        self.harness.charm._on_attach_ue_action(mock_event)

        patch_service_restart.assert_called()
        self.assertEqual(
            mock_event.set_results.call_args,
            call(
                {
                    "status": "UE attached successfully.",
                    "ue-ipv4-address": dummy_tun_srsue_ipv4_address,
                }
            ),
        )

    @patch("charm.ip_from_default_iface", new=Mock)
    @patch("linux_service.Service.restart", new=Mock)
    @patch("linux_service.Service.enable", new=Mock)
    @patch("linux_service.Service.create", new=Mock)
    @patch("linux_service.Service.is_active")
    @patch("charm.get_iface_ip_address")
    @patch("charm.wait_for_condition", new=Mock)
    def test_given_ue_running_when_attach_ue_action_then_event_fails(  # noqa: E501
        self, patch_get_iface_ip_address, patch_service_active
    ):
        self.harness.set_leader(True)
        mock_event = Mock()
        mock_event.params = self.ATTACH_ACTION_PARAMS
        self.create_lte_core_relation()
        dummy_ue_ipv4_address = None
        patch_get_iface_ip_address.return_value = dummy_ue_ipv4_address
        patch_service_active.return_value = True

        self.harness.charm._on_attach_ue_action(mock_event)

        self.assertEqual(
            mock_event.fail.call_args,
            call("Failed to attach. UE already running, please detach first."),
        )

    @patch("charm.ip_from_default_iface", new=Mock)
    @patch("linux_service.Service.restart", new=Mock)
    @patch("linux_service.Service.enable", new=Mock)
    @patch("linux_service.Service.create", new=Mock)
    @patch("charm.get_iface_ip_address")
    @patch("linux_service.Service.is_active", side_effect=[True, False])
    @patch("charm.wait_for_condition", new=Mock)
    def test_given_imsi_k_and_opc_when_attached_ue_action_then_srsue_service_sets_action_result(
        self, _, patch_get_iface_ip_address
    ):
        self.harness.set_leader(True)
        mock_event = Mock()
        mock_event.params = self.ATTACH_ACTION_PARAMS
        self.create_lte_core_relation()
        dummy_tun_srsue_ipv4_address = "0.0.0.0"
        patch_get_iface_ip_address.return_value = dummy_tun_srsue_ipv4_address

        self.harness.charm._on_attach_ue_action(mock_event)

        self.assertEqual(
            mock_event.set_results.call_args,
            call(
                {
                    "status": "UE attached successfully.",
                    "ue-ipv4-address": dummy_tun_srsue_ipv4_address,
                }
            ),
        )

    @patch("charm.ip_from_default_iface", new=Mock)
    @patch("linux_service.Service.restart", new=Mock)
    @patch("linux_service.Service.enable", new=Mock)
    @patch("linux_service.Service.create", new=Mock)
    @patch("charm.get_iface_ip_address")
    @patch("linux_service.Service.is_active", side_effect=[True, False])
    @patch("charm.wait_for_condition", new=Mock)
    def test_given_imsi_k_ops_and_mme_when_attached_ue_action_then_status_is_active(
        self, _, patch_get_iface_ip_address
    ):
        self.harness.set_leader(True)
        mock_event = Mock()
        mock_event.params = self.ATTACH_ACTION_PARAMS
        self.create_lte_core_relation()
        dummy_ue_ipv4_address = "192.168.128.13"
        patch_get_iface_ip_address.return_value = dummy_ue_ipv4_address

        self.harness.charm._on_attach_ue_action(mock_event)

        self.assertEqual(
            self.harness.charm.unit.status,
            ActiveStatus("ue attached."),
        )

    @patch("charm.ip_from_default_iface", new=Mock)
    @patch("linux_service.Service.restart", new=Mock)
    @patch("linux_service.Service.enable", new=Mock)
    @patch("linux_service.Service.create", new=Mock)
    @patch("charm.wait_for_condition")
    @patch("charm.shell", new=Mock())
    @patch("charm.get_iface_ip_address")
    @patch("linux_service.Service.is_active", side_effect=[True, False])
    def test_given_attach_ue_action_when_tun_srsue_ip_is_not_available_after_timeout_then_action_fails(  # noqa: E501
        self, _, patch_get_iface_ip_address, patch_wait_for_condition
    ):
        patch_wait_for_condition.return_value = False
        self.harness.set_leader(True)
        mock_event = Mock()
        mock_event.params = self.ATTACH_ACTION_PARAMS
        self.create_lte_core_relation()
        dummy_tun_srsue_ipv4_address = None
        patch_get_iface_ip_address.return_value = dummy_tun_srsue_ipv4_address

        self.harness.charm._on_attach_ue_action(mock_event)

        self.assertEqual(
            mock_event.fail.call_args,
            call("Failed to attach UE. Please, check if you have provided the right parameters."),
        )

    @patch("linux_service.Service.stop", new=Mock)
    @patch("linux_service.Service.delete", new=Mock)
    @patch("linux_service.Service.is_active")
    def test_given_detach_ue_action_when_action_is_successful_then_status_is_active(  # noqa: E501
        self, patch_service_active
    ):
        mock_event = Mock()
        mock_event.params = self.DETACH_ACTION_PARAMS
        patch_service_active.return_value = True

        self.harness.charm._on_detach_ue_action(mock_event)

        self.assertEqual(self.harness.charm.unit.status, ActiveStatus("ue detached"))

    @patch("linux_service.Service.delete", new=Mock)
    @patch("linux_service.Service.stop")
    def test_given_detach_ue_action_when_detach_ue_action_then_srsue_service_is_stopped(  # noqa: E501
        self,
        patch_service_stop,
    ):
        mock_event = Mock()
        mock_event.params = self.DETACH_ACTION_PARAMS

        self.harness.charm._on_detach_ue_action(mock_event)

        patch_service_stop.assert_called()

    @patch("linux_service.Service.delete", new=Mock)
    @patch("linux_service.Service.stop", new=Mock)
    def test_given_detach_ue_action_when_detach_ue_action_then_srsue_service_sets_action_result(  # noqa: E501
        self,
    ):
        mock_event = Mock()
        mock_event.params = self.DETACH_ACTION_PARAMS

        self.harness.charm._on_detach_ue_action(mock_event)

        self.assertEqual(
            mock_event.set_results.call_args,
            call({"status": "ok", "message": "Detached successfully"}),
        )

    @patch("charm.shell")
    def test_given_on_remove_default_gw_action_when_default_gw_action_then_removes_default_gw(  # noqa: E501
        self, patch_subprocess_run
    ):
        mock_event = Mock()

        self.harness.charm._on_remove_default_gw_action(mock_event)

        patch_subprocess_run.assert_any_call("route del default")

    @patch("charm.shell", new=Mock())
    def test_given_on_remove_default_gw_action_when_default_gw_action_then_sets_action_result(  # noqa: E501
        self,
    ):
        mock_event = Mock()

        self.harness.charm._on_remove_default_gw_action(mock_event)

        self.assertEqual(
            mock_event.set_results.call_args,
            call({"status": "ok", "message": "Default route removed!"}),
        )

    @patch("charm.shell", new=Mock())
    def test_given_on_remove_default_gw_action_when_remove_default_gw_action_then_status_does_not_change(  # noqa: E501
        self,
    ):
        mock_event = Mock()
        old_status = self.harness.charm.unit.status

        self.harness.charm._on_remove_default_gw_action(mock_event)

        self.assertEqual(self.harness.charm.unit.status, old_status)
