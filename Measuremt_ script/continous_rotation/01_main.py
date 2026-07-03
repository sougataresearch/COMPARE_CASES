"""Interactive entry point for 4x4 CONTINUOUS rotation.

Deliberate duplicate of discreate_angle/01_main.py's orchestration shape
(hardware bring-up, guided camera setup, transcript, error handling) but for
continuous rotation only — there is no 3x3/4x4/discrete mode choice here,
this folder only ever runs one experiment shape. The one thing this file
CANNOT do yet is actually spin the QWPs and capture frames: that is
continuous_engine.ContinuousEngine.run_continuous(), which raises
NotImplementedError until the frame-rate-vs-angle trigger decision is made
(see that module's docstring). Everything up to that point — environment
checks, hardware bring-up, camera verification, plan/config persistence —
is real and runs today, including in dry-run mode.
"""

from __future__ import annotations

import argparse
import signal
import threading
import traceback
from pathlib import Path

from camera_controller import CameraController
from config import ACTIVE_MOTORS, DATA_ROOT, ZERO_OFFSET, ExperimentConfig, ExperimentMetadata
from continuous_engine import ContinuousEngine, EmergencyStopRequested
from logger_manager import SessionTranscript
from motor_controller import MotorController
from rotation_plan import continuous_plan
from utils import check_environment, create_run_directory, parse_ratio, write_json, yes_no


def ask_float(prompt: str) -> float:
    while True:
        try:
            return float(input(prompt).strip())
        except ValueError:
            print("Enter a numeric angle.")


def ask_positive_float(prompt: str, default: float) -> float:
    while True:
        text = input(f"{prompt} [{default:g}]: ").strip()
        try:
            value = default if not text else float(text)
            if value <= 0:
                raise ValueError
            return value
        except ValueError:
            print("Enter a number greater than zero.")


def print_environment_report() -> bool:
    print("\nEnvironment verification")
    all_ok = True
    for name, passed, detail in check_environment():
        print(f"  {'OK' if passed else 'MISSING':7} {name}: {detail}")
        all_ok &= passed
    return all_ok


def confirm_stage(text: str) -> None:
    """Ask a yes/no confirmation before a safety-sensitive step; "no"
    cancels the whole session (KeyboardInterrupt, caught in run_session())."""

    if not yes_no(text):
        raise KeyboardInterrupt("Operator cancelled initialization.")


def configure_experiment(dry_run: bool, run: Path) -> ExperimentConfig:
    """Ask operator/sample/comments, the two fixed polarizer angles, and the
    QWP rotation ratio. Always 4x4 continuous — no mode choice."""

    metadata = ExperimentMetadata(
        operator=input("Operator Name: ").strip(),
        sample=input("Sample Name: ").strip(),
        comments=input("Comments: ").strip(),
    )
    fixed = {
        "PSG_Polarizer": ask_float("Fixed PSG Polarizer optical angle: ") % 360,
        "PSA_Analyzer": ask_float("Fixed PSA Analyzer optical angle: ") % 360,
    }
    while True:
        try:
            ratio = parse_ratio(input("QWP rotation ratio, slow:fast (e.g. 1:5): "))
            break
        except (ValueError, IndexError) as exc:
            print(f"Invalid ratio: {exc}")
    config = ExperimentConfig(
        metadata=metadata,
        run_directory=run,
        dry_run=dry_run,
        fixed_angles=fixed,
        rotation_ratio=ratio,
    )
    write_json(run / "Config" / "rotation_plan.json", continuous_plan(ratio, fixed))
    print(f"Fixed angles: {fixed}")
    print(f"Rotation ratio (PSG_QWP:PSA_QWP): {ratio}")
    return config


def initialize_motors(motors: MotorController) -> None:
    """discover -> connect_all -> initialize_all -> enable_all -> home_all ->
    move_to_optical_zero_all, each behind a confirm_stage. Identical shape to
    discreate_angle's initialize_motors(); after this, all four motors sit
    at optical zero — park_fixed_polarizers() then moves the two polarizers
    to the operator's chosen fixed angle."""

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


def park_fixed_polarizers(motors: MotorController, config: ExperimentConfig) -> None:
    """Move PSG_Polarizer/PSA_Analyzer to their fixed optical angle. They
    never move again for the rest of the run — only the two QWPs rotate."""

    from utils import optical_to_motor

    confirm_stage(
        f"Park PSG_Polarizer at optical {config.fixed_angles['PSG_Polarizer']:.3f}° and "
        f"PSA_Analyzer at optical {config.fixed_angles['PSA_Analyzer']:.3f}°?"
    )
    motors.move_motor_angle(
        "PSG_Polarizer", optical_to_motor(config.fixed_angles["PSG_Polarizer"], ZERO_OFFSET["PSG_Polarizer"])
    )
    motors.move_motor_angle(
        "PSA_Analyzer", optical_to_motor(config.fixed_angles["PSA_Analyzer"], ZERO_OFFSET["PSA_Analyzer"])
    )
    print("Polarizers parked at their fixed optical angle for the whole run.")


