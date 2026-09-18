from __future__ import annotations

import argparse
import io
import json
import math
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterable
from urllib.parse import urlparse

from PIL import Image, ImageDraw

BOUNDARY = "frame"


class SimulatorState:
    def __init__(self, width: int, height: int, fps: int, device_id: str, friendly_name: str) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self.device_id = device_id
        self.friendly_name = friendly_name
        self.started_at = time.time()

    def frame_bytes(self) -> bytes:
        elapsed = time.time() - self.started_at
        image = Image.new("RGB", (self.width, self.height), color=(18, 24, 31))
        draw = ImageDraw.Draw(image)
        radius = 32
        x = int((self.width - radius * 2) * (0.5 + 0.4 * math.sin(elapsed)))
        y = int((self.height - radius * 2) * (0.5 + 0.4 * math.cos(elapsed / 1.7)))
        draw.ellipse((x, y, x + radius * 2, y + radius * 2), fill=(220, 32, 32))
        text_lines = [
            "BodyCam Recorder Simulator",
            f"Device: {self.friendly_name}",
            f"ID: {self.device_id}",
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        ]
        for index, line in enumerate(text_lines):
            draw.text((16, 16 + index * 24), line, fill=(240, 240, 240))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=80)
        return buffer.getvalue()


class SimulatorHandler(BaseHTTPRequestHandler):
    server_version = "BodyCamSimulator/0.1"

    @property
    def state(self) -> SimulatorState:
        return self.server.state  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {"/", "/health"}:
            self._send_json({"status": "ok", "stream_url": "/stream"})
        elif path == "/device.json":
            self._send_json(
                {
                    "device_id": self.state.device_id,
                    "friendly_name": self.state.friendly_name,
                    "fps": self.state.fps,
                    "resolution": [self.state.width, self.state.height],
                }
            )
        elif path == "/stream":
            self._stream_frames()
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def _send_json(self, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _stream_frames(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Pragma", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY}")
        self.end_headers()

        frame_interval = 1 / max(1, self.state.fps)
        try:
            while True:
                frame = self.state.frame_bytes()
                self.wfile.write(f"--{BOUNDARY}\r\n".encode("ascii"))
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii"))
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
                time.sleep(frame_interval)
        except (BrokenPipeError, ConnectionResetError):
            return

    def log_message(self, format: str, *args: object) -> None:
        return


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def port_number(value: str) -> int:
    parsed = int(value)
    if parsed <= 0 or parsed > 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local BodyCam Recorder simulator.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=port_number, default=8000)
    parser.add_argument("--width", type=positive_int, default=640)
    parser.add_argument("--height", type=positive_int, default=480)
    parser.add_argument("--fps", type=positive_int, default=10)
    parser.add_argument("--device-id", default="SIMULATOR-LOCAL")
    parser.add_argument("--friendly-name", default="Local Simulated Camera")
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), SimulatorHandler)
    server.state = SimulatorState(  # type: ignore[attr-defined]
        width=args.width,
        height=args.height,
        fps=args.fps,
        device_id=args.device_id,
        friendly_name=args.friendly_name,
    )
    print(f"Simulator running at http://{args.host}:{args.port}/stream")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
