from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_BUFFER_SECONDS = 30
DEFAULT_TARGET_FPS = 10
DEFAULT_SIMULATOR_STREAM_URL = "http://127.0.0.1:8000/stream"
DEFAULT_DEVICE_ID = "SIMULATOR-LOCAL"
DEFAULT_DEVICE_NAME = "Local Simulated Camera"


def runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    path = runtime_root() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def devices_file() -> Path:
    return data_dir() / "devices.json"


def recordings_dir() -> Path:
    path = data_dir() / "recordings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def buffer_seconds() -> int:
    value = os.environ.get("BODYCAM_BUFFER_SECONDS", str(DEFAULT_BUFFER_SECONDS))
    return max(1, int(value))


def target_fps() -> int:
    value = os.environ.get("BODYCAM_TARGET_FPS", str(DEFAULT_TARGET_FPS))
    return max(1, int(value))


def default_stream_url() -> str:
    return os.environ.get("BODYCAM_SIMULATOR_STREAM_URL", DEFAULT_SIMULATOR_STREAM_URL)