def detect_camera(camera: CameraController) -> None:
    """Probe the camera and confirm it before any motor step runs — same
    fail-fast ordering as discreate_angle's detect_camera()."""

    camera.discover()
    confirm_stage("Camera detection succeeded. Continue with hardware initialization?")


def guided_camera_setup(config: ExperimentConfig, camera: CameraController) -> None:
    """Cockpit checks while Python has released the camera. Simpler than
    discreate_angle's version: the analyzer is fixed for the whole run, so
    there is only one bright state to confirm (at the operator's chosen
    fixed angle) rather than a bright/dark pair — a genuine dark reference
    would require moving the analyzer off its fixed angle, which this mode
    deliberately never does mid-run."""

    if config.dry_run:
        print(
            "Dry-run mode: IDS Peak Cockpit checks are simulated and saved camera "
            "defaults are retained."
        )
        return

    confirm_stage("Turn ON the illumination/light source. Is it on?")
    print("\nCAMERA CHECK — FIXED-ANGLE STATE")
    input(
        "Open IDS Peak Cockpit, confirm the image looks as expected at the fixed "
        "polarizer angles, then CLOSE Cockpit and press Enter..."
    )
    confirm_stage("Is IDS Peak Cockpit fully closed?")

    print("\nSELECT EXPERIMENT SETTINGS")
    input(
        "Open IDS Peak Cockpit, choose exposure time and frame rate, write down "
        "both values, then CLOSE Cockpit and press Enter..."
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


def capture_camera_reference(config: ExperimentConfig, camera: CameraController) -> None:
    """Capture one reference image at the fixed polarizer angles (no
    bright/dark pair — see guided_camera_setup())."""

    reference_dir = config.run_directory / "Reports"
    print("Capturing reference frame at the fixed polarizer angles...")
    stats = camera.test_frame(reference_dir / "Reference_fixed_angles.bmp")
    print(f"Reference frame mean intensity: {stats['mean']:.3f}")


def write_error_traceback(run: Path) -> None:
    details = traceback.format_exc()
    path = run / "Logs" / "error_traceback.txt"
    path.write_text(details, encoding="utf-8")
    print(f"Full error traceback saved to: {path}")
    print(details)


def run_session(run: Path) -> int:
    """Top-to-bottom continuous-rotation session. Returns a process exit
    code (0 success/expected-stop, 1 error, 2 blocked by a pre-check,
    130 stopped/cancelled). Structurally mirrors discreate_angle's
    run_session(), minus mode selection, disk-space estimate (continuous has
    no fixed image count ahead of time), and --resume (continuous rotation
    is not resumable — see checkpoint_manager.py)."""

    environment_ok = print_environment_report()
    dry_run = yes_no("Use dry-run mode?", default=not environment_ok)
    if not dry_run and not environment_ok:
        print("Required production dependencies are missing; non-dry operation is unsafe.")
        return 2

    config = configure_experiment(dry_run, run)
    write_json(run / "Config" / "experiment_config.json", config.to_dict())

    if not yes_no("Begin hardware initialization and acquisition?"):
        print(f"Configuration retained at {run}")
        return 0

    stop_event = threading.Event()
    motors = MotorController(ACTIVE_MOTORS, config.timing, dry_run)
    camera = CameraController(config.camera, dry_run)

    def request_stop(_signum, _frame) -> None:
        stop_event.set()
        motors.emergency_stop()
        camera.emergency_stop()

    def ask_camera_settings() -> tuple[float, float]:
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
        detect_camera(camera)
        initialize_motors(motors)
        park_fixed_polarizers(motors, config)
        guided_camera_setup(config, camera)
        write_json(run / "Config" / "experiment_config.json", config.to_dict())
        camera.initialize(ask_settings=ask_camera_settings)
        write_json(run / "Config" / "experiment_config.json", config.to_dict())
        capture_camera_reference(config, camera)
        confirm_stage("Camera verification complete. Start continuous rotation?")
        engine = ContinuousEngine(config, motors, camera, stop_event)
        completed, failed = engine.run_continuous()
        print(f"Continuous run complete: {completed} frames, {failed} failures.")
        print(f"Data directory: {run}")
        return 0
    except NotImplementedError as exc:
        print(f"Continuous acquisition not started: {exc}")
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
        try:
            camera.close()
        except Exception as exc:
            print(f"Camera cleanup warning: {exc}")
        motors.close()


def main() -> int:
    """Process entry point. There is no --resume: continuous rotation is a
    single uninterrupted revolution, not a resumable state list."""

    argparse.ArgumentParser(description=__doc__).parse_args()
    run = create_run_directory(DATA_ROOT)

    transcript = SessionTranscript(run / "Logs" / "terminal_transcript.txt")
    transcript.start()
    try:
        return run_session(run)
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
