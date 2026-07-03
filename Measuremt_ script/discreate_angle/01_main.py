"""Interactive entry point for the Mueller Matrix Imaging Ellipsometer."""

from __future__ import annotations

import argparse
import json
import shutil
import signal
import threading
import time
import traceback
from pathlib import Path

from camera_controller import CameraController
from config import (
    ACTIVE_MOTORS,
    DATA_ROOT,
    ZERO_OFFSET,
    ExperimentConfig,
    ExperimentMetadata,
)
from measurement_engine import EmergencyStopRequested, MeasurementEngine
from logger_manager import SessionTranscript
from motor_controller import MotorController
from state_generator import generate_3x3, generate_4x4_discrete
from utils import (
    check_environment,
    create_run_directory,
    estimate_disk_bytes,
    parse_angle_spec,
    print_angles,
    optical_to_motor,
    write_json,
    yes_no,
)


# -----------------------------------------------------------------------
# Small input helpers — each loops until the operator gives a valid answer.
# -----------------------------------------------------------------------

def ask_choice(prompt: str, choices: set[str]) -> str:
    """Ask until the operator types one of ``choices`` exactly (e.g. "1"/"2")."""

    while True:
        answer = input(prompt).strip()
        if answer in choices:
            return answer
        print(f"Enter one of: {', '.join(sorted(choices))}")


def ask_float(prompt: str) -> float:
    """Ask until the operator types a parseable float (used for single
    fixed polarizer angles in 4x4 mode)."""

    while True:
        try:
            return float(input(prompt).strip())
        except ValueError:
            print("Enter a numeric angle.")


def ask_positive_float(prompt: str, default: float) -> float:
    """Ask for a positive runtime setting while showing the saved default."""

    while True:
        text = input(f"{prompt} [{default:g}]: ").strip()
        try:
            value = default if not text else float(text)
            if value <= 0:
                raise ValueError
            return value
        except ValueError:
            print("Enter a number greater than zero.")


def ask_angles(prompt: str) -> list[float]:
    """Ask until utils.parse_angle_spec() accepts the text (either "360/step"
    or a comma-separated angle list). Used for every PSG/PSA/QWP angle-list prompt."""

    while True:
        try:
            return parse_angle_spec(input(prompt).strip())
        except ValueError as exc:
            print(f"Invalid angle specification: {exc}")


def choose_mode_first() -> str:
    """Ask 3x3 vs 4x4. Returns "3x3" or "4x4".

    This is intentionally the first input call: active hardware depends on it.
    Everything downstream (which motors get discovered/connected/homed, which
    ACTIVE_MOTORS entry is used) is decided by this single choice.
    """

    print("1 : 3×3 Mueller Matrix")
    print("2 : 4×4 Mueller Matrix")
    return "3x3" if ask_choice("Select measurement mode: ", {"1", "2"}) == "1" else "4x4"


def print_environment_report() -> bool:
    """Run utils.check_environment() and print an OK/MISSING line per check.
    Returns True only if every check passed. The return value feeds directly
    into the dry-run default and the "can we run for real" gate in run_session()."""

    print("\nEnvironment verification")
    all_ok = True
    for name, passed, detail in check_environment():
        print(f"  {'OK' if passed else 'MISSING':7} {name}: {detail}")
        all_ok &= passed
    return all_ok


