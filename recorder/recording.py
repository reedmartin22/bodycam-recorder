from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque, List

from recorder import config


@dataclass(slots=True)
class Frame:
    timestamp: float
    jpeg_bytes: bytes


class RollingBuffer:
    def __init__(self, duration_seconds: int) -> None:
        self.duration_seconds = duration_seconds
        self._frames: Deque[Frame] = deque()

    def append(self, frame: Frame) -> None:
        self._frames.append(frame)
        self._trim(frame.timestamp)

    def _trim(self, newest_timestamp: float) -> None:
        cutoff = newest_timestamp - self.duration_seconds
        while self._frames and self._frames[0].timestamp < cutoff:
            self._frames.popleft()

    def snapshot(self) -> List[Frame]:
        return list(self._frames)

    def __len__(self) -> int:
        return len(self._frames)


@dataclass
class RecordingSession:
    device_id: str
    device_name: str
    trigger_timestamp: float
    target_fps: int
    pre_event_frame_count: int
    frames: List[Frame] = field(default_factory=list)


class RecorderEngine:
    def __init__(self, buffer_seconds: int | None = None, target_fps: int | None = None, recordings_dir: Path | None = None) -> None:
        self.buffer_seconds = buffer_seconds or config.buffer_seconds()
        self.target_fps = target_fps or config.target_fps()
        self.recordings_dir = recordings_dir or config.recordings_dir()
        self.buffer = RollingBuffer(self.buffer_seconds)
        self.active_session: RecordingSession | None = None

    @property
    def is_recording(self) -> bool:
        return self.active_session is not None

    def ingest_frame(self, jpeg_bytes: bytes, timestamp: float) -> None:
        frame = Frame(timestamp=timestamp, jpeg_bytes=jpeg_bytes)
        self.buffer.append(frame)
        if self.active_session is not None:
            self.active_session.frames.append(frame)

    def start_event(self, device_id: str, device_name: str, timestamp: float) -> bool:
        if self.active_session is not None:
            return False
        snapshot = self.buffer.snapshot()
        self.active_session = RecordingSession(
            device_id=device_id,
            device_name=device_name,
            trigger_timestamp=timestamp,
            target_fps=self.target_fps,
            pre_event_frame_count=len(snapshot),
            frames=list(snapshot),
        )
        return True

    def stop_and_save(self) -> Path | None:
        session = self.active_session
        if session is None or not session.frames:
            self.active_session = None
            return None

        started_at = session.frames[0].timestamp
        recording_name = datetime.fromtimestamp(started_at, tz=timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        safe_device_id = re.sub(r"[^A-Za-z0-9._-]+", "-", session.device_id).strip("-") or "device"
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        output_dir = self.recordings_dir / f"{recording_name}_{safe_device_id}"
        frames_dir = output_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        frame_entries = []
        for index, frame in enumerate(session.frames, start=1):
            filename = f"frame_{index:05d}.jpg"
            (frames_dir / filename).write_bytes(frame.jpeg_bytes)
            frame_entries.append(
                {
                    "index": index,
                    "file": f"frames/{filename}",
                    "timestamp_utc": datetime.fromtimestamp(frame.timestamp, tz=timezone.utc).isoformat(),
                    "offset_ms": int(round((frame.timestamp - started_at) * 1000)),
                }
            )

        metadata = {
            "format": "jpeg-frame-sequence",
            "device_id": session.device_id,
            "device_name": session.device_name,
            "buffer_seconds": self.buffer_seconds,
            "target_fps": session.target_fps,
            "triggered_at_utc": datetime.fromtimestamp(session.trigger_timestamp, tz=timezone.utc).isoformat(),
            "recording_started_at_utc": datetime.fromtimestamp(started_at, tz=timezone.utc).isoformat(),
            "recording_stopped_at_utc": datetime.fromtimestamp(session.frames[-1].timestamp, tz=timezone.utc).isoformat(),
            "pre_event_frame_count": session.pre_event_frame_count,
            "total_frames": len(session.frames),
            "frames": frame_entries,
        }
        (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        self.active_session = None
        return output_dir
