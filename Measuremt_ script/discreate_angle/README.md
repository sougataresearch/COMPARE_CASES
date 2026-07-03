# MMIE Control Software — Discrete Angle Acquisition

Python control software for a Mueller Matrix Imaging Ellipsometer using:

- Four Thorlabs K10CR2/M cage rotators
- One IDS U3-3890CP-M-GL camera
- Thorlabs Kinesis through `pythonnet`
- IDS Peak

This folder covers **3×3** and **4×4 discrete** (stepped-QWP) acquisition only.
4×4 continuous rotation is a separate, independent implementation in
`../continous_rotation/` — the two folders share no code or run data.

## Which file should I run?

Run only:

```powershell
python 01_main.py
```

`01_main.py` is the operator entry point. It automatically imports and calls the
other Python files in the correct order. Do **not** run `motor_controller.py`,
`camera_controller.py`, or the other modules individually.

The `MMIE_Control` directory is a separate notebook-based reference
implementation. It is not required when running `01_main.py`.

## First-time setup on the lab computer

### 1. Copy the complete project folder

Keep all these files together:

```text
01_main.py
config.py
utils.py
state_generator.py
motor_controller.py
camera_controller.py
measurement_engine.py
logger_manager.py
checkpoint_manager.py
calibration.py
README.md
```

### 2. Install the hardware software

Install:

1. Thorlabs Kinesis 64-bit
2. IDS Peak SDK
3. Python 3.11 or newer

Install the required Python packages:

```powershell
python -m pip install pythonnet numpy pandas opencv-python
```

Install the IDS Peak Python packages supplied or recommended by your IDS Peak
installation. Confirm that these imports work:

```python
from ids_peak import ids_peak
from ids_peak import ids_peak_ipl_extension
from ids_peak_ipl import ids_peak_ipl
```

### 3. Edit `config.py`

Enter the real serial number for each motor:

```python
MOTOR_SN = {
    "PSG_Polarizer": "...",
    "PSG_QWP": "...",
    "PSA_QWP": "...",
    "PSA_Analyzer": "...",
}
```

Enter the measured motor position corresponding to optical zero:

```python
ZERO_OFFSET = {
    "PSG_Polarizer": 0.0,
    "PSG_QWP": 0.0,
    "PSA_QWP": 0.0,
    "PSA_Analyzer": 0.0,
}
```

Check that `KINESIS_DIR` points to the Kinesis installation and that
`MOTOR_SETTINGS_NAME` matches the K10CR2 profile shown by Kinesis.

Do not perform a real measurement until the serial numbers and offsets have
been verified.

## Recommended first test

Run:

```powershell
python 01_main.py
```

Choose **dry-run mode** when prompted. Dry run:

- Does not load Kinesis or IDS Peak
- Does not connect, home, or move physical motors
- Does not trigger the physical camera
- Executes the real measurement workflow
- Generates synthetic BMP images
- Creates logs, checkpoints, configuration files, and a report

Use a small angle set such as:

```text
0,90
```

This produces four states when both PSG and PSA use the same two angles.

## Running a real experiment

Connect and power the required motors and camera, then run:

```powershell
python 01_main.py
```

The program performs the following sequence:

```text
Select 3×3 or 4×4 mode
        ↓
Verify software environment
        ↓
Enter operator and sample information
        ↓
Enter optical-angle states
        ↓
Preview optical angles, motor angles, and total states
        ↓
Estimate required disk space
        ↓
Detect the camera (fails fast, before any motor time is spent)
        ↓
Discover required motors
        ↓
Connect motors sequentially
        ↓
Load K10CR2 settings
        ↓
Enable motors
        ↓
Home motors
        ↓
Move to optical-zero offsets
        ↓
Initialize and test the camera
        ↓
Run measurement states
        ↓
Write final checkpoint and report
```

The software asks for confirmation before safety-sensitive initialization
stages.

## Camera preparation before every experiment

The camera is probed for its model and serial number **before any motor is
discovered, connected, or homed** — if no camera is found, the run aborts
immediately, so a missing/misconfigured camera never costs you the time of
homing motors first. Everything else below happens after the motors reach
optical zero:

1. It probes the IDS camera and prints its model and serial number (this
   happens up front, before motor initialization — see above).
2. Once the motors are at optical zero, it asks you to confirm the
   illumination/light source is turned on, before any Cockpit check.
3. At PSG `0°`, PSA `0°`, it asks you to open IDS Peak Cockpit and confirm the
   bright state.
