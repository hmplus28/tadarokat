import math
from typing import Any

import pandas as pd


def json_safe(val: Any) -> Any:
    if isinstance(val, dict):
        return {k: json_safe(v) for k, v in val.items()}
    if isinstance(val, list):
        return [json_safe(v) for v in val]
    if isinstance(val, tuple):
        return [json_safe(v) for v in val]
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(val, "item"):
        try:
            return json_safe(val.item())
        except (ValueError, AttributeError):
            pass
    if isinstance(val, bool):
        return val
    return val


def records_json_safe(df) -> list:
    if df is None or getattr(df, "empty", True):
        return []
    rows = df.to_dict(orient="records")
    return [json_safe(r) for r in rows]