def configure_experiment(mode: str, dry_run: bool, run: Path) -> tuple[ExperimentConfig, list]:
    """Interactively collect everything needed to build an ExperimentConfig
    and the matching list of MeasurementState objects, for a FRESH (non
    --resume) run.

    Flow: ask operator/sample/comments -> branch on ``mode``:
      - "3x3": ask PSG_Polarizer and PSA_Analyzer angle lists, preview both,
        generate_3x3() builds the states.
      - "4x4": ask the two fixed polarizer angles, then ask PSG_QWP/PSA_QWP
        angle lists and generate_4x4_discrete().
    This folder only ever produces discrete states. 4x4 continuous rotation
    lives entirely in the separate continous_rotation/ folder.
    Returns (config, states).
    """

    metadata = ExperimentMetadata(
        operator=input("Operator Name: ").strip(),
        sample=input("Sample Name: ").strip(),
        comments=input("Comments: ").strip(),
    )

    if mode == "3x3":
        psg = ask_angles("PSG Polarizer angles (e.g. 360/10 or 0,30,60): ")
        psa = ask_angles("PSA Analyzer angles: ")
        print_angles("PSG Polarizer", psg, ZERO_OFFSET["PSG_Polarizer"])
        print_angles("PSA Analyzer", psa, ZERO_OFFSET["PSA_Analyzer"])
        states = generate_3x3(psg, psa)
        config = ExperimentConfig(
            mode=mode,
            metadata=metadata,
            run_directory=run,
            dry_run=dry_run,
            state_inputs={"PSG_Polarizer": psg, "PSA_Analyzer": psa},
        )
    else:
        fixed = {
            "PSG_Polarizer": ask_float("Fixed PSG Polarizer optical angle: ") % 360,
            "PSA_Analyzer": ask_float("Fixed PSA Analyzer optical angle: ") % 360,
        }
        psg = ask_angles("PSG QWP angles: ")
        psa = ask_angles("PSA QWP angles: ")
        print_angles("PSG QWP", psg, ZERO_OFFSET["PSG_QWP"])
        print_angles("PSA QWP", psa, ZERO_OFFSET["PSA_QWP"])
        states = generate_4x4_discrete(psg, psa, fixed)
        config = ExperimentConfig(
            mode=mode,
            metadata=metadata,
            run_directory=run,
            dry_run=dry_run,
            fixed_angles=fixed,
            state_inputs={"PSG_QWP": psg, "PSA_QWP": psa},
        )
    print(f"Total states: {len(states)}")
    return config, states


def states_from_config(config: ExperimentConfig) -> list:
    """Rebuild deterministic states for an explicit ``--resume`` run.

    Mirrors configure_experiment()'s state-generation branch, but reads the
    angle lists back from config.state_inputs/fixed_angles (saved in
    Config/experiment_config.json) instead of asking the operator again —
    this is what guarantees a resumed run reproduces the exact same
    MeasurementState list (and therefore the same filenames/indices) as the
    original run, so the checkpoint's last_completed_index still lines up.
    """

    if config.mode == "3x3":
        return generate_3x3(
            config.state_inputs["PSG_Polarizer"],
            config.state_inputs["PSA_Analyzer"],
        )
    return generate_4x4_discrete(
        config.state_inputs["PSG_QWP"],
        config.state_inputs["PSA_QWP"],
        config.fixed_angles,
    )


def confirm_stage(text: str) -> None:
    """Ask a yes/no confirmation before a safety-sensitive step; treats "no"
    as a full cancellation (raises KeyboardInterrupt, caught in run_session()'s
    except clause, which stops motors and exits cleanly)."""

    if not yes_no(text):
        raise KeyboardInterrupt("Operator cancelled initialization.")


def initialize_motors(motors: MotorController) -> None:
    """Run the full hardware bring-up sequence for the active motors, with
    an operator confirmation gate before each stage:
    discover -> connect_all -> initialize_all -> enable_all -> home_all ->
    move_to_optical_zero_all. Called once from run_session(), after the
    disk-space check and the "Begin hardware initialization?" confirmation.
    See motor_controller.py for what each stage does on the device side.
    """

    motors.discover()
    confirm_stage("Continue with the listed devices?")
    motors.connect_all()
    confirm_stage("All active motors connected. Initialize them sequentially?")
    motors.initialize_all()
    confirm_stage("Initialization complete. Enable motors?")
    motors.enable_all()
    confirm_stage("Motors enabled. Home active motors?")
    motors.home_all()
    confirm_stage("Homing complete. Move to configured optical zero offsets?")
    motors.move_to_optical_zero_all()


def move_analyzer_to_optical(
    motors: MotorController, config: ExperimentConfig, optical_angle: float
) -> None:
    """Move the analyzer using its configured optical-zero calibration.

    Converts ``optical_angle`` to a motor angle with ZERO_OFFSET["PSA_Analyzer"],
    commands the move, then sleeps timing.settling_before_s. Used by the
    guided camera-check sequence (bright at optical 0, dark at optical 90)
    and by capture_camera_references() — never during the main measurement
    loop, which instead goes through motor_controller.move_state().
    """

    motor_angle = optical_to_motor(optical_angle, ZERO_OFFSET["PSA_Analyzer"])
    print(
        f"Moving PSA Analyzer to optical {optical_angle:.3f}° "
        f"(motor {motor_angle:.3f}°)."
    )
    motors.move_motor_angle("PSA_Analyzer", motor_angle)
    time.sleep(config.timing.settling_before_s)


