from __future__ import annotations

import io
import os
import platform
import queue
import subprocess
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from recorder import config
from recorder.device_registry import Device, DeviceRegistry
from recorder.recording import RecorderEngine
from recorder.stream import MjpegStreamClient, StreamEvent


class EnrollmentDialog(tk.Toplevel):
    def __init__(self, master: tk.Tk, device: Device) -> None:
        super().__init__(master)
        self.title("Enroll Device")
        self.resizable(False, False)
        self.result: Device | None = None

        self.name_var = tk.StringVar(value=device.friendly_name)
        self.id_var = tk.StringVar(value=device.device_id)
        self.url_var = tk.StringVar(value=device.stream_url)

        form = ttk.Frame(self, padding=12)
        form.grid(sticky="nsew")
        for row, (label, variable) in enumerate(
            [
                ("Friendly name", self.name_var),
                ("Device ID / MAC", self.id_var),
                ("Stream URL", self.url_var),
            ]
        ):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Entry(form, width=42, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)

        button_row = ttk.Frame(form)
        button_row.grid(row=3, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(button_row, text="Cancel", command=self.destroy).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(button_row, text="Save", command=self._save).grid(row=0, column=1)

        self.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _save(self) -> None:
        friendly_name = self.name_var.get().strip()
        device_id = self.id_var.get().strip()
        stream_url = self.url_var.get().strip()
        if not friendly_name or not device_id or not stream_url:
            messagebox.showerror("Missing details", "Friendly name, device ID, and stream URL are required.", parent=self)
            return
        self.result = Device(device_id=device_id, friendly_name=friendly_name, stream_url=stream_url)
        self.destroy()


class BodyCamApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("BodyCam Recorder")
        self.root.geometry("900x700")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.registry = DeviceRegistry()
        self.device = self.registry.primary_device()
        self.recorder = RecorderEngine()
        self.events: queue.Queue[StreamEvent] = queue.Queue()
        self.stream_client: MjpegStreamClient | None = None
        self.stream_source_id = 0
        self.preview_image: ImageTk.PhotoImage | None = None

        self.device_name_var = tk.StringVar(value=self.device.friendly_name)
        self.device_id_var = tk.StringVar(value=self.device.device_id)
        self.connection_var = tk.StringVar(value="Disconnected")
        self.recording_var = tk.StringVar(value="Idle")
        self.error_var = tk.StringVar(value="")

        self._build_ui()
        self._connect_stream(reset_buffer=True)
        self.root.after(50, self._process_events)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)

        info = ttk.LabelFrame(container, text="Enrolled Device", padding=12)
        info.pack(fill="x")
        ttk.Label(info, text="Friendly name:").grid(row=0, column=0, sticky="w")
        ttk.Label(info, textvariable=self.device_name_var).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Label(info, text="Device ID:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(info, textvariable=self.device_id_var).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(6, 0))
        ttk.Button(info, text="Enroll / Edit Device", command=self.enroll_device).grid(row=0, column=2, rowspan=2, padx=(16, 0))

        status = ttk.LabelFrame(container, text="Status", padding=12)
        status.pack(fill="x", pady=(12, 0))
        ttk.Label(status, text="Connection:").grid(row=0, column=0, sticky="w")
        ttk.Label(status, textvariable=self.connection_var).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Label(status, text="Recording:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(status, textvariable=self.recording_var).grid(row=1, column=1, sticky="w", padx=(8, 0))
        ttk.Label(status, textvariable=self.error_var, foreground="#b00020", wraplength=820).grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))

        preview_frame = ttk.LabelFrame(container, text="Live Preview", padding=12)
        preview_frame.pack(fill="both", expand=True, pady=(12, 0))
        self.preview_label = ttk.Label(preview_frame, text="Waiting for camera stream...", anchor="center")
        self.preview_label.pack(fill="both", expand=True)

        controls = ttk.Frame(container)
        controls.pack(fill="x", pady=(12, 0))
        self.start_button = ttk.Button(controls, text="Start Event", command=self.start_event)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(controls, text="Stop & Save", command=self.stop_and_save)
        self.stop_button.pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Open Recordings Folder", command=self.open_recordings_folder).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Quit", command=self.on_close).pack(side="right")

    def _enqueue_stream_event(self, event: StreamEvent) -> None:
        """Queue stream events when the app has a queue, including in lightweight tests."""
        events = getattr(self, "events", None)
        if events is not None:
            events.put(event)

    def _connect_stream(self, reset_buffer: bool) -> None:
        if reset_buffer and self.recorder.is_recording:
            raise RuntimeError("Cannot reset the recorder while an event recording is active.")
        self.stream_source_id += 1
        if self.stream_client is not None:
            self.stream_client.stop()
        if reset_buffer:
            self.recorder = RecorderEngine(
                buffer_seconds=self.recorder.buffer_seconds,
                target_fps=self.recorder.target_fps,
                recordings_dir=self.recorder.recordings_dir,
            )
            self.recording_var.set("Idle")
        self.error_var.set("")
        self.connection_var.set("Connecting...")
        self.stream_client = MjpegStreamClient(
            self.device.stream_url,
            self._enqueue_stream_event,
            source_id=self.stream_source_id,
        )
        self.stream_client.start()

    def _process_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                if event.source_id != self.stream_source_id:
                    continue
                if event.kind == "frame" and event.jpeg_bytes is not None and event.timestamp is not None:
                    self.connection_var.set("Connected")
                    self.error_var.set("")
                    self.recorder.ingest_frame(event.jpeg_bytes, event.timestamp)
                    self._update_preview(event.jpeg_bytes)
                elif event.kind == "status":
                    self.connection_var.set(event.message)
                elif event.kind == "error":
                    self.connection_var.set("Offline")
                    self.error_var.set(event.message)
        except queue.Empty:
            pass
        self.root.after(50, self._process_events)

    def _update_preview(self, jpeg_bytes: bytes) -> None:
        try:
            image = Image.open(io.BytesIO(jpeg_bytes))
            image.thumbnail((840, 520))
            self.preview_image = ImageTk.PhotoImage(image)
            self.preview_label.configure(image=self.preview_image, text="")
        except OSError as exc:
            self.error_var.set(f"Preview update failed: {exc}")

    def enroll_device(self) -> None:
        if self.recorder.is_recording:
            messagebox.showinfo(
                "Stop recording first",
                "Stop and save the current event before switching to a different enrolled device.",
                parent=self.root,
            )
            return
        dialog = EnrollmentDialog(self.root, self.device)
        self.root.wait_window(dialog)
        if dialog.result is None:
            return
        self.registry.upsert_device(dialog.result)
        self.device = dialog.result
        self.device_name_var.set(self.device.friendly_name)
        self.device_id_var.set(self.device.device_id)
        self._connect_stream(reset_buffer=False)

    def start_event(self) -> None:
        started = self.recorder.start_event(
            device_id=self.device.device_id,
            device_name=self.device.friendly_name,
            timestamp=time.time(),
        )
        if started:
            self.recording_var.set(f"Recording ({len(self.recorder.buffer)} buffered frames preserved)")
        else:
            messagebox.showinfo("Already recording", "An event recording is already in progress.", parent=self.root)

    def stop_and_save(self) -> None:
        had_recording, output_dir = self._finalize_active_recording()
        if output_dir is None:
            self.recording_var.set("Idle")
            if had_recording:
                messagebox.showwarning(
                    "No frames captured",
                    "The event was started, but no camera frames were captured before it was stopped.",
                    parent=self.root,
                )
            else:
                messagebox.showinfo("Nothing to save", "Start an event before stopping and saving.", parent=self.root)
            return
        self.recording_var.set(f"Saved to {output_dir.name}")
        messagebox.showinfo(
            "Recording saved",
            f"Saved the recording to:\n{output_dir}",
            parent=self.root,
        )

    def open_recordings_folder(self) -> None:
        path = str(self.recorder.recordings_dir)
        self.recorder.recordings_dir.mkdir(parents=True, exist_ok=True)
        try:
            if platform.system() == "Windows":
                os.startfile(path)  # type: ignore[attr-defined]
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except OSError as exc:
            messagebox.showerror("Unable to open folder", f"Could not open the recordings folder:\n{exc}", parent=self.root)

    def on_close(self) -> None:
        had_recording, saved_path = self._finalize_active_recording()
        if self.stream_client is not None:
            self.stream_client.stop()
        if saved_path is not None:
            messagebox.showinfo("Recording saved", f"Active recording finalized at:\n{saved_path}", parent=self.root)
        elif had_recording:
            messagebox.showinfo(
                "No frames captured",
                "The active event was finalized during exit, but no camera frames had been captured yet.",
                parent=self.root,
            )
        self.root.destroy()

    def _finalize_active_recording(self) -> tuple[bool, Path | None]:
        had_recording = self.recorder.is_recording
        if not had_recording:
            return False, None
        return True, self.recorder.stop_and_save()


def main() -> int:
    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    app = BodyCamApp(root)
    _ = app
    root.mainloop()
    return 0
