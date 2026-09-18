from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


@dataclass(slots=True)
class StreamEvent:
    source_id: int
    kind: str
    message: str
    jpeg_bytes: bytes | None = None
    timestamp: float | None = None


class MjpegStreamClient:
    def __init__(
        self,
        stream_url: str,
        event_callback: Callable[[StreamEvent], None],
        reconnect_delay: float = 2.0,
        source_id: int = 0,
    ) -> None:
        self.stream_url = stream_url
        self.event_callback = event_callback
        self.reconnect_delay = reconnect_delay
        self.source_id = source_id
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._response = None
        self._response_lock = threading.Lock()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="mjpeg-stream-client", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self._response_lock:
            if self._response is not None:
                self._response.close()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self.event_callback(StreamEvent(source_id=self.source_id, kind="status", message="Connecting to camera..."))
            try:
                self._consume_stream()
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                self.event_callback(StreamEvent(source_id=self.source_id, kind="error", message=f"Camera offline: {exc}"))
            if not self._stop_event.is_set():
                time.sleep(self.reconnect_delay)

    def _consume_stream(self) -> None:
        buffer = bytearray()
        with urlopen(self.stream_url, timeout=5) as response:
            with self._response_lock:
                self._response = response
            try:
                self.event_callback(StreamEvent(source_id=self.source_id, kind="status", message="Camera connected"))
                while not self._stop_event.is_set():
                    chunk = response.read(4096)
                    if not chunk:
                        raise ConnectionError("stream ended")
                    buffer.extend(chunk)
                    while True:
                        start = buffer.find(b"\xff\xd8")
                        end = buffer.find(b"\xff\xd9", start + 2)
                        if start == -1 or end == -1:
                            if start > 0:
                                del buffer[:start]
                            break
                        jpeg_bytes = bytes(buffer[start : end + 2])
                        del buffer[: end + 2]
                        self.event_callback(
                            StreamEvent(
                                source_id=self.source_id,
                                kind="frame",
                                message="frame",
                                jpeg_bytes=jpeg_bytes,
                                timestamp=time.time(),
                            )
                        )
            finally:
                with self._response_lock:
                    self._response = None
