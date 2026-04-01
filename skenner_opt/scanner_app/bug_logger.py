"""
Bug logging and crash reporting system for SkennerOpt.

Provides:
- File-based logging with automatic rotation
- Crash/exception capture with stack traces
- System info collection (OS, Python, scanner, etc.)
- Bug report generation (text file export)
- Log viewer for the UI
"""

import os
import sys
import platform
import traceback
import datetime
import logging
import logging.handlers
import json
import shutil
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


# ── Log file setup ──────────────────────────────────────────────────────────

_LOG_DIR: Optional[str] = None
_LOG_FILE: Optional[str] = None
_BUG_REPORT_DIR: Optional[str] = None


def get_log_dir() -> str:
    """Get the log directory path, creating it if needed."""
    global _LOG_DIR
    if _LOG_DIR is None:
        if sys.platform == "win32":
            base = os.environ.get("APPDATA", os.path.expanduser("~"))
        else:
            base = os.path.expanduser("~/.config")
        _LOG_DIR = os.path.join(base, "SkennerOpt", "logs")
        os.makedirs(_LOG_DIR, exist_ok=True)
    return _LOG_DIR


def get_log_file() -> str:
    """Get the current log file path."""
    global _LOG_FILE
    if _LOG_FILE is None:
        _LOG_FILE = os.path.join(get_log_dir(), "skenner_opt.log")
    return _LOG_FILE


def get_bug_report_dir() -> str:
    """Get the bug report export directory."""
    global _BUG_REPORT_DIR
    if _BUG_REPORT_DIR is None:
        _BUG_REPORT_DIR = os.path.join(get_log_dir(), "bug_reports")
        os.makedirs(_BUG_REPORT_DIR, exist_ok=True)
    return _BUG_REPORT_DIR


def setup_file_logging(level: int = logging.DEBUG) -> str:
    """
    Initialize the file-based logging system.
    Creates a rotating log file that keeps up to 5 backups of 5MB each.
    Returns the log file path.
    """
    log_file = get_log_file()

    # Create rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(level)

    # Detailed format for file logs
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    # Add to root logger so all modules log to file
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)

    # Also ensure root logger level allows debug messages through
    if root_logger.level > level:
        root_logger.setLevel(level)

    # Log startup marker
    logger.info("=" * 70)
    logger.info("SkennerOpt session started")
    logger.info(f"Log file: {log_file}")
    logger.info(f"System: {platform.system()} {platform.release()} "
                f"({platform.machine()})")
    logger.info(f"Python: {sys.version}")
    logger.info("=" * 70)

    return log_file


# ── Exception hooking ──────────────────────────────────────────────────────

_original_excepthook = sys.excepthook


