import unittest
from unittest.mock import patch

from recorder.recording import RecorderEngine

try:
    from recorder.gui import BodyCamApp
except ModuleNotFoundError as exc:  # pragma: no cover - depends on local Python build
    BodyCamApp = None
    GUI_IMPORT_ERROR = exc
else:
    GUI_IMPORT_ERROR = None


class DummyVar:
    def __init__(self) -> None:
        self.value = None

    def set(self, value: str) -> None:
        self.value = value


class DummyDevice:
    stream_url = "http://127.0.0.1:8000/stream"


class DummyClient:
    def __init__(self, stream_url, event_callback, source_id=0, reconnect_delay=2.0):
        self.stream_url = stream_url
        self.event_callback = event_callback
        self.source_id = source_id
        self.reconnect_delay = reconnect_delay
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


@unittest.skipIf(BodyCamApp is None, f"tkinter unavailable: {GUI_IMPORT_ERROR}")
class GuiLogicTests(unittest.TestCase):
    def test_connect_stream_with_reset_replaces_recorder_and_increments_source_id(self) -> None:
        app = object.__new__(BodyCamApp)
        old_client = DummyClient("old", None, source_id=1)
        old_recorder = RecorderEngine(buffer_seconds=30, target_fps=10)
        old_recorder.ingest_frame(b"\xff\xd8frame\xff\xd9", timestamp=1.0)
        app.stream_client = old_client
        app.recorder = old_recorder
        app.recording_var = DummyVar()
        app.error_var = DummyVar()
        app.connection_var = DummyVar()
        app.device = DummyDevice()
        app.events = None
        app.stream_source_id = 1

        with patch("recorder.gui.MjpegStreamClient", DummyClient):
            BodyCamApp._connect_stream(app, reset_buffer=True)

        self.assertTrue(old_client.stopped)
        self.assertNotEqual(old_recorder, app.recorder)
        self.assertEqual(0, len(app.recorder.buffer))
        self.assertEqual(2, app.stream_source_id)
        self.assertEqual("Connecting...", app.connection_var.value)
        self.assertEqual("Idle", app.recording_var.value)
        self.assertTrue(app.stream_client.started)
        self.assertEqual(2, app.stream_client.source_id)

    def test_connect_stream_refuses_reset_during_active_recording(self) -> None:
        app = object.__new__(BodyCamApp)
        recorder = RecorderEngine(buffer_seconds=30, target_fps=10)
        recorder.start_event("CAM-001", "Front Camera", timestamp=1.0)
        app.stream_client = None
        app.recorder = recorder
        app.recording_var = DummyVar()
        app.error_var = DummyVar()
        app.connection_var = DummyVar()
        app.device = DummyDevice()
        app.events = None
        app.stream_source_id = 0

        with self.assertRaises(RuntimeError):
            BodyCamApp._connect_stream(app, reset_buffer=True)

    def test_stop_and_save_warns_when_event_has_no_frames(self) -> None:
        app = object.__new__(BodyCamApp)
        recorder = RecorderEngine(buffer_seconds=30, target_fps=10)
        recorder.start_event("CAM-001", "Front Camera", timestamp=1.0)
        app.recorder = recorder
        app.recording_var = DummyVar()
        app.root = object()

        with patch("recorder.gui.messagebox.showwarning") as showwarning:
            BodyCamApp.stop_and_save(app)

        self.assertEqual("Idle", app.recording_var.value)
        showwarning.assert_called_once()
        self.assertFalse(app.recorder.is_recording)


if __name__ == "__main__":
    unittest.main()
