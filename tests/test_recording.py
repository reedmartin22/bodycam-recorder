import json
import tempfile
import unittest
from pathlib import Path

from recorder.recording import Frame, RecorderEngine, RollingBuffer


JPEG_BYTES = b"\xff\xd8test-frame\xff\xd9"


class RollingBufferTests(unittest.TestCase):
    def test_buffer_keeps_only_recent_duration(self) -> None:
        buffer = RollingBuffer(duration_seconds=30)
        buffer.append(Frame(timestamp=0.0, jpeg_bytes=JPEG_BYTES))
        buffer.append(Frame(timestamp=15.0, jpeg_bytes=JPEG_BYTES))
        buffer.append(Frame(timestamp=31.0, jpeg_bytes=JPEG_BYTES))

        snapshot = buffer.snapshot()

        self.assertEqual([15.0, 31.0], [frame.timestamp for frame in snapshot])


class RecorderEngineTests(unittest.TestCase):
    def test_start_event_preserves_pre_event_frames_and_saves_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = RecorderEngine(buffer_seconds=30, target_fps=10, recordings_dir=Path(temp_dir))
            engine.ingest_frame(JPEG_BYTES, timestamp=100.0)
            engine.ingest_frame(JPEG_BYTES, timestamp=110.0)

            self.assertTrue(engine.start_event("CAM-001", "Front Camera", timestamp=112.0))
            engine.ingest_frame(JPEG_BYTES, timestamp=120.0)
            output_dir = engine.stop_and_save()

            self.assertIsNotNone(output_dir)
            metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual("jpeg-frame-sequence", metadata["format"])
            self.assertEqual(2, metadata["pre_event_frame_count"])
            self.assertEqual(3, metadata["total_frames"])
            self.assertTrue((output_dir / "frames" / "frame_00001.jpg").exists())
            self.assertTrue((output_dir / "frames" / "frame_00003.jpg").exists())

    def test_stop_without_frames_returns_none_and_clears_active_session(self) -> None:
        engine = RecorderEngine(buffer_seconds=30, target_fps=10, recordings_dir=Path.cwd())

        self.assertTrue(engine.start_event("CAM-001", "Front Camera", timestamp=112.0))
        self.assertIsNone(engine.stop_and_save())
        self.assertFalse(engine.is_recording)


if __name__ == "__main__":
    unittest.main()
