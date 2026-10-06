import os
import time
from pathlib import Path
from datetime import datetime
from .constants import CONFIG_DIR
from typing import Optional


class FileLogger:
    """Simple file-based logger for debugging and error tracking."""

    def __init__(self):
        """Initialize file logger."""
        self.log_dir = CONFIG_DIR / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "logs.txt"
        self.max_log_size = 5 * 1024 * 1024  # 5MB
        self.max_backups = 5

        self.setup()

    def setup(self):
        """Setup logging on app launch."""
        self.rotate_if_needed()
        self.write_line("=" * 80)
        self.write_line(f"APP LAUNCHED - {self.timestamp()}")
        self.write_line("=" * 80)

    def timestamp(self) -> str:
        """Get formatted timestamp."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def write_line(self, message: str) -> None:
        """Write a line to log file."""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{self.timestamp()}] {message}\n")
        except Exception:
            pass

    def log_info(self, message: str) -> None:
        """Log info message."""
        self.write_line(f"INFO: {message}")

    def log_error(self, message: str, exception: Optional[Exception] = None) -> None:
        """Log error message."""
        if exception:
            self.write_line(f"ERROR: {message} - {str(exception)}")
        else:
            self.write_line(f"ERROR: {message}")

    def log_warning(self, message: str) -> None:
        """Log warning message."""
        self.write_line(f"WARNING: {message}")

    def log_api_request(self, provider: str, method: str, url: str) -> None:
        """Log API request."""
        self.write_line(f"API_REQUEST [{provider}] {method} {url}")

    def log_api_response(self, provider: str, status_code: int, latency: float) -> None:
        """Log API response."""
        self.write_line(f"API_RESPONSE [{provider}] Status: {status_code} Latency: {latency:.0f}ms")

    def log_api_error(self, provider: str, error: str) -> None:
        """Log API error."""
        self.write_line(f"API_ERROR [{provider}] {error}")

    def log_provider_saved(self, provider: str) -> None:
        """Log provider saved."""
        self.write_line(f"PROVIDER_SAVED: {provider}")

    def log_model_fetched(self, provider: str, count: int) -> None:
        """Log models fetched."""
        self.write_line(f"MODELS_FETCHED [{provider}]: {count} models")

    def rotate_if_needed(self) -> None:
        """Rotate log file if it exceeds max size."""
        if not self.log_file.exists():
            return

        try:
            file_size = self.log_file.stat().st_size
            if file_size > self.max_log_size:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = self.log_dir / f"logs_{timestamp}.txt"
                self.log_file.rename(backup_file)
                self.cleanup_old_logs()
        except Exception:
            pass

    def cleanup_old_logs(self) -> None:
        """Clean up old backup logs, keeping only the latest max_backups."""
        try:
            backup_files = sorted(
                self.log_dir.glob("logs_*.txt"),
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )

            for backup_file in backup_files[self.max_backups:]:
                try:
                    backup_file.unlink()
                except Exception:
                    pass
        except Exception:
            pass

    def shutdown(self) -> None:
        """Log app shutdown."""
        self.write_line("=" * 80)
        self.write_line(f"APP SHUTDOWN - {self.timestamp()}")
        self.write_line("=" * 80)
        self.write_line("")

    def read_logs(self) -> str:
        """Read and return current log file contents."""
        try:
            if self.log_file.exists():
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception:
            pass
        return "No logs available"

    def get_recent_logs(self, lines: int = 50) -> str:
        """Get recent log lines."""
        try:
            if self.log_file.exists():
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    all_lines = f.readlines()
                    return ''.join(all_lines[-lines:])
        except Exception:
            pass
        return "No logs available"

    def get_log_files(self) -> list:
        """Get list of all log files."""
        try:
            log_files = []

            if self.log_file.exists():
                stat = self.log_file.stat()
                log_files.append({
                    "name": "logs.txt (current)",
                    "path": str(self.log_file),
                    "size": stat.st_size,
                    "mtime": stat.st_mtime
                })

            for backup_file in sorted(
                self.log_dir.glob("logs_*.txt"),
                key=lambda f: f.stat().st_mtime,
                reverse=True
            ):
                stat = backup_file.stat()
                log_files.append({
                    "name": backup_file.name,
                    "path": str(backup_file),
                    "size": stat.st_size,
                    "mtime": stat.st_mtime
                })

            return log_files
        except Exception:
            return []

    def clear_old_logs(self) -> None:
        """Delete all backup logs, keep only current."""
        try:
            for backup_file in self.log_dir.glob("logs_*.txt"):
                backup_file.unlink()
            self.log_info("Old log files cleaned up")
        except Exception:
            pass
