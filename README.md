# COMPARE_CASES

Control and analysis software for a Mueller Matrix Imaging Ellipsometer (MMIE)
(`control/`), plus two standalone analysis tools that empirically compare
9-image angle-subset Mueller matrix reconstructions against the full
over-determined capture (`angle_subset_comparison/`, `subset_error_analysis/`).

## Repository layout

```
COMPARE_CASES/
├── control/                    ← MMIE hardware control + Mueller matrix reconstruction
│   ├── Measuremt_ script/
│   │   ├── discreate_angle/       ← 3x3 and 4x4 discrete acquisition (production)
│   │   ├── continous_rotation/    ← 4x4 continuous rotation (independent, WIP)
│   │   ├── MMIE_Control/          ← earlier notebook-based reference implementation
│   │   └── check_config_sync.py   ← standalone: diffs motor calibration between the two folders
│   ├── matrix/                    ← offline Mueller matrix reconstruction from saved images
│   │   ├── NAMING.md               ← the one folder-naming rule, used by every capture
│   │   ├── own_code/
│   │   │   ├── DISCRETE/
│   │   │   │   ├── 3x3/            ← reconstructs a 3x3 Mueller matrix from discrete-angle images
│   │   │   │   └── 4x4/            ← reconstructs a full 4x4 Mueller matrix from discrete-angle images
│   │   │   └── CONTINOUS/
│   │   │       └── 4x4/            ← reconstructs a full 4x4 Mueller matrix from a continuous-rotation run
│   │   ├── tinghuye/                ← earlier from-scratch reconstruction scripts, kept for reference
│   │   └── Mueller_calculation_36_images_method.py  ← reference-paper's canonical 36-image method
│   └── Data/                      ← captured images, organized Data/<date>/<sample-type>/<sample> (gitignored)
├── angle_subset_comparison/    ← single-sample angle-subset vs. theory comparison (see below)
└── subset_error_analysis/      ← multi-sample angle-subset vs. theory comparison (see below)
```

**The whole `control/` project, end to end:** capture images with an
acquisition folder under `control/Measuremt_ script/` → copy that run's
images and config into a sample-labeled folder following
`control/matrix/NAMING.md` → run the matching pipeline under
`control/matrix/own_code/DISCRETE/` or `control/matrix/own_code/CONTINOUS/`
to get a reconstructed Mueller matrix. Each destination has its own README
with a "physics background, from zero" section — together they explain,
from no prior assumed knowledge, what a Stokes vector and a Mueller matrix
are, why the rig rotates the motors it does, and exactly how the images
turn into a matrix.

The two acquisition folders under `control/Measuremt_ script/` are
**deliberately independent** — neither imports from the other, and neither
shares a `Data/` run directory. They cover different experiment shapes and
evolved to have different acquisition loops, so keeping them separate avoids
one mode's control flow leaking into the other's.

### `control/Measuremt_ script/discreate_angle/`

The current, working entry point for **3×3** (2 polarizers) and **4×4
discrete** (2 polarizers + 2 stepped QWPs) Mueller matrix acquisition. Run
`python 01_main.py`. Hardware bring-up (discover/connect/initialize/
enable/home/zero) and camera Cockpit setup happen once per session; the
operator is then looped through as many samples as needed without
restarting the script — each sample gets its own `Data/YYYY-MM-DD_<sample
name>` folder, its own auto-selected bright/dark reference ROI (re-verified
every sample), and a prompt to insert/remove the sample at the right point
so nothing measures with the beam path in the wrong state. A real
acquisition failure offers to skip that sample and continue with the next
one rather than aborting the whole queue; motors rehome and everything
disconnects for real only once the operator is done with all samples.
Retried/verified image acquisition, crash-safe checkpointing (`--resume`,
single-sample only), CSV logging, and a final report per sample round out
the flow. See its own `README.md` for full operator instructions and a
function-by-function reference.

### `control/Measuremt_ script/continous_rotation/`

