from __future__ import annotations
from pathlib import Path
import pandas as pd


def write_metrics_csv(path: Path, metrics: dict) -> None:
    """
    Write metrics to a well-formatted CSV file.

    Parameters:
        path: Output CSV path
        metrics: Dictionary of metric name -> value pairs
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dataframe with descriptive columns
    rows = []
    for key, value in metrics.items():
        # Categorize metrics
        if key == "total_errors" or key.startswith("total_"):
            category = "summary"
        elif key.startswith("count_"):
            category = "error_counts"
        elif key.startswith("top_"):
            category = "ranking"
        else:
            category = "other"

        rows.append(
            {
                "category": category,
                "metric": key,
                "value": value,
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
