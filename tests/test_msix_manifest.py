from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "packaging" / "msix" / "AppxManifest.xml.template"


class MsixManifestTests(unittest.TestCase):
    def test_manifest_template_is_valid_xml(self) -> None:
        root = ET.parse(MANIFEST).getroot()
        self.assertTrue(root.tag.endswith("Package"))

    def test_manifest_has_desktop_full_trust_entry_point(self) -> None:
        root = ET.parse(MANIFEST).getroot()
        ns = {"a": "http://schemas.microsoft.com/appx/manifest/foundation/windows10"}
        app = root.find(".//a:Application", ns)
        self.assertIsNotNone(app)
        self.assertEqual(app.attrib.get("Executable"), "AURIX-AI.exe")
        self.assertEqual(app.attrib.get("EntryPoint"), "Windows.FullTrustApplication")

    def test_manifest_requests_full_trust_and_microphone(self) -> None:
        root = ET.parse(MANIFEST).getroot()
        capabilities = root.find("{http://schemas.microsoft.com/appx/manifest/foundation/windows10}Capabilities")
        self.assertIsNotNone(capabilities)
        names = {element.attrib.get("Name") for element in capabilities}
        self.assertIn("runFullTrust", names)
        self.assertIn("microphone", names)

    def test_manifest_identity_values_are_build_time_tokens(self) -> None:
        text = MANIFEST.read_text(encoding="utf-8")
        for token in ("__IDENTITY_NAME__", "__PUBLISHER__", "__VERSION__", "__PUBLISHER_DISPLAY_NAME__"):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
