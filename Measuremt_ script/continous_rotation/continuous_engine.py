"""The (not yet implemented) continuous-rotation acquisition loop.

This is the ONE piece of continuous mode that is intentionally not built —
everything around it (hardware bring-up, plan saving, checkpoint/logger
scaffolding) is ready and wired up in 01_main.py so that implementing
run_continuous() below is the only remaining step once the trigger scheme is
decided.

Open decision (must be made before writing the loop):
  (a) FRAME-RATE capture — camera free-runs at a fixed fps (hardware
      trigger / continuous acquisition, not software-triggered per frame);
      after each frame, poll both QWP encoder positions and log them
      against that frame. Simple to implement, but frame-to-angle mapping
      has jitter equal to whatever the poll/frame timing skew is.
  (b) ANGLE-triggered capture — poll PSG_QWP (and/or PSA_QWP) position in a
      tight loop and fire a software trigger (CameraController.acquire())
      every time it crosses a configured angular threshold. Precise angle
      labeling, but the achievable frame rate is bounded by how fast the
      position-poll + software-trigger round trip is.

Implementation sketch once a scheme is chosen:
  1. motors.move_motor_angle() the two polarizers to their fixed angles
     (already done by 01_main.park_fixed_polarizers() before this runs).
  2. motors.move_motor_angle() both QWPs to a known starting angle (0).
  3. motors.set_velocity() for both QWPs using config.TimingSettings
     .base_angular_velocity_deg_s and the configured rotation_ratio.
  4. motors.start_continuous() on both QWPs (PSG_QWP direction defines
     "forward" for the revolution-completion check below).
  5. Loop: capture per the chosen scheme above; after each frame, call
     checkpoints.record_frame() and logger.log(); check stop_event via the
     same _ensure_running() pattern discreate_angle/measurement_engine.py
     uses, so Ctrl-C still calls motors.emergency_stop()/camera.emergency_stop().
  6. Detect one full PSG_QWP revolution (position returns within
     config.TimingSettings.revolution_tolerance_deg of its start angle)
     and call motors.stop_continuous() on both QWPs.
  7. checkpoints.complete(), write_report(), same as discrete mode.
"""

from __future__ import annotations

import threading

from camera_controller import CameraController
from checkpoint_manager import CheckpointManager
from config import ExperimentConfig, ROTATING_MOTORS
from logger_manager import ExperimentLogger, write_report
from motor_controller import MotorController


class EmergencyStopRequested(RuntimeError):
    """Raised when the operator's Ctrl-C stop event is detected mid-run.
    Mirrors discreate_angle/measurement_engine.EmergencyStopRequested."""


class ContinuousEngine:
    """Owns the (future) continuous-rotation acquisition loop.

    Constructed the same way as discreate_angle's MeasurementEngine so that
    01_main.py's hardware bring-up and cleanup code is structurally similar
    across both folders, even though nothing here shares an import.
    """

    def __init__(
        self,
        config: ExperimentConfig,
        motors: MotorController,
        camera: CameraController,
        stop_event: threading.Event | None = None,
    ) -> None:
        self.config = config
        self.motors = motors
        self.camera = camera
        self.stop_event = stop_event or threading.Event()
        self.checkpoints = CheckpointManager(config.run_directory / "Checkpoints" / "checkpoint.json")
        self.logger = ExperimentLogger(config.run_directory / "Logs" / "experiment_log.csv")

    def run_continuous(self) -> tuple[int, int]:
        """Spin PSG_QWP/PSA_QWP through one PSG_QWP revolution, capturing
        frames per the (not yet chosen) trigger scheme documented above.

        Raises NotImplementedError on purpose — see the module docstring
        for the two implementation options and the sketch of what this
        method should do once one is picked. Left as a real exception
        (not a silent no-op) so a run started from 01_main.py fails loudly
        here instead of pretending to succeed.
        """

        raise NotImplementedError(
            "Continuous-rotation acquisition is not implemented yet: the "
            "frame-rate-free-run vs angle-triggered capture decision has not "
            "been made. See continuous_engine.py's module docstring for the "
            "two options and the implementation sketch. Rotating motors: "
            f"{', '.join(ROTATING_MOTORS)}."
        )
