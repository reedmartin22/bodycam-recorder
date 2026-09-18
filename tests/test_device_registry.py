import json
import tempfile
import unittest
from pathlib import Path

from recorder.device_registry import Device, DeviceRegistry


class DeviceRegistryTests(unittest.TestCase):
    def test_missing_registry_creates_default_device(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = DeviceRegistry(Path(temp_dir) / "devices.json")

            devices = registry.load_devices()

            self.assertEqual(1, len(devices))
            self.assertEqual("SIMULATOR-LOCAL", devices[0].device_id)
            self.assertTrue(registry.path.exists())

    def test_upsert_replaces_matching_device_id_case_insensitively(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "devices.json"
            path.write_text(
                json.dumps([
                    {
                        "device_id": "aa:bb:cc:dd:ee:ff",
                        "friendly_name": "Old Camera",
                        "stream_url": "http://old/stream",
                    }
                ]),
                encoding="utf-8",
            )
            registry = DeviceRegistry(path)

            devices = registry.upsert_device(
                Device(
                    device_id="AA:BB:CC:DD:EE:FF",
                    friendly_name="New Camera",
                    stream_url="http://new/stream",
                )
            )

            self.assertEqual(1, len(devices))
            self.assertEqual("New Camera", devices[0].friendly_name)
            self.assertEqual("http://new/stream", devices[0].stream_url)


if __name__ == "__main__":
    unittest.main()