def detect_camera(config: ExperimentConfig, camera: CameraController) -> None:
    """Probe the camera and confirm it before any motor step runs.

    Called first from run_session(), before initialize_motors(), so a
    missing/broken camera aborts the session immediately instead of after
    motors have already been connected, initialized, enabled, and homed —
    homing especially takes real time, and there is no point spending it if
    the camera was never going to work this run. Only camera.discover()
    runs here (a brief open-then-release probe); the camera is not actually
    opened for acquisition until guided_camera_setup()'s Cockpit checks are
    done and CameraController.initialize() is called.
    """

    model, serial = camera.discover()
    config.camera.model = model
    config.camera.serial_number = serial
    confirm_stage("Camera detection succeeded. Continue with hardware initialization?")


def guided_camera_setup(
    config: ExperimentConfig,
    motors: MotorController,
    camera: CameraController,
) -> None:
    """Guide Cockpit checks while Python has released the camera.

    Called once from run_session(), after motors reach optical zero and
    before camera.initialize(). Camera presence was already confirmed
    earlier by detect_camera(), before any motor step. Sequence (see README
    "Camera preparation before every experiment" for the operator-facing
    version):
      1. Light-source reminder — operator confirms the illumination is on
         before any Cockpit check, since every check below needs it.
      2. Bright check at PSG=0, PSA=0 — operator opens Cockpit, confirms
         bright, closes Cockpit.
      3. Move PSA_Analyzer to optical 90 (move_analyzer_to_optical) — dark
         check — operator opens Cockpit, confirms darker, closes Cockpit.
      4. Move PSA_Analyzer back to optical 0.
      5. Operator opens Cockpit one more time to pick exposure/frame rate,
         writes both numbers down, closes Cockpit.
      6. ask_positive_float() collects those two numbers into
         config.camera.exposure_us / frame_rate_fps (still just requested
         values — nothing has touched the real camera driver yet; that
         happens later in CameraController.initialize()).
    Dry-run mode skips every Cockpit prompt and keeps the saved defaults.
    """

    if config.dry_run:
        print(
            "Dry-run mode: IDS Peak Cockpit checks are simulated and saved camera "
            "defaults are retained."
        )
        return

    confirm_stage("Turn ON the illumination/light source. Is it on?")

    print("\nCAMERA CHECK 1 — BRIGHT STATE")
    print("PSG Polarizer and PSA Analyzer are at optical 0°.")
    input(
        "Open IDS Peak Cockpit, confirm the 0_0 image is bright, then CLOSE "
        "Cockpit and press Enter..."
    )
    confirm_stage("Is IDS Peak Cockpit fully closed?")

    move_analyzer_to_optical(motors, config, 90.0)
    print("\nCAMERA CHECK 2 — DARK STATE")
    input(
        "Open IDS Peak Cockpit, confirm the 0_90 image is darker, then CLOSE "
        "Cockpit and press Enter..."
    )
    confirm_stage("Is IDS Peak Cockpit fully closed?")

    move_analyzer_to_optical(motors, config, 0.0)
    print("\nCAMERA CHECK 3 — SELECT EXPERIMENT SETTINGS")
    input(
        "Open IDS Peak Cockpit at 0_0, choose exposure time and frame rate, "
        "write down both values, then CLOSE Cockpit and press Enter..."
    )
    confirm_stage("Is IDS Peak Cockpit fully closed?")

    exposure_ms = ask_positive_float(
        "Exposure time selected in IDS Peak Cockpit (ms)",
        config.camera.exposure_us / 1000.0,
    )
    frame_rate_fps = ask_positive_float(
        "Frame rate selected in IDS Peak Cockpit (fps)",
        config.camera.frame_rate_fps,
    )
    config.camera.exposure_us = exposure_ms * 1000.0
    config.camera.frame_rate_fps = frame_rate_fps
    print(f"Requested experiment exposure: {exposure_ms:.3f} ms")
    print(f"Requested experiment frame rate: {frame_rate_fps:.3f} fps")


