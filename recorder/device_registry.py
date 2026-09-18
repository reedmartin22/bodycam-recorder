from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List

from recorder import config


@dataclass
class Device:
    device_id: str
    friendly_name: str
    stream_url: str

    @classmethod
    def from_dict(cls, payload: dict) -> "Device":
        return cls(
            device_id=str(payload["device_id"]).strip(),
            friendly_name=str(payload.get("friendly_name") or payload["device_id"]).strip(),
            stream_url=str(payload["stream_url"]).strip(),
        )


def _default_device() -> Device:
    return Device(
        device_id=config.DEFAULT_DEVICE_ID,
        friendly_name=config.DEFAULT_DEVICE_NAME,
        stream_url=config.default_stream_url(),
    )


class DeviceRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config.devices_file()

    def ensure_exists(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.save_devices([_default_device()])

    def load_devices(self) -> List[Device]:
        self.ensure_exists()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = []
        if not isinstance(payload, list):
            payload = []

        devices = []
        for item in payload:
            if not item:
                continue
            try:
                devices.append(Device.from_dict(item))
            except (KeyError, TypeError, ValueError):
                continue
        if not devices:
            devices = [_default_device()]
            self.save_devices(devices)
        return devices

    def save_devices(self, devices: Iterable[Device]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serializable = [asdict(device) for device in devices]
        self.path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")

    def upsert_device(self, device: Device) -> List[Device]:
        devices = self.load_devices()
        updated: List[Device] = []
        replaced = False
        for existing in devices:
            if existing.device_id.casefold() == device.device_id.casefold():
                updated.append(device)
                replaced = True
            else:
                updated.append(existing)
        if not replaced:
            updated.insert(0, device)
        self.save_devices(updated)
        return updated

    def primary_device(self) -> Device:
        return self.load_devices()[0]
