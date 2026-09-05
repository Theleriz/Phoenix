"""Run the development-only synthetic replay without installing this package."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
runpy.run_module("phoenix_imu_gateway.synthetic", run_name="__main__")