def capture_camera_references(
    config: ExperimentConfig,
    motors: MotorController,
    camera: CameraController,
) -> None:
    """Capture quantitative bright/dark references without modifying pixels.

    Called once from run_session(), after camera.initialize() and before
    the measurement loop starts. Moves to PSA optical 0 (bright) and 90
    (dark), saves each as a real BMP via camera.test_frame(), computes the
    bright/dark mean ratio, and — for real (non-dry-run) hardware — warns
    (and asks for confirmation to continue) if the bright reference isn't
    actually brighter than dark, or if it contains saturated (255) pixels.
    This is the software's only automatic sanity check that the polarizers
    are actually crossed/aligned correctly before committing to a full scan.
    """

    reference_dir = config.run_directory / "Results"
    move_analyzer_to_optical(motors, config, 0.0)
    print("Capturing bright reference at PSG=0°, PSA=0°...")
    bright = camera.test_frame(reference_dir / "BrightReference_0_0.bmp")

    move_analyzer_to_optical(motors, config, 90.0)
    print("Capturing dark reference at PSG=0°, PSA=90°...")
    dark = camera.test_frame(reference_dir / "DarkReference_0_90.bmp")
    move_analyzer_to_optical(motors, config, 0.0)

    bright_mean = float(bright["mean"])
    dark_mean = float(dark["mean"])
    contrast = float("inf") if dark_mean == 0 else bright_mean / dark_mean
    print(
        f"Polarization reference result — bright mean: {bright_mean:.3f}, "
        f"dark mean: {dark_mean:.3f}, bright/dark ratio: {contrast:.3f}"
    )
    if config.dry_run:
        print(
            "Dry-run mode: reference files and statistics were verified, but "
            "physical polarization contrast cannot be evaluated."
        )
        return

    problems = []
    if bright_mean <= dark_mean:
        problems.append("bright-reference mean is not greater than dark-reference mean")
    if int(bright["saturated_pixels"]) > 0:
        problems.append(
            f"bright reference contains {bright['saturated_pixels']} pixels at 255"
        )
    if problems:
        print("CAMERA VERIFICATION WARNING: " + "; ".join(problems))
        confirm_stage("Continue despite the camera verification warning?")
    else:
        print("Camera bright/dark and saturation verification passed.")


def write_error_traceback(run: Path) -> None:
    """Persist the full active exception while also showing it in the transcript.

    Must be called from inside an ``except`` block (relies on
    traceback.format_exc() reading the currently-handled exception). Called
    from both run_session()'s and main()'s except clauses, writing
    Logs/error_traceback.txt.
    """

    details = traceback.format_exc()
    path = run / "Logs" / "error_traceback.txt"
    path.write_text(details, encoding="utf-8")
    print(f"Full error traceback saved to: {path}")
    print(details)


