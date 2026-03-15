import json
import time
from typing import Any, Dict, Optional
from .config import AUDIT_LOG_PATH

def write_audit(event: Dict[str, Any]) -> None:
    event = dict(event)
    event.setdefault("ts", int(time.time()))
    line = json.dumps(event, ensure_ascii=False)
    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def safe_truncate(text: Optional[str], limit: int = 500) -> Optional[str]:
    if text is None:
        return None
    if len(text) <= limit:
        return text
    return text[:limit] + "…"
