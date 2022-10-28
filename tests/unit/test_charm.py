# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import Mock, call, mock_open, patch

from ops import testing
from ops.model import ActiveStatus, MaintenanceStatus

from charm import SrsLteCharm

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
        "usim-imsi": "whatever imsi",
        "usim-opc": "whatever opc",
        "usim-k": "whatever k",
    }
    DETACH_ACTION_PARAMS = {"usim-imsi": None, "usim-opc": None, "usim-k": None}

    def setUp(self) -> None:
        self.remote_app_name = "magma-access-gateway-operator"
        self.relation_name = "lte-core"
        self.harness = testing.Harness(SrsLteCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.mkdir")
    @patch("shutil.copy")
    @patch("shutil.rmtree")
    @patch("subprocess.run")
    def test_given_list_of_packages_to_install_when_install_then_apt_cache_is_updated(
        self, patch_subprocess_run, _, __, ___, ____
    ):
        self.harness.charm.on.install.emit()

        patch_subprocess_run.assert_any_call(
            "sudo apt -qq update", shell=True, stdout=-1, encoding="utf-8"
        )

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.mkdir")
    @patch("shutil.copy")
    @patch("shutil.rmtree")
    @patch("subprocess.run")
    def test_given_list_of_packages_to_install_when_install_then_apt_packages_are_installed(
        self, patch_subprocess_run, _, __, ___, ____
    ):
        self.harness.charm.on.install.emit()

        patch_subprocess_run.assert_any_call(
            "sudo apt -y install git libzmq3-dev cmake build-essential libmbedtls-dev libboost-program-options-dev libsctp-dev libconfig++-dev libfftw3-dev net-tools",  # noqa: E501
            shell=True,
            stdout=-1,
            encoding="utf-8",
        )

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.mkdir")
    @patch("shutil.copy")
    @patch("shutil.rmtree")
    @patch("subprocess.run")
    def test_given_install_event_when_install_then_srs_directories_are_removed_and_recreated(
        self, _, patch_rmtree, __, patch_mkdir, ___
    ):
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
    @patch("os.mkdir")
    @patch("shutil.copy")
    @patch("shutil.rmtree")
    @patch("subprocess.run")
    def test_given_install_event_when_install_then_srsran_repo_is_cloned(
        self, patch_subprocess_run, _, __, ___, ____
    ):
        self.harness.charm.on.install.emit()

        patch_subprocess_run.assert_any_call(
            "git clone --branch=release_20_10 --depth=1 https://github.com/srsLTE/srsLTE.git /srsLTE",  # noqa: E501
            shell=True,
            stdout=-1,
            encoding="utf-8",
        )

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.mkdir")
    @patch("shutil.copy")
    @patch("shutil.rmtree")
    @patch("subprocess.run")
    def test_given_install_event_when_install_then_srsran_is_built(
        self, patch_subprocess_run, _, __, ___, ____
    ):
        self.harness.charm.on.install.emit()

        patch_subprocess_run.assert_any_call(
            "cd /build && cmake /srsLTE && make -j `nproc` srsenb srsue",
            shell=True,
            stdout=-1,
            encoding="utf-8",
        )

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.mkdir")
    @patch("shutil.copy")
    @patch("shutil.rmtree")
    @patch("subprocess.run")
    def test_given_install_event_when_install_then_files_are_copied(
        self, _, __, patch_copy, ___, ____
    ):
        self.harness.charm.on.install.emit()

        calls = [
            call("/srsLTE/srsenb/enb.conf.example", "/config/enb.conf"),
            call("/srsLTE/srsenb/drb.conf.example", "/config/drb.conf"),
            call("/srsLTE/srsenb/rr.conf.example", "/config/rr.conf"),
            call("/srsLTE/srsenb/sib.conf.example", "/config/sib.conf"),
            call("/srsLTE/srsenb/sib.conf.mbsfn.example", "/config/sib.mbsfn.conf"),
            call("/srsLTE/srsue/ue.conf.example", "/config/ue.conf"),
        ]
        patch_copy.assert_has_calls(calls=calls)

    @patch("os.mkdir")
    @patch("shutil.copy")
    @patch("shutil.rmtree")
    @patch("subprocess.run")
    def test_given_service_template_when_install_then_srsenb_service_file_is_rendered(
        self, _, __, ___, ____
    ):

        with open("templates/srsenb.service", "r") as f:
            srsenb_service_content = f.read()
        with open("templates/srsue.service", "r") as f:
            srsue_service_content = f.read()

        with patch("builtins.open") as mock_open:
            mock_open_read_srsenb_template = MockOpen(read_data=srsenb_service_content)
            mock_open_write_srsenb_service = MockOpen()
            mock_open_read_srsue_template = MockOpen(read_data=srsue_service_content)
            mock_open_write_srsue_service = MockOpen()
            mock_open.side_effect = [
                mock_open_read_srsenb_template,
                mock_open_write_srsenb_service,
                mock_open_read_srsue_template,
                mock_open_write_srsue_service,
            ]
            self.harness.charm.on.install.emit()

        srsenb_expected_service = (
            "[Unit]\n"
            "Description=Srs EnodeB Service\n"
            "After=network.target\n"
            "StartLimitIntervalSec=0\n"
            "[Service]\n"
            "Type=simple\n"
            "Restart=always\n"
            "RestartSec=1\n"
            "User=root\n"
            "ExecStart=/build/srsenb/src/srsenb --enb.name=dummyENB01 --enb.mcc=901 --enb.mnc=70 --enb_files.rr_config=/config/rr.conf --enb_files.sib_config=/config/sib.conf --enb_files.drb_config=/config/drb.conf /config/enb.conf --rf.device_name=zmq --rf.device_args=fail_on_disconnect=true,tx_port=tcp://*:2000,rx_port=tcp://localhost:2001,id=enb,base_srate=23.04e6\n\n"  # noqa: E501, W505
            "[Install]\n"
            "WantedBy=multi-user.target"
        )
        srsue_expected_service = (
            "[Unit]\n"
            "Description=Srs User Emulator Service\n"
            "After=network.target\n"
            "StartLimitIntervalSec=0\n"
            "[Service]\n"
            "Type=simple\n"
            "Restart=always\n"
            "RestartSec=1\n"
            "ExecStart=/build/srsue/src/srsue --usim.algo=milenage --nas.apn=oai.ipv4 --rf.device_name=zmq --rf.device_args=tx_port=tcp://*:2001,rx_port=tcp://localhost:2000,id=ue,base_srate=23.04e6 /config/ue.conf\n"  # noqa: E501, W505
            "User=root\n"
            "KillSignal=SIGINT\n"
            "TimeoutStopSec=10\n"
            "ExecStopPost=service srsenb restart\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target"
        )

        self.assertEqual(mock_open_write_srsenb_service.written_data, srsenb_expected_service)
        self.assertEqual(mock_open_write_srsue_service.written_data, srsue_expected_service)

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.mkdir")
    @patch("shutil.copy")
    @patch("shutil.rmtree")
    @patch("subprocess.run")
    def test_given_install_event_when_install_then_status_is_maintenance(
        self, _, __, patch_copy, ___, ____
    ):
        self.harness.charm.on.install.emit()

        self.assertEqual(
            self.harness.model.unit.status, MaintenanceStatus("Generating systemd files")
        )

    @patch("subprocess.run")
    def test_given_service_not_yet_started_when_on_start_then_srsenb_service_is_started(  # noqa: E501
        self, patch_run
    ):
        self.harness.charm.on.start.emit()

        patch_run.assert_any_call(
            "systemctl start srsenb", shell=True, stdout=-1, encoding="utf-8"
        )

    @patch("charm.service_active")
    @patch("subprocess.run")
    def test_given_service_started_when_on_start_then_srsenb_status_is_active(
        self, _, patch_service_active
    ):
        self.harness.charm.on.start.emit()

        self.assertEqual(self.harness.charm.unit.status, ActiveStatus("srsenb started. "))

    @patch("shutil.rmtree")
    @patch("os.mkdir")
    @patch("subprocess.run")
    def test_given_srsenb_service_is_running_when_on_stop_then_service_is_stopped(
        self, patch_run, _, __
    ):
        self.harness.charm.on.stop.emit()

        patch_run.assert_any_call("systemctl stop srsenb", shell=True, stdout=-1, encoding="utf-8")

    @patch("shutil.rmtree")
    @patch("os.mkdir")
    @patch("subprocess.run")
    def test_given_srsenb_service_is_running_when_on_stop_then_folders_content_is_removed(
        self, _, patch_mkdir, patch_rmtree
    ):
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
        self.harness.charm._stored.installed = True
        self.harness.charm.on.stop.emit()

        self.assertEqual(self.harness.charm.unit.status, ActiveStatus("SW installed."))

    @patch("subprocess.run")
    @patch("builtins.open", new_callable=mock_open)
    def test_given_any_config_when_on_config_changed_then_systemd_manager_configuration_is_reloaded(  # noqa: E501
        self, _, patch_run
    ):
        key_values = {}
        self.harness.update_config(key_values=key_values)

        patch_run.assert_any_call(
            "systemctl daemon-reload", shell=True, stdout=-1, encoding="utf-8"
        )

    @patch("subprocess.run")
    @patch("builtins.open", new_callable=mock_open)
    def test_given_any_config_and_installed_when_on_config_changed_then_status_is_active(  # noqa: E501
        self, _, __
    ):
        key_values = {}
        self.harness.charm._stored.installed = True

        self.harness.update_config(key_values=key_values)

        self.assertEqual(self.harness.charm.unit.status, ActiveStatus("SW installed."))

    @patch("subprocess.run")
    @patch("builtins.open", new_callable=mock_open)
    def test_given_any_config_and_not_installed_when_on_config_changed_then_status_is_active(  # noqa: E501
        self, _, __
    ):
        key_values = {}

        self.harness.update_config(key_values=key_values)

        self.assertEqual(self.harness.charm.unit.status, ActiveStatus(""))

    @patch("subprocess.run")
    @patch("builtins.open", new_callable=mock_open)
    def test_given_any_config_and_started_is_true_when_on_config_changed_then_srsenb_service_is_restarted(  # noqa: E501
        self, _, patch_subprocess_run
    ):
        key_values = {}
        self.harness.charm._stored.started = True

        self.harness.update_config(key_values=key_values)

        patch_subprocess_run.assert_any_call(
            "systemctl restart srsenb", shell=True, stdout=-1, encoding="utf-8"
        )

    @patch("utils.service_restart")
    @patch("subprocess.run")
    @patch("builtins.open", new_callable=mock_open)
    def test_given_any_config_and_started_is_false_when_on_config_changed_then_srsenb_service_is_not_restarted(  # noqa: E501
        self, _, __, patch_service_restart
    ):
        key_values = {}

        self.harness.update_config(key_values=key_values)

        patch_service_restart.assert_not_called()

    @patch("charm.service_active", side_effect=[True, False])
    @patch("charm.get_iface_ip_address")
    @patch("builtins.open", new_callable=mock_open)
    @patch("subprocess.run")
    def test_given_imsi_k_opc_and_tun_srsue_interface_configured_when_attach_ue_action_then_srsue_service_is_restarted(  # noqa: E501
        self, patch_subprocess_run, _, patch_get_iface_ip_address, __
    ):
        mock_event = Mock()
        mock_event.params = self.ATTACH_ACTION_PARAMS
        dummy_ue_ipv4_address = "192.168.128.13"
        patch_get_iface_ip_address.return_value = dummy_ue_ipv4_address

        self.harness.charm._on_attach_ue_action(mock_event)

        patch_subprocess_run.assert_any_call(
            "systemctl restart srsue", shell=True, stdout=-1, encoding="utf-8"
        )
        self.assertEqual(
            mock_event.set_results.call_args,
            call(
                {
                    "message": "Attached successfully.",
                    "ue-ipv4": dummy_ue_ipv4_address,
                }
            ),
        )

    @patch("charm.service_active", side_effect=[True, False])
    @patch("charm.get_iface_ip_address")
    @patch("builtins.open", new_callable=mock_open)
    @patch("subprocess.run")
    def test_given_imsi_k_opc_and_tun_srsue_interface_not_configured_when_attach_ue_action_then_srsue_service_sets_no_ip_found_action_result(  # noqa: E501
        self, patch_subprocess_run, _, patch_get_iface_ip_address, __
    ):
        mock_event = Mock()
        mock_event.params = self.ATTACH_ACTION_PARAMS
        dummy_ue_ipv4_address = None
        patch_get_iface_ip_address.return_value = dummy_ue_ipv4_address

        self.harness.charm._on_attach_ue_action(mock_event)

        patch_subprocess_run.assert_any_call(
            "systemctl restart srsue", shell=True, stdout=-1, encoding="utf-8"
        )
        self.assertEqual(
            mock_event.fail.call_args,
            call("Failed to attach. Make sure you have provided the right configuration."),
        )

    @patch("charm.service_active")
    @patch("charm.get_iface_ip_address")
    @patch("builtins.open", new_callable=mock_open)
    @patch("subprocess.run")
    def test_given_ue_running_when_attach_ue_action_then_event_fails(  # noqa: E501
        self, patch_subprocess_run, _, patch_get_iface_ip_address, patch_service_active
    ):
        mock_event = Mock()
        mock_event.params = self.ATTACH_ACTION_PARAMS
        dummy_ue_ipv4_address = None
        patch_get_iface_ip_address.return_value = dummy_ue_ipv4_address
        patch_service_active.return_value = True

        self.harness.charm._on_attach_ue_action(mock_event)

        self.assertEqual(
            mock_event.fail.call_args,
            call("Failed to attach. UE already running, please detach first."),
        )

    @patch("charm.service_active", side_effect=[True, False])
    @patch("charm.get_iface_ip_address")
    @patch("builtins.open", new_callable=mock_open)
    @patch("subprocess.run")
    def test_given_imsi_k_and_opc_when_attached_ue_action_then_srsue_service_sets_action_result(
        self, patch_subprocess_run, _, patch_get_iface_ip_address, patch_service_active
    ):
        mock_event = Mock()
        mock_event.params = self.ATTACH_ACTION_PARAMS
        dummy_ue_ipv4_address = "192.168.128.13"
        patch_get_iface_ip_address.return_value = dummy_ue_ipv4_address

        self.harness.charm._on_attach_ue_action(mock_event)

        self.assertEqual(
            mock_event.set_results.call_args,
            call(
                {
                    "message": "Attached successfully.",
                    "ue-ipv4": dummy_ue_ipv4_address,
                }
            ),
        )

    @patch("charm.service_active", side_effect=[True, False, True, True])
    @patch("charm.get_iface_ip_address")
    @patch("builtins.open", new_callable=mock_open)
    @patch("subprocess.run")
    def test_given_imsi_k_ops_and_mme_when_attached_ue_action_then_status_is_active(
        self, patch_subprocess_run, _, patch_get_iface_ip_address, __
    ):
        mock_event = Mock()
        mock_event.params = self.ATTACH_ACTION_PARAMS
        dummy_ue_ipv4_address = "192.168.128.13"
        patch_get_iface_ip_address.return_value = dummy_ue_ipv4_address
        self.harness.charm._stored.installed = True
        self.harness.charm._stored.started = True
        self.harness.charm._stored.mme_addr = "0.0.0.0"
        self.harness.charm.ue_attached = True

        self.harness.charm._on_attach_ue_action(mock_event)

        self.assertEqual(
            self.harness.charm.unit.status,
            ActiveStatus("srsenb started. mme: 0.0.0.0. ue attached. "),
        )

    @patch("utils.service_active")
    @patch("builtins.open", new_callable=mock_open)
    @patch("subprocess.run")
    def test_given_detach_ue_action_when_detach_ue_action_then_status_is_active(  # noqa: E501
        self, _, __, patch_service_active
    ):
        mock_event = Mock()
        mock_event.params = self.DETACH_ACTION_PARAMS
        self.harness.charm._stored.installed = True
        self.harness.charm._stored.started = True
        patch_service_active.return_value = True
        self.harness.charm._stored.ue_attached = False

        self.harness.charm._on_detach_ue_action(mock_event)

        self.assertNotEqual(self.harness.charm.unit.status, ActiveStatus("ue attached. "))
        self.assertNotEqual(self.harness.charm.unit.status, ActiveStatus(""))

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
    @patch("subprocess.run")
    def test_given_detach_ue_action_when_detach_ue_action_then_srsue_service_sets_action_result(  # noqa: E501
        self, _, __
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

    @patch("subprocess.run")
    def test_given_on_remove_default_gw_action_when_default_gw_action_then_sets_action_result(  # noqa: E501
        self, patch_subprocess_run
    ):
        mock_event = Mock()

        self.harness.charm._on_remove_default_gw_action(mock_event)

        self.assertEqual(
            mock_event.set_results.call_args,
            call({"status": "ok", "message": "Default route removed!"}),
        )

    @patch("subprocess.run")
    def test_given_on_remove_default_gw_action_when_remove_default_gw_action_then_status_does_not_change(  # noqa: E501
        self, _
    ):
        mock_event = Mock()
        old_status = self.harness.charm.unit.status

        self.harness.charm._on_remove_default_gw_action(mock_event)

        self.assertEqual(self.harness.charm.unit.status, old_status)

    # lte-core-interface
    @patch("subprocess.run", new=Mock())
    @patch("builtins.open", new_callable=mock_open)
    @patch("charm.service_active")
    def test_given_lte_core_provider_charm_when_relation_is_created_then_mme_addr_is_updated_in_stored(  # noqa: E501
        self, patch_service_active, _
    ):
        mme_ipv4_address = "0.0.0.0"
        relation_data = {"mme_ipv4_address": mme_ipv4_address}
        relation_id = self.harness.add_relation(
            relation_name=self.relation_name, remote_app=self.remote_app_name
        )

        self.harness.update_relation_data(
            relation_id=relation_id,
            app_or_unit=self.remote_app_name,
            key_values=relation_data,
        )

        self.assertEqual(self.harness.charm._stored.mme_addr, mme_ipv4_address)
