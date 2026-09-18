# BodyCam Recorder

A Windows-first Python MVP for a DIY body camera workflow. It includes:

- a plain Tkinter desktop app for monitoring and recording
- a local simulated camera that speaks a simple MJPEG-over-HTTP stream
- a 30-second rolling pre-event buffer at a default 10 FPS target
- Windows packaging with PyInstaller and a GitHub Actions artifact build

## What gets saved

Recordings are written under `data/recordings/`.

Each saved event is a folder named like:

```text
data/recordings/20260918-031500-123456_SIMULATOR-LOCAL/
```

Inside each folder:

- `frames/frame_00001.jpg`, `frame_00002.jpg`, ...: JPEG frames in order
- `metadata.json`: timestamps, device information, target FPS, and how many buffered pre-event frames were preserved

This MVP intentionally stores a reliable JPEG frame sequence instead of attempting hardware-specific video packaging too early.

## Device enrollment

The GUI reads `data/devices.json`. On first run, if that file is missing, the app creates a default local simulator device automatically.

Each enrolled device entry uses this shape:

```json
[
  {
    "device_id": "AA:BB:CC:DD:EE:FF",
    "friendly_name": "Chest Camera",
    "stream_url": "http://192.168.1.50:8000/stream"
  }
]
```

For the simulator, the default device is already included:

```json
[
  {
    "device_id": "SIMULATOR-LOCAL",
    "friendly_name": "Local Simulated Camera",
    "stream_url": "http://127.0.0.1:8000/stream"
  }
]
```

## Run from source on Windows

These steps are for local development or testing from source. You only need Python installed for this path.

1. Install Python 3.12 or newer from [python.org](https://www.python.org/downloads/windows/).
2. Clone or download this repository.
3. Open **PowerShell** in the repository folder.
4. Create and activate a virtual environment:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

5. Install the runtime dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Start the simulator

In one PowerShell window:

```powershell
python -m simulator --host 127.0.0.1 --port 8000 --fps 10
```

### Start the GUI

In another PowerShell window:

```powershell
python -m recorder
```

The GUI will show the enrolled device name and ID, connection state, recording state, a live preview, and buttons to start/stop event recording and open the recordings folder.

### Typical simulator test flow

1. Start the simulator.
2. Start the GUI.
3. Confirm the preview updates.
4. Let it run for at least 30 seconds.
5. Click **Start Event**.
6. Wait a few more seconds.
7. Click **Stop & Save**.
8. Open `data/recordings/` to inspect the new event folder.

If the simulator is offline, the GUI shows a clear offline error and keeps retrying the connection.

## Build a Windows executable locally

Install the packaging dependency:

```powershell
python -m pip install -r requirements-dev.txt
```

Build the GUI app:

```powershell
python -m PyInstaller --noconfirm --windowed --name BodyCamRecorder recorder/__main__.py
```

The executable is created at:

```text
dist/BodyCamRecorder/BodyCamRecorder.exe
```

Copy `data/devices.json` beside the extracted build as `dist/BodyCamRecorder/data/devices.json`, or let the app create a default local simulator entry on first run.

## Download the compiled executable from GitHub Actions

A Windows workflow builds the GUI and uploads an artifact named **`BodyCamRecorder-windows`**.

To download it:

1. Open the repository **Actions** tab.
2. Open a completed **Build Windows executable** workflow run.
3. Download the **`BodyCamRecorder-windows`** artifact.
4. Extract the artifact and run `BodyCamRecorder.exe`.

You do **not** need Python installed to run the packaged executable.

## Config knobs

The app uses these optional environment variables:

- `BODYCAM_BUFFER_SECONDS` (default `30`)
- `BODYCAM_TARGET_FPS` (default `10`)
- `BODYCAM_SIMULATOR_STREAM_URL` (default `http://127.0.0.1:8000/stream`)

## Tests

Run the non-GUI unit tests with:

```powershell
python -m unittest discover -s tests -v
```
