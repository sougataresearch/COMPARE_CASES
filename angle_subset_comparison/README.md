# angle_subset_comparison

Empirically compares a Mueller matrix reconstruction built from every
possible angle-subset combination against the full over-determined capture
and the known theoretical matrix, one sample at a time (edit
`SAMPLE_DIRECTORY` and rerun per sample). See the sibling folder
`subset_error_analysis/` for the version that scans every sample under
`Data/` automatically instead.

Split by mode, matching `control/matrix/own_code/DISCRETE/{3x3,4x4}`:

- **`3x3/`** — for 3×3 captures (2 rotating polarizers). Minimum acquisition
  is 9 images (3 angles × 3 angles). See `3x3/README.md`.
- **`4x4/`** — for 4×4 discrete captures (fixed polarizers + 2 rotating
  QWPs). Minimum acquisition is 16 images (4 angles × 4 angles). See
  `4x4/README.md`. Not applicable to continuous-rotation 4×4 — see that
  folder's README for why.

Both are fully self-contained (no shared code, no imports from `control/`),
only ever *read* from `Data/`, and use the exact same underlying
calculation to reduce a 3×3 or 4×4 difference matrix to the single number
each `deviation_chart.png` bar shows — see either subfolder's README, or the
root `README.md`, for the full step-by-step derivation of that number (the
Frobenius norm) and how it relates to MSE/RMSE.
