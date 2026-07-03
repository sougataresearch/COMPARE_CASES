# MMIE Control Software — 4x4 Continuous Rotation

Companion folder to `../discreate_angle/`, which covers 3×3 and 4×4 discrete
acquisition. This folder is **independent** — no shared imports, no shared
run data — because continuous rotation's hardware lifecycle overlaps with
discrete mode (same four motors, same camera) but its acquisition loop does
not: there is no discrete state list, no per-state filename, and no
resumable checkpoint (see `checkpoint_manager.py`).

## Current status

Everything up to the acquisition loop itself is implemented and runs today,
including in dry-run mode:

- Environment verification, hardware bring-up (discover → connect →
  initialize → enable → home → optical zero), same safety-confirmation gates
  as discrete mode.
- Parking `PSG_Polarizer`/`PSA_Analyzer` at the operator's fixed optical
  angle.
- Camera Cockpit-guided setup, initialization, and a reference-frame
  capture.
- Saving `Config/rotation_plan.json` and `Config/experiment_config.json`.

**Not implemented**: the actual continuous-rotation acquisition loop
(`continuous_engine.ContinuousEngine.run_continuous()`). Running
`01_main.py` today gets all the way through camera verification and then
stops with a clear `NotImplementedError` instead of pretending to spin the
QWPs or capture frames.

## The one open decision blocking the acquisition loop

Pick one before implementing `continuous_engine.py`:

- **Frame-rate free-run** — camera free-runs at a fixed fps; after each
  frame, poll both QWP encoders and log their angle against that frame.
- **Angle-triggered** — poll QWP position in a tight loop and fire a
  software trigger every time it crosses a configured angular threshold.

See `continuous_engine.py`'s module docstring for the trade-offs and an
implementation sketch for each option.

## Which file should I run?

```powershell
python 01_main.py
```

Same rule as `discreate_angle/`: run only `01_main.py`. There is no mode
choice here — this folder always runs 4x4 continuous. There is also no
`--resume`; an interrupted continuous run restarts its revolution from
scratch.

## Files

| File | Purpose |
|---|---|
| `01_main.py` | Operator prompts and orchestration (run this file). |
| `config.py` | Motor identities, offsets, camera settings, timing, and the continuous-only velocity/tolerance settings. |
| `utils.py` | Environment checks, run-directory creation, JSON writing, rotation-ratio parsing. |
| `motor_controller.py` | Kinesis discovery/bring-up plus `set_velocity`/`start_continuous`/`stop_continuous` — the primitives the future engine needs. |
| `camera_controller.py` | IDS Peak configuration, software-triggered acquisition, BMP save/verify. |
| `rotation_plan.py` | Serializes the chosen ratio and fixed angles to JSON. |
| `checkpoint_manager.py` | Records progress within a single (non-resumable) revolution. |
| `logger_manager.py` | Transcript, per-frame CSV logging, final report — continuous-shaped columns. |
| `continuous_engine.py` | **The unimplemented acquisition loop.** Read its docstring first. |

## Settings to verify before any real run

`config.py`'s `MOTOR_SN` and `ZERO_OFFSET` are duplicated by hand from
`../discreate_angle/config.py`, not imported — if you recalibrate a motor
or swap hardware, update both files.
