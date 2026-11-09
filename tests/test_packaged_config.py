from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aurix import config


class PackagedAppConfigTests(unittest.TestCase):
    def test_msix_uses_package_local_state_for_user_data(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(config, "PACKAGE_FAMILY_NAME", "AURIXAI_testpublisher"), patch.dict(
                os.environ, {"LOCALAPPDATA": temporary}, clear=False
            ):
                result = config._resolve_app_data_dir()
            self.assertEqual(
                result,
                Path(temporary) / "Packages" / "AURIXAI_testpublisher" / "LocalState" / "AurixAI",
            )

    def test_classic_install_keeps_roaming_appdata_location(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            roaming = Path(temporary) / "Roaming"
            with patch.object(config, "PACKAGE_FAMILY_NAME", None), patch.dict(
                os.environ, {"APPDATA": str(roaming)}, clear=False
            ):
                result = config._resolve_app_data_dir()
            self.assertEqual(result, roaming / "AurixAI")

    def test_msix_does_not_write_classic_run_registry_entry(self) -> None:
        with patch.object(config, "is_packaged_app", return_value=True):
            ok, message = config.set_start_with_windows(True)
        self.assertFalse(ok)
        self.assertIn("gerenciada pelo Windows", message)


if __name__ == "__main__":
    unittest.main()