The entry point for **4×4 continuous rotation only** (a 3×3 continuous mode
— dual rotating linear polarizers, no QWPs — was considered and
deliberately not built), where both QWPs spin continuously at a fixed
revolution ratio (classically 1:5 for a dual-rotating-retarder polarimeter
— see that folder's README) instead of stepping through discrete angles.
Structurally mirrors `discreate_angle/`'s session/multi-sample/disconnect
behavior described above. The acquisition loop (`continuous_engine.py`)
captures with **angle-triggered** timing: the camera fires every time
`PSG_QWP` crosses a configured angular step
(`TimingSettings.capture_angle_step_deg`, default 1°, i.e. 360 frames per
revolution), logging each frame's *actual* polled `PSG_QWP`/`PSA_QWP`
angle — not the nominal threshold — to `Logs/experiment_log.csv`. This was
chosen over frame-rate free-run because the reconstruction side needs
images at known angles regardless of real hardware's velocity ripple; see
that module's docstring for the full reasoning.

### `control/Measuremt_ script/MMIE_Control/`

An earlier, notebook-driven (`NB0`–`NB4`) reference implementation of the
same hardware control, kept for comparison. Not required to run either
folder above.

### `control/matrix/`

Everything here is offline: it reads previously captured images and never
touches the motors or camera. Nothing in `matrix/` is imported by, or
modifies, anything under `Measuremt_ script/`.

- **`NAMING.md`** — the one folder-naming rule every capture should follow
  before either pipeline below can use it (what to call a single run vs. a
  repeat round, and why). Read this first if you're not sure where a run's
  images should live.

- **`own_code/DISCRETE/3x3/`** — reconstructs a sample's 3×3 Mueller matrix
  (linear-polarization sub-block only) from however many PSG/PSA-angle
  images a run actually has, using the real rotation physics of a rotated
  polarizer rather than a fixed-image-count shortcut. Works on any sample —
  air, a polarizer, a QWP, tissue — since the sample's identity never
  enters the code. `main.py` is the one file you run for a single capture;
  `average_rounds.py` aggregates several repeat rounds of the same sample
  into a mean and standard deviation. `validate_against_theory.py` checks
  reconstructions against known-theory samples (air, lp, qwp). See its
  `README.md` for a full physics primer (assuming no prior polarimetry
  background) and a function-by-function walkthrough. Results (from
  `main.py`, `average_rounds.py`, and `validate_against_theory.py`) are
  saved under `Results/`, mirroring the same `<date>/<sample-type>/<sample>`
  path each run has under `Data/`, so the same sample name captured on a
  different date never overwrites an earlier result.

- **`own_code/DISCRETE/4x4/`** — the full 4×4 counterpart for
  `discreate_angle/`'s discrete-angle acquisition: same architecture, same
  usage pattern (`main.py` / `average_rounds.py` / `validate_against_theory.py`),
  but models the rig's fixed-polarizer + rotating-QWP generator/analyzer
  instead, so it can also recover the circular-polarization-coupled entries
  a 3×3 measurement cannot see.

  `own_code/DISCRETE/3x3/` and `own_code/DISCRETE/4x4/` are deliberately
  independent — no shared files, each with its own complete copy of the
  rotation physics, its own image loader (which refuses to run on the other
  mode's data with a clear error), and its own README.

- **`own_code/CONTINOUS/4x4/`** — the 4×4 counterpart for
  `continous_rotation/`'s continuous-rotation acquisition (4×4 only — see
  above). Same physics as `DISCRETE/4x4/` (a verbatim copy of
  `mueller_forward_model.py`) and the same generalized least-squares
  reconstruction, since that fit already handles "however many
  (angle, intensity) samples a run has" with no assumption about a discrete
  grid — a continuous sweep's 360 non-grid samples need no separate
  Fourier/harmonic-analysis step. The one real difference is
  `image_loader.py`: it reads each frame's actual polled angle from
  `Logs/experiment_log.csv` (skipping any frame logged `FAILED`, or a
  `SUCCESS` row with no matching image file) rather than parsing it from
  the filename. See its `README.md` for the full comparison.

- **`tinghuye/`** — earlier from-scratch reconstruction scripts (3×3 and
  4×4, built from a fixed small angle set, plus a theory-vs-experiment
  comparison plot). Kept for reference; superseded in capability by
  `own_code/` (arbitrary image count, real rig integration, calibration
  hooks) but useful as a simpler standalone read of the same math.

- **`Mueller_calculation_36_images_method.py`** — the reference paper's
  original method: reconstructs a 4×4 Mueller matrix from exactly 36 images
  captured at the canonical H/V/P/M/R/L polarization-state combinations
  (a different acquisition pattern from what this rig's `discreate_angle`
  currently produces — see `own_code/4x4/README.md`'s discussion of why),
  plus polar decomposition into diattenuation, polarizance, and
  depolarization maps.

  Based on: S. Obando-Vasquez, A. Doblas, and C. Trujillo, *"Apparatus and
  method to estimate the Mueller matrix in bright-field microscopy,"*
  Applied Optics (2021).

### `control/Measuremt_ script/check_config_sync.py`

Standalone diagnostic (not called by either `01_main.py`) that diffs
`MOTOR_SN`/`ZERO_OFFSET` between the two acquisition folders' `config.py`
files — they're hand-duplicated by design (no shared code), so nothing else
catches them drifting apart after a recalibration or hardware swap in only
one file. Run `python check_config_sync.py` from inside `Measuremt_ script/`
after any hardware change.

## Getting started with `control/`

1. Install Thorlabs Kinesis (64-bit) and the IDS Peak SDK on the lab PC.
2. Pick the acquisition folder matching your experiment (`discreate_angle`
   for 3×3/4×4-discrete, `continous_rotation` for 4×4-continuous) and follow
   its own `README.md` for setup, calibration, and run instructions.
3. Run `python 01_main.py` from inside that folder — always that file, never
   the other modules directly.
4. Use dry-run mode first to verify the full software pipeline without
   touching hardware.
5. Each acquisition folder has a `test_pure_functions.py` covering its
   hardware-independent logic — run `python -m unittest test_pure_functions
   -v` from inside it. A few ROI-selection tests need NumPy and are skipped
   without it (dry-run never exercises that code either).
6. Once you have captured data, run the matching reconstruction pipeline to
   get a Mueller matrix:
   - Discrete 3×3/4×4: copy that run's `Images/` folder and
     `Config/experiment_config.json` into a sample-labeled folder following
     `matrix/NAMING.md`, then run `matrix/own_code/DISCRETE/3x3/main.py` or
     `matrix/own_code/DISCRETE/4x4/main.py` (matching the mode you captured).
   - Continuous 4×4: point `matrix/own_code/CONTINOUS/4x4/main.py`'s
     `RUN_DIRECTORY` at the run folder directly (it reads `Images/`,
     `Logs/experiment_log.csv`, and `Config/experiment_config.json` from
     wherever that folder is — no renaming/copying step required).

   New to the physics behind any of this? Start with the "Physics
   background, from zero" section in
   `control/Measuremt_ script/discreate_angle/README.md` or
   `control/matrix/own_code/DISCRETE/3x3/README.md` — either builds the same
   ideas up from no prior assumed knowledge.

## `angle_subset_comparison/` and `subset_error_analysis/`

Both tools answer the same question: a 3x3 Mueller matrix only needs 9
images (3 PSG angles x 3 PSA angles) to solve for, but a run may capture more
than that (e.g. 36 images at 6x6 angles) for an over-determined fit. Does
using all of them actually reduce error against the known theoretical
matrix, or does some specific 9-image subset (e.g. `(0,30,120)`) do just as
well or better? Each is fully self-contained — its own copy of the
rotation-sandwich physics, image loader, and theoretical-matrix formulas —
and only ever *reads* from `control/Data/`, never writes there. Each folder
also has its own `README.md` with this same walkthrough plus tool-specific
usage instructions.

- **`angle_subset_comparison/`** — processes one sample run at a time (edit
  `SAMPLE_DIRECTORY` in `compare_subsets.py` and rerun per sample).
- **`subset_error_analysis/`** — processes every over-determined run found
  under `control/Data/` automatically in one execution (asks you to confirm
  the discovered run list first, in case a folder is missing).

Both write, per sample, into `Results/<date>/.../<sample>/` (mirroring the
same date/sample-type path as `control/Data/`):
- `matrices.txt` / `matrices.json` — the theoretical matrix, the full
  all-angles reconstruction, and every 9-image subset's actual reconstructed
  Mueller matrix plus its element-wise difference from theory.
- `deviation_chart.png` — one bar chart, every angle combination (plus the
  full-angle capture) sorted so the lowest bar is the combination that
  deviates least from theory.

### How "how far off is this matrix" becomes one number

Every reconstruction gives you a 3×3 matrix, and you're comparing it against
a 3×3 theoretical matrix. That's 9 individual differences — comparing 20
different 9-number spreads by eye to rank subsets isn't practical, so
`deviation_chart.png` needs one number per subset that summarizes "how
different are these two matrices overall."

Take `lp30`'s full 36-image reconstruction as a concrete example (real
numbers, straight out of `matrices.txt`). The theoretical matrix for a
linear polarizer at 30°, and what was actually reconstructed:

```
Theory:                          Reconstructed:
[ 1.0000  0.5000  0.8660 ]       [ 1.0000  0.5185  0.8586 ]
[ 0.5000  0.2500  0.4330 ]       [ 0.5074  0.2649  0.4341 ]
[ 0.8660  0.4330  0.7500 ]       [ 0.8542  0.4415  0.7339 ]
```

**Step 1 — element-wise difference.** Subtract theory from the
reconstruction, element by element (this is exactly the "Difference from
theory" matrix already printed in `matrices.txt`):

```
[  0.0000   0.0185  -0.0074 ]
[  0.0074   0.0149   0.0011 ]
[ -0.0118   0.0085  -0.0161 ]
```

**Step 2 — square every one of the 9 differences**, so negative and
positive errors both count as "bad" instead of canceling out (a +0.02 error
and a -0.02 error are equally wrong, but a plain sum would have them cancel
to 0 and hide the error entirely):

```
0.0000² = 0.00000000     0.0185² = 0.00034225     0.0074² = 0.00005476
0.0074² = 0.00005476     0.0149² = 0.00022201     0.0011² = 0.00000121
0.0118² = 0.00013924     0.0085² = 0.00007225     0.0161² = 0.00025921
```

**Step 3 — add all 9 squared differences together:**

```
0.00034225 + 0.00005476 + 0.00005476 + 0.00022201 + 0.00000121
+ 0.00013924 + 0.00007225 + 0.00025921 = 0.00114569
```

**Step 4 — take the square root**, to undo the squaring from step 2 and
bring the number back to the same scale/units as the original matrix
entries:

```
sqrt(0.00114569) ≈ 0.0338
```

That `0.0338` is exactly the number reported for `lp30`'s full-image
baseline, and it's the same four-step calculation (difference → square →
sum → square root) behind every bar in `deviation_chart.png`. In code, this
whole four-step process is just:

```python
deviation = float(np.linalg.norm(matrix_mean - theory))
```

because `np.linalg.norm` on a 2D array does exactly steps 1–4 for you by
default.

### This number has a name: the Frobenius norm

The quantity computed above — square every element-wise difference, add
them up, square root the sum — is called the **Frobenius norm** of the
difference matrix, written `‖A − B‖_F`:

```
‖A − B‖_F = sqrt( Σ over every row i, column j of (A_ij − B_ij)² )
```

**Why this and not something else?** Think of an ordinary 2D or 3D
distance: the distance between two points `(x1, y1)` and `(x2, y2)` is
`sqrt((x1−x2)² + (y1−y2)²)` — square the difference in each coordinate, add
them, square root. That's the Euclidean distance formula you already know.
The Frobenius norm is *exactly that same formula*, just applied to a matrix
instead of a point — if you took this 3×3 matrix and laid its 9 numbers out
in a single row instead of a grid, the Frobenius norm of the difference is
precisely the ordinary Euclidean distance between those two 9-number lists.
Nothing new is being invented here; it's the most natural way anyone would
generalize "distance between two numbers" to "distance between two grids of
numbers."

This also directly explains why **squaring** matters in step 2 above:
without it, a matrix that's `+0.02` too high in one spot and `−0.02` too low
in another would report zero total error (they'd cancel), even though both
spots are equally wrong. Squaring makes every error contribute positively,
regardless of its sign — the same reason ordinary distance formulas square
differences instead of just summing them.

### Isn't Mean Squared Error (MSE) the usual thing to use?

Yes — and the good news is you don't have to choose between them, because
**they always rank things identically.** MSE and RMSE (root mean squared
error) are the same calculation as the Frobenius norm above, just with one
extra step:

```
MSE  = (1/N) × Σ (A_ij − B_ij)²                <- average the squared differences
RMSE = sqrt(MSE)                                 <- square root, back to original units
Frobenius norm = sqrt(Σ (A_ij − B_ij)²) = sqrt(N) × RMSE
```

where `N` is the number of matrix elements (`N = 9` for a 3×3 matrix). So
for this 3×3 case, Frobenius norm is always exactly `sqrt(9) = 3` times
RMSE — not a different measurement, just a different constant multiplier on
the *same* underlying quantity (`Σ (A_ij − B_ij)²`, the raw sum of squared
errors). Because multiplying every value in a list by the same positive
constant (here, 3) never changes their *order*, ranking subsets by
Frobenius norm gives you the *exact same ranking* you'd get from ranking
them by MSE or RMSE instead. Whichever combo has the lowest Frobenius norm
also has the lowest MSE — always, no exceptions.

So Frobenius norm isn't "better than MSE" in the sense of measuring
something MSE misses — it's the same information, just skipping the
division by `N` and taking the root a step earlier. Two real reasons this
convention (Frobenius norm, not MSE) is what these tools — and the
Mueller-matrix/optics literature generally — report instead:

1. **It's the standard, basis-independent way to describe "distance between
   two matrices."** It has a clean geometric meaning (ordinary Euclidean
   distance, as shown above) and is unaffected by the arbitrary choice of
   how the matrix's elements happen to be arranged into a grid — a property
   MSE also has here, but Frobenius norm is the name and convention you'll
   see used when comparing Mueller matrices in published papers, so
   reporting it here keeps these numbers directly comparable to that
   literature.
2. **It matches the physical units of the matrix elements**, same as RMSE
   does (both are "back in the original units" after undoing the squaring),
   whereas plain MSE is in squared units and harder to interpret at a
   glance — e.g. an MSE of `0.0000011` for `lp30`'s full-image case doesn't
   immediately tell you "typical error is a bit over a hundredth," while
   its Frobenius norm (`0.0338`) or RMSE (`0.0338 / 3 ≈ 0.0113`) does.

If you'd rather think in RMSE terms, converting any number in this
project's output is just dividing by `sqrt(9) = 3` — the ranking of
subsets, and which one "wins," is identical either way.