4. You must close Cockpit and confirm that it is closed.
5. The software moves the PSA analyzer to optical `90°`.
6. It asks you to open Cockpit and confirm that the image is darker.
7. You close Cockpit, and the analyzer returns to optical `0°`.
8. At `0_0`, use Cockpit to select exposure time and frame rate.
9. Close Cockpit and enter those two values in the Python terminal.
10. Python applies the values through the IDS API and reads them back. If the
    camera rejects either value, it prints the error and asks for both
    values again — see "If the exposure time or frame rate..." below.
11. The requested and actual camera values are printed and saved.
12. Python captures automatic `0_0` bright and `0_90` dark references.
13. Minimum, maximum, mean, and pixels equal to 255 are reported.
14. A final confirmation is required before measurement begins.

Do not leave IDS Peak Cockpit open while Python is acquiring images. Cockpit
and Python can compete for control of the same camera.

If the exposure time or frame rate you enter is outside what the camera
actually supports at that setting (for example, the IDS U3-3890's minimum
frame rate is roughly 1.6 fps — entering something lower, or swapping the
exposure and frame-rate values by mistake, will be rejected), the software
prints the camera's error and asks for both values again. It does **not**
abort the run or require redoing motor homing/connecting — only the
exposure/frame-rate step is retried, on the same already-open camera
connection.

The runtime prompts use:

```text
Exposure time selected in IDS Peak Cockpit (ms)
Frame rate selected in IDS Peak Cockpit (fps)
```

Images are saved without automatic exposure, intensity rescaling, dark
subtraction, or saturation correction. In Mono8, a pixel value of 255 indicates
the top of the representable range. The software reports such pixels but does
not modify them.

## Mode behavior

### 3×3 mode

Only these motors are used:

- `PSG_Polarizer`
- `PSA_Analyzer`

The QWP motors are not connected, initialized, homed, or moved.

### 4×4 discrete mode

All four motors are initialized. The polarizers are placed at fixed optical
angles, while the two QWPs step through the requested angle combinations.

4×4 **continuous** rotation is not handled by this folder at all — see
`../continous_rotation/README.md`.

## Entering angles

Full-circle step syntax:

```text
360/10
```

This generates:

```text
0, 10, 20, ..., 350
```

The equivalent 360° state is not included.

Manual syntax:

```text
0,30,60,90,120,150
```

All entered angles are optical angles. The motor command is calculated as:

```text
motor angle = (optical angle + zero offset) modulo 360
```

Image filenames contain optical angles, not motor positions.

## Measurement loop

For each state, the software:

1. Commands each required motor.
2. Waits for motion to finish.
3. Compares commanded and motor-reported positions.
4. Retries a failed move up to two times.
5. Waits for mechanical settling.
6. Sends a software trigger to the camera.
7. Waits for image acquisition.
8. Retries failed acquisition up to two times.
9. Saves and decodes the BMP to verify it.
10. Writes the CSV log.
11. Updates the checkpoint only after success.
12. Continues to the next state.

The default retry delay and position tolerance can be changed in `config.py`.

## Emergency stop

Press:

```text
Ctrl-C
```

The program requests an immediate motor stop, stops camera acquisition,
preserves the last successful checkpoint, and disconnects the devices.

Keep the physical hardware emergency-stop or power-isolation method accessible.
Software stopping is not a substitute for laboratory hardware safety controls.

## Output folders

Each run creates:

```text
Data/
└── YYYY-MM-DD_RunXX/
    ├── Images/
    ├── Logs/
    ├── Config/
    ├── DarkFrames/
    ├── Reports/
    ├── Checkpoints/
    └── Results/
```

Important files:

- `Images/*.bmp` — captured images
- `Logs/experiment_log.csv` — commanded and reported positions and status
- `Logs/terminal_transcript.txt` — terminal output, prompts, and operator answers
- `Logs/error_traceback.txt` — full technical traceback when an error occurs
- `Config/experiment_config.json` — complete saved experiment configuration
- `Checkpoints/checkpoint.json` — last successfully completed state
- `Reports/ExperimentReport.txt` — final experiment summary
- `Results/BrightReference_0_0.bmp` — pre-measurement bright reference
- `Results/DarkReference_0_90.bmp` — pre-measurement dark reference

The transcript is flushed continuously so it remains useful after most crashes.
It includes environment results, confirmations, device identities, requested
and applied camera settings, image statistics, warnings, and retry messages.

## Resuming an interrupted experiment

Use the directory of the interrupted run:

```powershell
python 01_main.py --resume Data\YYYY-MM-DD_RunXX
```

The saved configuration is loaded, and acquisition continues after the last
successful checkpoint. Do not manually alter images or the checkpoint before
resuming.

## What each Python module does

