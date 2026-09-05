# PHOENIX biomechanics

`preprocessing.py` is the first non-clinical part of stage 8. It validates a
shared three-sensor time window, resamples raw axes on a deterministic grid and
applies a versioned, centered moving-average filter. It runs only when Signal
Quality permits it. It deliberately does not perform
sensor fusion, knee-angle estimation, rep segmentation, ML interpretation,
scoring or patient feedback: each needs an approved device protocol and a
validated calibration method.

`orientation.py` contains isolated quaternion mathematics and can retain an
adapter's declared Euler orientation as research-only data. It requires an
explicit orientation baseline for both sensors before it can produce a generic
relative orientation. It does not infer anatomical axes or a knee angle.

Run its tests from the repository root:

```powershell
python -m unittest discover -s services/biomechanics/tests -v
```
