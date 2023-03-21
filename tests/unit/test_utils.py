# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import patch

from utils import shell


class TestUtils(unittest.TestCase):
    @patch("subprocess.run")
    def test_given_command_when_shell_then_subprocess_run(self, patch_run):
        command = "whatever command"

        shell(command=command)

        patch_run.assert_called_with(command, shell=True, stdout=-1, encoding="utf-8")