| File | Purpose | Run directly? |
|---|---|---|
| `01_main.py` | Operator prompts and complete experiment orchestration | **Yes** |
| `config.py` | Motor identities, offsets, camera settings, and timing | No |
| `utils.py` | Environment checks, angle parsing, paths, and JSON writing | No |
| `state_generator.py` | Generates 3×3 and 4×4 optical states | No |
| `motor_controller.py` | Kinesis discovery, initialization, motion, and stopping | No |
| `camera_controller.py` | IDS configuration, triggering, saving, and verification | No |
| `measurement_engine.py` | Ordered measurement loop and error handling | No |
| `logger_manager.py` | CSV logging and final report generation | No |
| `checkpoint_manager.py` | Atomic crash-recovery checkpoints | No |
| `calibration.py` | Optical-zero and verification-scan utilities | No |

Every function below also has a matching explanatory comment directly above
it in the source file — read this table alongside the code with `#`
comments open to cross-check both at once.

## Settings that need to change for an experiment

### One-time, per lab computer / per hardware setup (edit `config.py`)

| Setting | File / location | What it controls |
|---|---|---|
| `MOTOR_SN` | `config.py` | USB serial number of each K10CR2/M rotator. Must match the physical device for that axis or `MotorController.discover()` raises `MotorError`. |
| `ZERO_OFFSET` | `config.py` | Motor angle that equals optical zero for each axis, found with `calibration.py`. Wrong values silently rotate every measurement by a constant offset. |
| `KINESIS_DIR` | `config.py` | Path to the Thorlabs Kinesis install. Checked by `utils.check_environment()` and used by `motor_controller._load_kinesis()`. |
| `MOTOR_SETTINGS_NAME` | `config.py` | Must match the K10CR2 device-settings profile name shown in Kinesis. |
| `CameraSettings.mean_too_dark` / `mean_too_bright` | `config.py` | Image-quality warning thresholds used in `camera_controller.save_bmp()`. Advisory only — does not block a run. |
| `TimingSettings.position_tolerance_deg` | `config.py` | Maximum allowed motor position error before a move is retried/failed. |
| `TimingSettings.*_s` delays, `motor_max_retries`, `CameraSettings.max_retries` | `config.py` | Retry counts and settle/backoff delays; tune for your hardware's noise and speed. |

### Every experiment (answered as prompts by `01_main.py`, not edited in code)

| Prompt | Asked by | Stored in |
|---|---|---|
| 3×3 vs 4×4 mode | `choose_mode_first()` | `ExperimentConfig.mode` |
| Dry-run vs real | `run_session()` (`utils.yes_no`) | `ExperimentConfig.dry_run` |
| Operator / sample / comments | `configure_experiment()` | `ExperimentConfig.metadata` |
| PSG/PSA (or QWP) angle lists | `ask_angles()` | `ExperimentConfig.state_inputs` |
| Fixed polarizer angles (4×4 only) | `ask_float()` in `configure_experiment()` | `ExperimentConfig.fixed_angles` |
| Exposure time (ms) / frame rate (fps) | `guided_camera_setup()` (`ask_positive_float`) | `ExperimentConfig.camera.exposure_us` / `frame_rate_fps` |
| Every safety confirmation (`confirm_stage`) | throughout `01_main.py` | not stored — answering "no" cancels that stage |

Everything in the second table is designed to be changed per run through the
terminal prompts, not by editing source files. Only the first table
(`config.py`) should normally need source edits, and only when the physical
hardware setup itself changes (different rotor swapped in, re-calibrated
zero, new lab PC, etc.).

## Function-by-function reference

### `01_main.py` — operator prompts and orchestration (run this file)

