# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import Mock, call, mock_open, patch

from ops import testing
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus

from charm import SrsRANCharm

testing.SIMULATE_CAN_CONNECT = True


class MockOpen:
    def __init__(self, read_data: str = ""):
        """Init."""
        self.read_data = read_data
        self.written_data = None

    def __enter__(self):
        """Enter."""
        return self

    def read(self):
        """Read."""
        return self.read_data

    def write(self, data: str):
        """Write."""
        self.written_data = data

    def __exit__(self, *args):
        """Exit."""
        pass


class TestCharm(unittest.TestCase):
    SRC_PATH = "/srsLTE"
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

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.mkdir", new=Mock())
    @patch("shutil.copy", new=Mock())
    @patch("shutil.rmtree", new=Mock())
    @patch("subprocess.run")
    def test_given_unit_is_leader_when_install_then_apt_cache_is_updated(
        self,
        patch_subprocess_run,
        _,
    ):
        self.harness.set_leader(True)

        self.harness.charm.on.install.emit()

        patch_subprocess_run.assert_any_call(
            "sudo apt -qq update", shell=True, stdout=-1, encoding="utf-8"
        )

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.mkdir", new=Mock())
    @patch("shutil.copy", new=Mock())
    @patch("shutil.rmtree", new=Mock())
    @patch("subprocess.run")
    def test_given_unit_is_leader_when_install_then_apt_packages_are_installed(
        self,
        patch_subprocess_run,
        _,
    ):
        self.harness.set_leader(True)

        self.harness.charm.on.install.emit()

        patch_subprocess_run.assert_any_call(
            "sudo apt -y install git libzmq3-dev cmake build-essential libmbedtls-dev libboost-program-options-dev libsctp-dev libconfig++-dev libfftw3-dev net-tools",  # noqa: E501
            shell=True,
            stdout=-1,
            encoding="utf-8",
        )

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.mkdir")
    @patch("shutil.copy", new=Mock())
    @patch("shutil.rmtree")
    @patch("subprocess.run", new=Mock())
    def test_given_unit_is_leader_when_install_then_srs_directories_are_removed_and_recreated(
        self, patch_rmtree, patch_mkdir, _
    ):
        self.harness.set_leader(True)
        build_path = "/build"
        config_path = "/config"
        service_path = "/service"

        self.harness.charm.on.install.emit()

        rmtree_calls = [
            call(self.SRC_PATH, ignore_errors=True),
            call(build_path, ignore_errors=True),
            call(config_path, ignore_errors=True),
            call(service_path, ignore_errors=True),
        ]
        mkdir_calls = [
            call(self.SRC_PATH),
            call(build_path),
            call(config_path),
            call(service_path),
        ]
        patch_rmtree.assert_has_calls(calls=rmtree_calls)
        patch_mkdir.assert_has_calls(calls=mkdir_calls)


    @patch("builtins.open", new_callable=mock_open)
    @patch("os.mkdir", new=Mock())
    @patch("shutil.copy", new=Mock())
    @patch("shutil.rmtree", new=Mock())
    @patch("subprocess.run")
    def test_given_unit_is_leader_when_install_then_srsran_is_installed(
        self,
        patch_subprocess_run,
        _,
    ):
        self.harness.set_leader(True)

        self.harness.charm.on.install.emit()

        patch_subprocess_run.assert_any_call(
            "cd /build && cmake /srsLTE && make -j `nproc` srsenb srsue",
            shell=True,
            stdout=-1,
            encoding="utf-8",
        )  # TODO Change test to validate install

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.mkdir", new=Mock())
    @patch("shutil.copy")
    @patch("shutil.rmtree", new=Mock())
    @patch("subprocess.run", new=Mock())
    def test_given_unit_is_leader_when_install_then_files_are_copied(
        self,
        patch_copy,
        _,
    ):
        self.harness.set_leader(True)

        self.harness.charm.on.install.emit()

        calls = [
            call("/srsLTE/srsenb/drb.conf.example", "/config/drb.conf"),
            call("/srsLTE/srsenb/rr.conf.example", "/config/rr.conf"),
            call("/srsLTE/srsenb/sib.conf.example", "/config/sib.conf"),
            call("/srsLTE/srsenb/sib.conf.mbsfn.example", "/config/sib.mbsfn.conf"),
            call("/srsLTE/srsue/ue.conf.example", "/config/ue.conf"),
        ]
        patch_copy.assert_has_calls(calls=calls)

    @patch("charm.ip_from_default_iface")
    @patch("charm.wait_for_condition", new=Mock())
    @patch("charm.service_active", side_effect=[True, False])
    @patch("subprocess.run", new=Mock())
    def test_given_lte_core_relation_when_mme_address_is_available_then_srsenb_service_file_is_rendered(  # noqa: E501
        self,
        _,
        patch_ip_from_default_iface,
    ):
        bind_address = "1.1.1.1"
        patch_ip_from_default_iface.return_value = bind_address
        self.harness.set_leader(True)

        with open("templates/srsue.service", "r") as f:
            srsue_service_content = f.read()

        with patch("builtins.open") as patch_open:
            mock_open_read_srsue_template = MockOpen(read_data=srsue_service_content)
            mock_open_write_srsue_service = MockOpen()
            patch_open.side_effect = [
                mock_open_read_srsue_template,
                mock_open_write_srsue_service,
            ]
            self.create_lte_core_relation()

        srsue_expected_service = (
            "[Unit]\n"
            "Description=Srs User Emulator Service\n"
            "After=network.target\n"
            "StartLimitIntervalSec=0\n"
            "[Service]\n"
            "Type=simple\n"
            "Restart=always\n"
            "RestartSec=1\n"
            f"ExecStart=/build/srsenb/src/srsenb --enb.mme_addr=1.2.3.4 --enb.gtp_bind_addr={bind_address} --enb.s1c_bind_addr={bind_address} --enb.name=dummyENB01 --enb.mcc=001 --enb.mnc=01 --enb_files.rr_config=/config/rr.conf --enb_files.sib_config=/config/sib.conf --enb_files.drb_config=/config/drb.conf /config/enb.conf --rf.device_name=zmq --rf.device_args=fail_on_disconnect=true,tx_port=tcp://*:2000,rx_port=tcp://localhost:2001,id=enb,base_srate=23.04e6\n"  # noqa: E501, W505
            "User=root\n"
            "KillSignal=SIGINT\n"
            "TimeoutStopSec=10\n"
            "ExecStopPost=service srsenb restart\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target"
        )

        self.assertEqual(mock_open_write_srsue_service.written_data, srsue_expected_service)

    @patch("charm.wait_for_condition", new=Mock())
    @patch("charm.service_active", side_effect=[True, False])
    @patch("subprocess.run", new=Mock())
    def test_given_lte_core_relation_when_ue_attach_then_srsue_service_file_is_rendered(
        self,
        _,
    ):
        self.harness.set_leader(True)

        with open("templates/srsue.service", "r") as f:
            srsue_service_content = f.read()

        with patch("builtins.open") as patch_open:
            patch_open.side_effect = [MockOpen(), MockOpen()]
            self.create_lte_core_relation()

        with patch("builtins.open") as patch_open:
            mock_open_read_srsue_template = MockOpen(read_data=srsue_service_content)
            mock_open_write_srsue_service = MockOpen()
            patch_open.side_effect = [
                mock_open_read_srsue_template,
                mock_open_write_srsue_service,
            ]
            mock_event = Mock()
            mock_event.params = self.ATTACH_ACTION_PARAMS
            self.harness.charm._on_attach_ue_action(event=mock_event)

        srsue_expected_service = (
            "[Unit]\n"
            "Description=Srs User Emulator Service\n"
            "After=network.target\n"
            "StartLimitIntervalSec=0\n"
            "[Service]\n"
            "Type=simple\n"
            "Restart=always\n"
            "RestartSec=1\n"
            "ExecStart=/build/srsue/src/srsue --usim.imsi=whatever-imsi --usim.k=whatever-k --usim.opc=whatever-opc --usim.algo=milenage --nas.apn=oai.ipv4 --rf.device_name=zmq --rf.device_args=tx_port=tcp://*:2001,rx_port=tcp://localhost:2000,id=ue,base_srate=23.04e6 /config/ue.conf\n"  # noqa: E501, W505
            "User=root\n"
            "KillSignal=SIGINT\n"
            "TimeoutStopSec=10\n"
            "ExecStopPost=service srsenb restart\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target"
        )

        self.assertEqual(mock_open_write_srsue_service.written_data, srsue_expected_service)

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.mkdir", new=Mock())
    @patch("shutil.copy", new=Mock())
    @patch("shutil.rmtree", new=Mock())
    @patch("subprocess.run", new=Mock())
    def test_given_unit_is_leader_when_install_then_status_is_maintenance(
        self,
        _,
    ):
        self.harness.set_leader(True)

        self.harness.charm.on.install.emit()

        self.assertEqual(self.harness.model.unit.status, MaintenanceStatus("Installing srsRAN"))

    @patch("subprocess.run")
    @patch("builtins.open", new_callable=mock_open)
    def test_given_mme_address_is_available_when_on_config_changed_then_srsenb_service_is_restarted(  # noqa: E501
        self,
        _,
        patch_run,
    ):
        self.harness.set_leader(True)
        self.create_lte_core_relation()

        self.harness.update_config(key_values={})

        patch_run.assert_any_call(
            "systemctl restart srsenb", shell=True, stdout=-1, encoding="utf-8"
        )

    @patch("shutil.rmtree")
    @patch("os.mkdir")
    @patch("subprocess.run")
    def test_given_srsenb_service_is_running_when_on_stop_then_service_is_stopped(
        self, patch_run, _, __
    ):
        self.harness.set_leader(True)

        self.harness.charm.on.stop.emit()

        patch_run.assert_any_call("systemctl stop srsenb", shell=True, stdout=-1, encoding="utf-8")

    @patch("shutil.rmtree")
    @patch("os.mkdir")
    @patch("subprocess.run")
    def test_given_srsenb_service_is_running_when_on_stop_then_folders_content_is_removed(
        self, _, patch_mkdir, patch_rmtree
    ):
        self.harness.set_leader(True)

        self.harness.charm.on.stop.emit()

        patch_rmtree.assert_has_calls(
            calls=[
                call("/srsLTE", ignore_errors=True),
                call("/build", ignore_errors=True),
                call("/config", ignore_errors=True),
                call("/service", ignore_errors=True),
            ]
        )
        patch_mkdir.assert_has_calls(
            calls=[
                call("/srsLTE"),
                call("/build"),
                call("/config"),
                call("/service"),
            ]
        )

    @patch("shutil.rmtree")
    @patch("os.mkdir")
    @patch("subprocess.run")
    def test_given_on_stop_when_on_stop_then_status_is_active(self, _, __, ___):
        self.harness.set_leader(True)

        self.harness.charm.on.stop.emit()

        self.assertEqual(
            self.harness.charm.unit.status, BlockedStatus("Unit is down, service has stopped")
        )

    @patch("subprocess.run")
    @patch("builtins.open", new_callable=mock_open)
    def test_given_any_config_when_on_config_changed_then_systemd_manager_configuration_is_reloaded(  # noqa: E501
        self, _, patch_run
    ):
        self.harness.set_leader(True)
        self.create_lte_core_relation()

        self.harness.update_config(key_values={})

        patch_run.assert_any_call(
            "systemctl daemon-reload", shell=True, stdout=-1, encoding="utf-8"
        )

    @patch("subprocess.run", new=Mock())
    @patch("builtins.open", new_callable=mock_open)
    def test_given_any_config_and_installed_when_on_config_changed_then_status_is_active(  # noqa: E501
        self,
        _,
    ):
        self.harness.set_leader(True)
        self.create_lte_core_relation()

        self.harness.update_config(key_values={})

        self.assertEqual(self.harness.charm.unit.status, ActiveStatus("srsenb started"))

    @patch("subprocess.run", new=Mock())
    @patch("builtins.open", new_callable=mock_open)
    def test_given_any_config_and_not_installed_when_on_config_changed_then_status_is_active(  # noqa: E501
        self,
        _,
    ):
        self.harness.set_leader(True)
        self.create_lte_core_relation()

        self.harness.update_config(key_values={})

        self.assertEqual(self.harness.charm.unit.status, ActiveStatus("srsenb started"))

    @patch("subprocess.run")
    @patch("builtins.open", new_callable=mock_open)
    @patch("charm.service_active", new=Mock())
    def test_given_any_config_and_started_is_true_when_on_config_changed_then_srsenb_service_is_restarted(  # noqa: E501
        self, _, patch_subprocess_run
    ):
        self.harness.set_leader(True)
        self.create_lte_core_relation()

        self.harness.update_config(key_values={})

        patch_subprocess_run.assert_any_call(
            "systemctl restart srsenb", shell=True, stdout=-1, encoding="utf-8"
        )

    @patch("utils.service_restart")
    @patch("subprocess.run", new=Mock())
    @patch("builtins.open", new_callable=mock_open)
    def test_given_any_config_and_started_is_false_when_on_config_changed_then_srsenb_service_is_not_restarted(  # noqa: E501
        self, _, patch_service_restart
    ):
        self.create_lte_core_relation()

        self.harness.update_config(key_values={})

        patch_service_restart.assert_not_called()

    @patch("charm.get_iface_ip_address")
    @patch("charm.service_active", side_effect=[True, False])
    @patch("builtins.open", new_callable=mock_open)
    @patch("subprocess.run")
    def test_given_imsi_k_opc_when_attach_ue_action_then_srsue_service_is_restarted(  # noqa: E501
        self, patch_subprocess_run, _, __, patch_get_iface_ip_address
    ):
        self.harness.set_leader(True)
        mock_event = Mock()
        mock_event.params = self.ATTACH_ACTION_PARAMS
        self.create_lte_core_relation()
        dummy_tun_srsue_ipv4_address = "0.0.0.0"
        patch_get_iface_ip_address.return_value = dummy_tun_srsue_ipv4_address

        self.harness.charm._on_attach_ue_action(mock_event)

        patch_subprocess_run.assert_any_call(
            "systemctl restart srsue", shell=True, stdout=-1, encoding="utf-8"
        )
        self.assertEqual(
            mock_event.set_results.call_args,
            call(
                {
                    "status": "UE attached successfully.",
                    "ue-ipv4-address": dummy_tun_srsue_ipv4_address,
                }
            ),
        )

    @patch("charm.service_active")
    @patch("charm.get_iface_ip_address")
    @patch("builtins.open", new_callable=mock_open)
    @patch("subprocess.run", new=Mock())
    def test_given_ue_running_when_attach_ue_action_then_event_fails(  # noqa: E501
        self, __, patch_get_iface_ip_address, patch_service_active
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

    @patch("charm.get_iface_ip_address")
    @patch("charm.service_active", side_effect=[True, False])
    @patch("builtins.open", new_callable=mock_open)
    @patch("subprocess.run", new=Mock())
    def test_given_imsi_k_and_opc_when_attached_ue_action_then_srsue_service_sets_action_result(
        self, _, __, patch_get_iface_ip_address
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

    @patch("subprocess.run", new=Mock())
    @patch("charm.get_iface_ip_address")
    @patch("charm.service_active", side_effect=[True, False])
    @patch("builtins.open", new_callable=mock_open)
    def test_given_imsi_k_ops_and_mme_when_attached_ue_action_then_status_is_active(
        self, _, __, patch_get_iface_ip_address
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

    @patch("charm.wait_for_condition")
    @patch("subprocess.run", new=Mock())
    @patch("charm.get_iface_ip_address")
    @patch("charm.service_active", side_effect=[True, False])
    @patch("builtins.open", new_callable=mock_open)
    def test_given_attach_ue_action_when_tun_srsue_ip_is_not_available_after_timeout_then_action_fails(  # noqa: E501
        self, _, __, patch_get_iface_ip_address, patch_wait_for_condition
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

    @patch("utils.service_active")
    @patch("builtins.open", new_callable=mock_open)
    @patch("subprocess.run", new=Mock())
    def test_given_detach_ue_action_when_action_is_successful_then_status_is_active(  # noqa: E501
        self, _, patch_service_active
    ):
        mock_event = Mock()
        mock_event.params = self.DETACH_ACTION_PARAMS
        patch_service_active.return_value = True

        self.harness.charm._on_detach_ue_action(mock_event)

        self.assertEqual(self.harness.charm.unit.status, ActiveStatus("ue detached"))

    @patch("builtins.open", new_callable=mock_open)
    @patch("subprocess.run")
    def test_given_detach_ue_action_when_detach_ue_action_then_srsue_service_is_stopped(  # noqa: E501
        self, patch_subprocess_run, _
    ):
        mock_event = Mock()
        mock_event.params = self.DETACH_ACTION_PARAMS

        self.harness.charm._on_detach_ue_action(mock_event)

        patch_subprocess_run.assert_any_call(
            "systemctl stop srsue", shell=True, stdout=-1, encoding="utf-8"
        )

    @patch("builtins.open", new_callable=mock_open)
    @patch("subprocess.run", new=Mock())
    def test_given_detach_ue_action_when_detach_ue_action_then_srsue_service_sets_action_result(  # noqa: E501
        self,
        _,
    ):
        mock_event = Mock()
        mock_event.params = self.DETACH_ACTION_PARAMS

        self.harness.charm._on_detach_ue_action(mock_event)

        self.assertEqual(
            mock_event.set_results.call_args,
            call({"status": "ok", "message": "Detached successfully"}),
        )

    @patch("subprocess.run")
    def test_given_on_remove_default_gw_action_when_default_gw_action_then_removes_default_gw(  # noqa: E501
        self, patch_subprocess_run
    ):
        mock_event = Mock()

        self.harness.charm._on_remove_default_gw_action(mock_event)

        patch_subprocess_run.assert_any_call(
            "route del default", shell=True, stdout=-1, encoding="utf-8"
        )

    @patch("subprocess.run", new=Mock())
    def test_given_on_remove_default_gw_action_when_default_gw_action_then_sets_action_result(  # noqa: E501
        self,
    ):
        mock_event = Mock()

        self.harness.charm._on_remove_default_gw_action(mock_event)

        self.assertEqual(
            mock_event.set_results.call_args,
            call({"status": "ok", "message": "Default route removed!"}),
        )

    @patch("subprocess.run", new=Mock())
    def test_given_on_remove_default_gw_action_when_remove_default_gw_action_then_status_does_not_change(  # noqa: E501
        self,
    ):
        mock_event = Mock()
        old_status = self.harness.charm.unit.status

        self.harness.charm._on_remove_default_gw_action(mock_event)

        self.assertEqual(self.harness.charm.unit.status, old_status)
