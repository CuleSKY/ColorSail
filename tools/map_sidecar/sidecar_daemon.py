from __future__ import annotations

import os
import signal
import sys
import time
from typing import Dict, Iterable, Optional

ENV_FILE = "/etc/default/map-sidecar"
DEFAULT_PROJECT_ROOT = "/opt/example-app/NERV_CS2ZE"
PID_FILENAME = "map_sidecar.pid"
LOG_FILENAME = "map_sidecar_daemon.log"


def _load_env_file(path: str) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not os.path.exists(path):
        return env
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"")
            if key:
                env[key] = value
    return env


def _apply_env(env: Dict[str, str]) -> None:
    for key, value in env.items():
        os.environ.setdefault(key, value)


def _get_project_root() -> str:
    return os.environ.get("PROJECT_ROOT", DEFAULT_PROJECT_ROOT)


def _get_log_path(project_root: str) -> Optional[str]:
    log_dir = os.environ.get("MAP_SIDECAR_LOG_DIR", os.path.join(project_root, "logs"))
    if not log_dir:
        return None
    return os.path.join(log_dir, LOG_FILENAME)


def _pid_path(project_root: str) -> str:
    return os.path.join(project_root, "run", PID_FILENAME)


def _read_pid(path: str) -> Optional[int]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = handle.read().strip()
            return int(raw) if raw else None
    except (OSError, ValueError):
        return None


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _write_pid(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(str(os.getpid()))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def _remove_pid(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _tail_lines(path: str, max_lines: int = 200) -> Iterable[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            lines = handle.readlines()
    except OSError:
        return []
    return lines[-max_lines:]


def _run_ingest_foreground() -> int:
    from tools.map_sidecar.config import load_ingest_settings, load_settings, validate_ingest_settings, validate_settings
    from tools.map_sidecar.db import MySQLClient
    from tools.map_sidecar.ingest_server import run_server
    from tools.map_sidecar.logging_utils import setup_logging
    from tools.map_sidecar.redis_cache import RedisCache

    app_settings = load_settings()
    ingest_settings = load_ingest_settings()
    logger = setup_logging(app_settings.log_dir)
    logger.setLevel(20)

    try:
        validate_settings(app_settings, require_mysql=True)
        validate_ingest_settings(ingest_settings)
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    db = MySQLClient(app_settings)
    cache = RedisCache(app_settings)
    return run_server(ingest_settings, app_settings, logger, db, cache, once=False)


def _daemonize(log_path: Optional[str]) -> None:
    if os.fork() > 0:
        os._exit(0)
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    sys.stdin.flush()
    sys.stdout.flush()
    sys.stderr.flush()
    with open("/dev/null", "r", encoding="utf-8") as dev_null:
        os.dup2(dev_null.fileno(), sys.stdin.fileno())
    if log_path:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        log_handle = open(log_path, "a", encoding="utf-8")
        os.dup2(log_handle.fileno(), sys.stdout.fileno())
        os.dup2(log_handle.fileno(), sys.stderr.fileno())
    else:
        with open("/dev/null", "a", encoding="utf-8") as dev_null:
            os.dup2(dev_null.fileno(), sys.stdout.fileno())
            os.dup2(dev_null.fileno(), sys.stderr.fileno())


def _start(project_root: str) -> int:
    pid_file = _pid_path(project_root)
    pid = _read_pid(pid_file)
    if pid and _is_running(pid):
        print(f"map sidecar already running (pid {pid})")
        return 0
    if pid:
        _remove_pid(pid_file)

    log_path = _get_log_path(project_root)
    _daemonize(log_path)
    _write_pid(pid_file)
    try:
        return _run_ingest_foreground()
    finally:
        _remove_pid(pid_file)


def _foreground(project_root: str) -> int:
    pid_file = _pid_path(project_root)
    pid = _read_pid(pid_file)
    if pid and _is_running(pid):
        print(f"map sidecar already running (pid {pid})")
        return 1
    _write_pid(pid_file)
    try:
        return _run_ingest_foreground()
    finally:
        _remove_pid(pid_file)


def _stop(project_root: str) -> int:
    pid_file = _pid_path(project_root)
    pid = _read_pid(pid_file)
    if not pid:
        print("map sidecar not running")
        return 0
    if not _is_running(pid):
        print("map sidecar not running (stale pid)")
        _remove_pid(pid_file)
        return 0
    os.kill(pid, signal.SIGTERM)
    timeout = time.time() + 10
    while time.time() < timeout:
        if not _is_running(pid):
            _remove_pid(pid_file)
            print("map sidecar stopped")
            return 0
        time.sleep(0.2)
    print("map sidecar did not stop in time; sending SIGKILL")
    os.kill(pid, signal.SIGKILL)
    _remove_pid(pid_file)
    return 0


def _status(project_root: str) -> int:
    pid = _read_pid(_pid_path(project_root))
    if pid and _is_running(pid):
        print(f"map sidecar running (pid {pid})")
        return 0
    print("map sidecar not running")
    return 1


def _logs(project_root: str) -> int:
    log_path = _get_log_path(project_root)
    if not log_path or not os.path.exists(log_path):
        print("log file not configured or missing")
        return 1
    for line in _tail_lines(log_path):
        sys.stdout.write(line)
    return 0


def main() -> int:
    env = _load_env_file(ENV_FILE)
    _apply_env(env)
    project_root = _get_project_root()

    if len(sys.argv) < 2:
        print("Usage: sidecar_daemon.py start|stop|restart|status|foreground|logs")
        return 1

    command = sys.argv[1]
    if command == "start":
        return _start(project_root)
    if command == "stop":
        return _stop(project_root)
    if command == "restart":
        _stop(project_root)
        return _start(project_root)
    if command == "status":
        return _status(project_root)
    if command == "foreground":
        return _foreground(project_root)
    if command == "logs":
        return _logs(project_root)

    print(f"Unknown command: {command}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