def _crash_excepthook(exc_type, exc_value, exc_tb):
    """Global exception handler that logs unhandled crashes."""
    # Format the traceback
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    tb_text = "".join(tb_lines)

    logger.critical("UNHANDLED EXCEPTION — Application crash")
    logger.critical(f"Exception type: {exc_type.__name__}")
    logger.critical(f"Exception value: {exc_value}")
    logger.critical(f"Traceback:\n{tb_text}")

    # Also save a crash dump
    try:
        crash_file = os.path.join(
            get_log_dir(),
            f"crash_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        with open(crash_file, "w", encoding="utf-8") as f:
            f.write(f"SkennerOpt Crash Report\n")
            f.write(f"Time: {datetime.datetime.now().isoformat()}\n")
            f.write(f"System: {platform.system()} {platform.release()}\n")
            f.write(f"Python: {sys.version}\n")
            f.write(f"\n{'=' * 60}\n\n")
            f.write(tb_text)
        logger.info(f"Crash dump saved to: {crash_file}")
    except Exception:
        pass

    # Call original handler
    _original_excepthook(exc_type, exc_value, exc_tb)


def install_crash_handler():
    """Install the global crash handler."""
    sys.excepthook = _crash_excepthook
    logger.info("Crash handler installed")


# ── System information collection ──────────────────────────────────────────

def collect_system_info() -> Dict[str, Any]:
    """Collect system information for bug reports."""
    info = {
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "python_version": sys.version,
        "python_executable": sys.executable,
        "timestamp": datetime.datetime.now().isoformat(),
    }

    # Collect package versions
    packages = {}
    for pkg_name in ["PyQt6", "PIL", "numpy", "cv2", "comtypes", "win32com"]:
        try:
            if pkg_name == "PIL":
                from PIL import __version__
                packages["Pillow"] = __version__
            elif pkg_name == "cv2":
                import cv2
                packages["opencv"] = cv2.__version__
            elif pkg_name == "PyQt6":
                from PyQt6.QtCore import PYQT_VERSION_STR
                packages["PyQt6"] = PYQT_VERSION_STR
            elif pkg_name == "numpy":
                import numpy
                packages["numpy"] = numpy.__version__
            elif pkg_name == "comtypes":
                import comtypes
                packages["comtypes"] = getattr(comtypes, "__version__", "unknown")
            elif pkg_name == "win32com":
                try:
                    import win32com
                    packages["pywin32"] = "installed"
                except ImportError:
                    packages["pywin32"] = "not installed"
        except Exception:
            packages[pkg_name] = "not available"

    info["packages"] = packages

    # Scanner info
    try:
        from .scanner import get_scanner, DemoScanner
        scanner = get_scanner(use_demo=False)
        if isinstance(scanner, DemoScanner):
            info["scanner"] = "No hardware detected (demo mode)"
        else:
            scanners = scanner.list_scanners()
            info["scanner"] = [
                {"name": s.name, "id": s.device_id, "transparency": s.has_transparency}
                for s in scanners
            ]
    except Exception as e:
        info["scanner"] = f"Error detecting scanner: {e}"

    return info


# ── Bug report dataclass ──────────────────────────────────────────────────

@dataclass
class BugReport:
    """Structured bug report."""
    title: str = ""
    description: str = ""
    steps_to_reproduce: str = ""
    expected_behavior: str = ""
    actual_behavior: str = ""
    severity: str = "medium"  # low, medium, high, critical
    category: str = "general"  # general, scanner, processing, ui, crash
    system_info: Dict[str, Any] = field(default_factory=dict)
    log_excerpt: str = ""
    timestamp: str = ""
    app_version: str = "1.0.0"

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.datetime.now().isoformat()
        if not self.system_info:
            self.system_info = collect_system_info()


def read_recent_logs(num_lines: int = 200) -> str:
    """Read the most recent log entries."""
    log_file = get_log_file()
    if not os.path.exists(log_file):
        return "(No log file found)"

    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        # Return the last N lines
        recent = lines[-num_lines:] if len(lines) > num_lines else lines
        return "".join(recent)
    except Exception as e:
        return f"(Error reading log: {e})"


def read_full_log() -> str:
    """Read the entire current log file."""
    log_file = get_log_file()
    if not os.path.exists(log_file):
        return "(No log file found)"
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"(Error reading log: {e})"


def export_bug_report(report: BugReport, output_path: Optional[str] = None) -> str:
    """
    Export a bug report to a text file.
    Returns the path to the exported file.
    """
    if output_path is None:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(get_bug_report_dir(), f"bug_report_{ts}.txt")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("  SkennerOpt Bug Report\n")
        f.write("=" * 70 + "\n\n")

        f.write(f"Date: {report.timestamp}\n")
        f.write(f"App Version: {report.app_version}\n")
        f.write(f"Severity: {report.severity}\n")
        f.write(f"Category: {report.category}\n\n")

        f.write("-" * 70 + "\n")
        f.write(f"Title: {report.title}\n")
        f.write("-" * 70 + "\n\n")

        f.write("DESCRIPTION:\n")
        f.write(f"{report.description}\n\n")

        if report.steps_to_reproduce:
            f.write("STEPS TO REPRODUCE:\n")
            f.write(f"{report.steps_to_reproduce}\n\n")

        if report.expected_behavior:
            f.write("EXPECTED BEHAVIOR:\n")
            f.write(f"{report.expected_behavior}\n\n")

        if report.actual_behavior:
            f.write("ACTUAL BEHAVIOR:\n")
            f.write(f"{report.actual_behavior}\n\n")

        f.write("-" * 70 + "\n")
        f.write("SYSTEM INFORMATION:\n")
        f.write("-" * 70 + "\n")
        for key, value in report.system_info.items():
            if isinstance(value, dict):
                f.write(f"  {key}:\n")
                for k2, v2 in value.items():
                    f.write(f"    {k2}: {v2}\n")
            elif isinstance(value, list):
                f.write(f"  {key}:\n")
                for item in value:
                    f.write(f"    - {item}\n")
            else:
                f.write(f"  {key}: {value}\n")

        f.write(f"\n{'=' * 70}\n")
        f.write("APPLICATION LOG (recent entries):\n")
        f.write("=" * 70 + "\n\n")
        f.write(report.log_excerpt if report.log_excerpt else read_recent_logs(300))
        f.write("\n\n[End of Bug Report]\n")

    logger.info(f"Bug report exported to: {output_path}")
    return output_path


def export_full_log_bundle(output_path: str) -> str:
    """
    Export all log files as a bundle (copies current + rotated logs).
    Returns the output directory.
    """
    os.makedirs(output_path, exist_ok=True)
    log_dir = get_log_dir()

    # Copy all log files
    for fname in os.listdir(log_dir):
        if fname.endswith(".log") or fname.startswith("crash_"):
            src = os.path.join(log_dir, fname)
            dst = os.path.join(output_path, fname)
            try:
                shutil.copy2(src, dst)
            except Exception as e:
                logger.warning(f"Could not copy log file {fname}: {e}")

    # Add system info
    info_path = os.path.join(output_path, "system_info.json")
    try:
        info = collect_system_info()
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2, default=str)
    except Exception as e:
        logger.warning(f"Could not write system info: {e}")

    logger.info(f"Log bundle exported to: {output_path}")
    return output_path


def clear_old_logs(days: int = 30):
    """Remove log files older than the specified number of days."""
    log_dir = get_log_dir()
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)

    for fname in os.listdir(log_dir):
        fpath = os.path.join(log_dir, fname)
        if os.path.isfile(fpath):
            try:
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath))
                if mtime < cutoff:
                    os.remove(fpath)
                    logger.info(f"Removed old log: {fname}")
            except Exception:
                pass
