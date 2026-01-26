from __future__ import annotations
from pathlib import Path
import pandas as pd

def write_metrics_csv(path: Path, metrics: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({"metric": list(metrics.keys()), "value": list(metrics.values())})
    df.to_csv(path, index=False)