| Function | What it does |
|---|---|
| `ask_choice` / `ask_float` / `ask_positive_float` / `ask_angles` | Loop-until-valid input helpers for a choice set, a plain float, a positive float (camera exposure/frame rate), and an angle spec (`utils.parse_angle_spec`). |
| `choose_mode_first` | First prompt of every fresh run: 3×3 vs 4×4. Fixes which motors are active for the rest of the run. |
| `print_environment_report` | Runs `utils.check_environment()`, prints OK/MISSING per check, returns whether all passed. |
| `configure_experiment` | Asks operator/sample/comments, then mode-specific angle prompts; builds the `ExperimentConfig` and the `MeasurementState` list (via `state_generator`) for a fresh run. |
| `states_from_config` | Rebuilds the identical `MeasurementState` list from a saved config, for `--resume`, without re-asking the operator. |
| `confirm_stage` | Yes/no gate before a safety-sensitive step; "no" cancels the whole session. |
| `detect_camera` | Probes the camera (`camera.discover()`) and confirms it, before any motor step — so a missing camera aborts before motor time is spent homing. |
| `initialize_motors` | Runs discover → connect → initialize → enable → home → move-to-optical-zero, each behind a `confirm_stage`. |
| `move_analyzer_to_optical` | Moves `PSA_Analyzer` to a given optical angle (used by camera checks/references, not the main measurement loop). |
| `guided_camera_setup` | Confirms the light source is on, then walks the operator through the IDS Peak Cockpit bright/dark/exposure checks and records the chosen exposure/frame rate. |
| `capture_camera_references` | Captures and verifies the `BrightReference_0_0.bmp` / `DarkReference_0_90.bmp` images and checks bright > dark with no saturation. |
| `write_error_traceback` | Saves the current exception's full traceback to `Logs/error_traceback.txt`. |
| `ask_camera_settings` (nested in `run_session`) | The `ask_settings` callback passed to `camera.initialize()`; re-prompts for exposure/frame rate when the camera rejects them. |
| `run_session` | The full top-to-bottom run: mode → environment → config → disk check → hardware init → camera setup → measurement loop → cleanup. Its `finally` block always runs `camera.close()` and then `motors.close()`, even if `camera.close()` itself raises, so a camera cleanup problem can never leave the motors connected/undisconnected. Returns the process exit code. |
| `main` | Entry point: parses `--resume`, opens/creates the run directory, starts/stops the `SessionTranscript`, calls `run_session`. |

### `config.py` — settings and data models (not run directly)

| Item | What it does |
|---|---|
| `PROJECT_ROOT`, `DATA_ROOT` | Anchor paths; `DATA_ROOT` is where `Data/YYYY-MM-DD_RunXX` folders are created. |
| `MOTOR_SN`, `ZERO_OFFSET`, `KINESIS_DIR`, `REQUIRED_KINESIS_DLLS`, `MOTOR_SETTINGS_NAME` | Hardware identity/calibration constants — see "Settings that need to change" above. |
| `CameraSettings` | Dataclass of requested + applied camera values (exposure, frame rate, gain, retry/timeout, warning thresholds). |
| `TimingSettings` | Dataclass of every delay, retry count, and position tolerance used around motor/camera operations. |
| `ExperimentMetadata` | Operator/sample/comments text. |
| `ExperimentConfig` | The full serializable snapshot of one run (mode, metadata, angles, camera/timing settings); `to_dict()`/`from_dict()` make `Config/experiment_config.json` and `--resume` possible. |
| `ACTIVE_MOTORS` | Which motor names are active for `"3x3"` vs `"4x4"` mode. |

### `utils.py` — shared helpers (not run directly)

| Function | What it does |
|---|---|
| `optical_to_motor` | Core calibration formula: `motor = (optical + zero_offset) % 360`. |
| `format_angle` | Turns an angle into a clean, filesystem-safe label for filenames. |
| `parse_angle_spec` | Parses `"360/step"` or `"a,b,c"` angle text into a validated, duplicate-free list. |
| `create_run_directory` | Creates the next `Data/YYYY-MM-DD_RunXX` folder tree with its seven subfolders. |
| `write_json` | Atomic JSON write (write to `.tmp`, then rename) so crashes can't leave a half-written file. |
| `check_environment` | Import/filesystem-only diagnostic checks (Python version, packages, Kinesis DLLs, disk space). |
| `estimate_disk_bytes` | Conservative BMP size estimate used for the pre-run disk-space check. |
| `yes_no` | Y/n prompt helper used throughout `01_main.py`. |
| `print_angles` | Prints an angle list next to its motor-angle equivalent, for operator sanity-checking. |

### `state_generator.py` — builds the measurement plan (not run directly)

| Item | What it does |
|---|---|
| `MeasurementState` | One planned move+capture step: index, optical angles, motor angles, output filename. |
| `generate_3x3` | Cartesian product of PSG_Polarizer × PSA_Analyzer angles. |
| `generate_4x4_discrete` | Cartesian product of PSG_QWP × PSA_QWP angles, polarizers held fixed. |

### `motor_controller.py` — Kinesis motor control (not run directly)

