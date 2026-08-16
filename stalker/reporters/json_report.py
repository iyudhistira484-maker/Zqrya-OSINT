"""JSON report exporter."""

import json
from pathlib import Path
from typing import Dict, Any, Optional


def save(result: Dict[str, Any], output_dir: Path, username: str, timestamp: str) -> Optional[Path]:
    """Save investigation results as JSON."""
    try:
        filename = f"stalker_{username}_{timestamp}.json"
        filepath = output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

        return filepath
    except Exception:
        return None
