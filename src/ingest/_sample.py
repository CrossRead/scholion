"""Sample identifier for the pipeline scripts.

Resolution order: the SAMPLE environment variable → the `.sample` file in the
project root → the default value. The real number is never hard-coded: it is
personal, whereas `src/` is a portable layer.
"""
import os
from pathlib import Path


def sample_id(default: str = "SAMPLE") -> str:
    v = os.environ.get("SAMPLE")
    if v and v.strip():
        return v.strip()
    f = Path(__file__).resolve().parents[2] / ".sample"
    if f.exists():
        s = f.read_text(encoding="utf-8").strip()
        if s:
            return s
    return default