| Function | What it does |
|---|---|
| `angular_error_deg` | Shortest angular distance between two wrapped (0–360°) angles. |
| `MotorController.discover` | Lists USB motors and verifies every active motor's `MOTOR_SN` is configured and present. |
| `MotorController.connect_all` / `initialize_all` / `enable_all` / `home_all` | Sequential Kinesis bring-up: connect, load settings profile, enable, home — one motor at a time, never in parallel. |
| `MotorController.move_to_optical_zero_all` | Moves every active motor to its `ZERO_OFFSET`. |
| `MotorController.move_motor_angle` | Moves one axis and verifies the encoder position is within `position_tolerance_deg`, retrying on failure. The core move primitive everything else calls. |
| `MotorController.move_state` | Moves every axis needed for one `MeasurementState`, in a fixed order. |
| `MotorController.encoder_positions` | Reads back current reported positions for all connected motors. |
| `MotorController.emergency_stop` / `close` | Immediate stop (Ctrl-C path) and orderly shutdown (always runs via `finally`). |

### `camera_controller.py` — IDS Peak camera control (not run directly)

| Function | What it does |
|---|---|
| `CameraController.discover` | Briefly opens the camera to read its model/serial, then releases it so Cockpit can be opened. |
| `CameraController.initialize` | Opens the device/data stream once, then applies exposure/gain/frame-rate/pixel-format and starts acquisition. Accepts an optional `ask_settings` callback that re-prompts for exposure/frame rate (without reopening the device) if the camera rejects them — see `CameraSettingsError` below. |
| `CameraController._apply_acquisition_settings` | The retryable part of `initialize()`: applies pixel format/exposure/gain/frame rate and reads back what the camera actually accepted. Raises `CameraSettingsError` if exposure or frame rate is rejected. |
| `CameraController._start_streaming` | The non-retryable part of `initialize()`: switches to software trigger, allocates buffers, and starts acquisition. Only runs once settings are accepted. |
| `CameraController.acquire` | Fires a software trigger and returns one Mono8 frame as a NumPy array. |
| `CameraController.save_bmp` | Writes the frame to disk and computes/prints min/max/mean/saturated-pixel statistics (no correction is ever applied to the pixels). |
| `CameraController.verify_image` | Confirms the saved file is a real, decodable image. |
| `CameraController.acquire_save_verify` | Combines acquire → save → verify with retries; the single entry point every image capture uses. |
| `CameraController.test_frame` | Used for the bright/dark reference shots. |
| `CameraController.close` / `emergency_stop` | Orderly shutdown and Ctrl-C-path immediate stop. Both are best-effort and never raise; they skip the Acquisition-Stop calls entirely if acquisition was never actually started (e.g. `initialize()` failed before `_start_streaming()` ran), since the SDK errors on stopping a stream that was never started. |
| `CameraSettingsError` | Subclass of `CameraError` raised only for a rejected exposure/frame-rate value, so `01_main.py` can retry instead of aborting the whole run. |

### `measurement_engine.py` — the measurement loop (not run directly)

| Item | What it does |
|---|---|
| `EmergencyStopRequested` | Raised when the operator's Ctrl-C stop event is detected mid-run. |
| `MeasurementEngine.run_discrete` | For each `MeasurementState` (skipping already-checkpointed ones): move → settle → trigger/save/verify → log → checkpoint → settle. Writes the final report on the way out regardless of outcome. |

### `logger_manager.py` — logging and reporting (not run directly)

| Item | What it does |
|---|---|
| `SessionTranscript` | Tees stdout/stderr and `input()` prompts/answers into `Logs/terminal_transcript.txt` for the whole session. |
| `ExperimentLogger` | Appends one CSV row per state to `Logs/experiment_log.csv` (commanded vs. reported positions, attempt count, status). |
| `write_report` | Writes the final human-readable `Reports/ExperimentReport.txt` summary. |

### `checkpoint_manager.py` — crash recovery (not run directly)

| Function | What it does |
|---|---|
| `CheckpointManager.load` / `next_index` | Reads the last completed state index (or "nothing done yet"). |
| `CheckpointManager.update` | Records a state as completed, only after its image is verified and logged. |
| `CheckpointManager.complete` | Marks the whole run as finished. |

### `calibration.py` — manual calibration helpers (not run directly, not called by `01_main.py`)

| Function | What it does |
|---|---|
| `move_to_calibration_zero` | Moves one motor to a candidate optical-zero angle so the operator can visually confirm it, before hand-copying the value into `config.ZERO_OFFSET`. |
| `verification_scan` | Sweeps a motor across a list of optical angles and records commanded-vs-encoder pairs, to check calibration accuracy across the full range. |

## Before collecting research data

Verify all of the following:

- Correct serial number is assigned to every optical component.
- Every optical-zero offset has been measured experimentally.
- Motor direction and angle wrapping are correct.
- Reported motor positions remain within the configured tolerance.
- Exposure and gain do not produce black or saturated images.
- The test-frame image has the expected orientation and dimensions.
- Available disk space is sufficient.
- A small real-hardware scan completes successfully before a full scan.
