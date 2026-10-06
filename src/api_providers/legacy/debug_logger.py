import json
import time
from pathlib import Path
from .constants import CONFIG_DIR
from typing import Dict, List


class DebugLogger:
    """Logs API requests and responses for debugging."""

    def __init__(self):
        """Initialize debug logger."""
        self.log_dir = CONFIG_DIR / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logs: List[Dict] = []
        self.max_logs = 100

    def log_request(self, provider: str, method: str, url: str, headers: Dict = None, data: Dict = None) -> None:
        """Log an API request."""
        entry = {
            "timestamp": time.time(),
            "type": "request",
            "provider": provider,
            "method": method,
            "url": url,
            "headers": {k: "[REDACTED]" if k.lower() in ("authorization", "x-api-key", "api-key") else v for k, v in (headers or {}).items()},
            "data": data
        }
        self.logs.insert(0, entry)
        self._trim_logs()
        self._write_to_file(entry)

    def log_response(self, provider: str, status_code: int, response_text: str = "", latency: float = 0.0) -> None:
        """Log an API response."""
        try:
            response_preview = response_text[:500] if response_text else ""
            try:
                json.loads(response_text)
                response_preview = json.loads(response_text)
            except:
                pass
        except:
            response_preview = response_text[:500] if response_text else ""

        entry = {
            "timestamp": time.time(),
            "type": "response",
            "provider": provider,
            "status_code": status_code,
            "response": response_preview,
            "latency": latency
        }
        self.logs.insert(0, entry)
        self._trim_logs()
        self._write_to_file(entry)

    def log_error(self, provider: str, error: str) -> None:
        """Log an error."""
        entry = {
            "timestamp": time.time(),
            "type": "error",
            "provider": provider,
            "error": error
        }
        self.logs.insert(0, entry)
        self._trim_logs()
        self._write_to_file(entry)

    def get_logs(self) -> List[Dict]:
        """Get all logs."""
        return self.logs

    def get_last_request(self, provider: str) -> Dict:
        """Get last request/response pair for a provider."""
        request_log = None
        response_log = None

        for log in self.logs:
            if log["provider"] == provider:
                if log["type"] == "request" and not request_log:
                    request_log = log
                elif log["type"] == "response" and not response_log:
                    response_log = log

                if request_log and response_log:
                    break

        return {"request": request_log, "response": response_log}

    def clear_logs(self) -> None:
        """Clear all logs."""
        self.logs = []

    def _trim_logs(self) -> None:
        """Keep only last max_logs entries."""
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[:self.max_logs]

    def _write_to_file(self, entry: Dict) -> None:
        """Write log entry to file."""
        try:
            log_file = self.log_dir / f"debug_{time.strftime('%Y%m%d')}.json"

            logs = []
            if log_file.exists():
                with open(log_file, 'r') as f:
                    try:
                        logs = json.load(f)
                    except:
                        logs = []

            logs.insert(0, entry)
            logs = logs[:1000]

            with open(log_file, 'w') as f:
                json.dump(logs, f, indent=2, default=str)
        except Exception:
            pass

    def export_logs(self, filepath: str) -> bool:
        """Export logs to file."""
        try:
            with open(filepath, 'w') as f:
                json.dump(self.logs, f, indent=2, default=str)
            return True
        except Exception:
            return False