def run_session(
    arguments: argparse.Namespace,
    run: Path,
    resumed_config: ExperimentConfig | None,
) -> int:
    """Run one fully transcripted operator session — the top-level flow
    described in the README's sequence diagram, from mode selection through
    the final report. Returns a process exit code (0 success, 1 error,
    2 blocked by a pre-check, 130 stopped/cancelled).

    High-level steps:
      1. Mode: choose_mode_first() for a fresh run, or take it from
         resumed_config for --resume (so a resume can never switch modes
         mid-experiment).
      2. print_environment_report() + dry-run choice (forced True if the
         environment isn't production-ready).
      3. configure_experiment() (fresh) or states_from_config() (resume) to
         get the ExperimentConfig and MeasurementState list.
      4. Disk-space check (utils.estimate_disk_bytes vs shutil.disk_usage).
      5. "Begin hardware initialization and acquisition?" confirmation.
      6. Build MotorController/CameraController, install the SIGINT
         (Ctrl-C) handler that triggers stop_event + emergency stops.
      7. initialize_motors() -> guided_camera_setup() -> camera.initialize()
         -> capture_camera_references() -> final confirmation ->
         MeasurementEngine.run_discrete(states).
      8. Always (success or failure): camera.close() and motors.close() in
         the ``finally`` block.
    Errors: EmergencyStopRequested/KeyboardInterrupt return 130; any other
    exception stops the motors, writes the traceback, and returns 1.
    """

    # Fresh experiments ask mode first. Resumed experiments intentionally obtain it
    # from the immutable saved configuration, preventing an incompatible selection.
    if resumed_config is not None:
        config = resumed_config
        mode = config.mode
    else:
        mode = choose_mode_first()
    environment_ok = print_environment_report()
    dry_run = config.dry_run if resumed_config is not None else yes_no(
        "Use dry-run mode?", default=not environment_ok
    )
    if not dry_run and not environment_ok:
        print("Required production dependencies are missing; non-dry operation is unsafe.")
        return 2

    if resumed_config is not None:
        states = states_from_config(config)
        print(f"Resuming saved {mode} experiment: {run}")
    else:
        config, states = configure_experiment(mode, dry_run, run)
        write_json(run / "Config" / "experiment_config.json", config.to_dict())

    estimate = estimate_disk_bytes(len(states))
    free = shutil.disk_usage(run).free
    print(f"Estimated image space: {estimate / 1024**3:.2f} GB; free: {free / 1024**3:.2f} GB")
    if estimate > free:
        print("Insufficient disk space for the planned images.")
        return 2
    if not yes_no("Begin hardware initialization and acquisition?"):
        print(f"Configuration retained at {run}")
        return 0

    stop_event = threading.Event()
    motors = MotorController(ACTIVE_MOTORS[mode], config.timing, dry_run)
    camera = CameraController(config.camera, dry_run)

    def request_stop(_signum, _frame) -> None:
        stop_event.set()
        # Stop immediately instead of waiting for the blocking state operation to
        # return. Both calls are best-effort and safe when running without hardware.
        motors.emergency_stop()
        camera.emergency_stop()

    def ask_camera_settings() -> tuple[float, float]:
        """CameraController.initialize()'s retry callback: re-prompt for
        exposure/frame rate after the camera rejected the previous values,
        so a bad/swapped value doesn't force redoing motor homing/connecting.
        See camera_controller.CameraSettingsError."""

        exposure_ms = ask_positive_float(
            "Exposure time (ms)", config.camera.exposure_us / 1000.0
        )
        frame_rate_fps = ask_positive_float(
            "Frame rate (fps)", config.camera.frame_rate_fps
        )
        print(
            f"Retrying with exposure {exposure_ms:.3f} ms, "
            f"frame rate {frame_rate_fps:.3f} fps."
        )
        return exposure_ms * 1000.0, frame_rate_fps

    signal.signal(signal.SIGINT, request_stop)
    try:
        detect_camera(config, camera)
        initialize_motors(motors)
        guided_camera_setup(config, motors, camera)
        # Save operator-selected values before opening the camera, then save again
        # after initialization to include the actual values read back from hardware.
        write_json(run / "Config" / "experiment_config.json", config.to_dict())
        camera.initialize(ask_settings=ask_camera_settings)
        write_json(run / "Config" / "experiment_config.json", config.to_dict())
        capture_camera_references(config, motors, camera)
        confirm_stage("Camera verification complete. Start the measurement?")
        engine = MeasurementEngine(config, motors, camera, stop_event)
        completed, failed = engine.run_discrete(states)
        print(f"Experiment complete: {completed} images, {failed} failures.")
        print(f"Data directory: {run}")
        return 0
    except EmergencyStopRequested as exc:
        print(exc)
        return 130
    except KeyboardInterrupt:
        motors.emergency_stop()
        print("Cancelled by operator.")
        return 130
    except Exception as exc:
        motors.emergency_stop()
        print(f"Experiment aborted: {type(exc).__name__}: {exc}")
        write_error_traceback(run)
        return 1
    finally:
        # camera.close() is defensive and should never raise, but a second
        # failure here must still never prevent motors.close() from running —
        # skipping it left the Kinesis connections undisconnected before.
        try:
            camera.close()
        except Exception as exc:
            print(f"Camera cleanup warning: {exc}")
        motors.close()


def main() -> int:
    """Process entry point (called from ``if __name__ == "__main__"`` at the
    bottom of this file). Parses --resume, opens the run directory (new or
    existing), wraps the whole session in a SessionTranscript so every print
    and prompt is captured to Logs/terminal_transcript.txt, and delegates to
    run_session(). This is the ONLY function that should be invoked to start
    the program — see README "Which file should I run?".
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resume",
        type=Path,
        metavar="RUN_DIRECTORY",
        help="resume an existing run from its checkpoint instead of creating a new run",
    )
    arguments = parser.parse_args()

    resumed_config: ExperimentConfig | None = None
    if arguments.resume:
        run = arguments.resume.resolve()
        config_path = run / "Config" / "experiment_config.json"
        if not config_path.is_file():
            parser.error(f"saved configuration does not exist: {config_path}")
        resumed_config = ExperimentConfig.from_dict(
            json.loads(config_path.read_text(encoding="utf-8"))
        )
        # The command-line path is authoritative if the folder was moved.
        resumed_config.run_directory = run
    else:
        # Creating the run before the first question lets the transcript capture
        # mode selection and every later terminal interaction.
        run = create_run_directory(DATA_ROOT)

    transcript = SessionTranscript(run / "Logs" / "terminal_transcript.txt")
    transcript.start()
    try:
        return run_session(arguments, run, resumed_config)
    except KeyboardInterrupt:
        print("Session cancelled before hardware acquisition.")
        return 130
    except Exception as exc:
        print(f"Unhandled session error: {type(exc).__name__}: {exc}")
        write_error_traceback(run)
        return 1
    finally:
        transcript.stop()


if __name__ == "__main__":
    raise SystemExit(main())
