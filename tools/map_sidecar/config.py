from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass


INDEX_STAMP_KEY = "map_sidecar:index_stamp"
EXG_LAST_INGEST_KEY = "map_sidecar:exg_last_ingest"


@dataclass(frozen=True)
class Settings:
    mysql_host: str
    mysql_port: int
    mysql_db: str
    mysql_user: str
    mysql_password: str
    redis_url: str | None
    redis_host: str | None
    redis_port: int | None
    redis_password: str | None
    main_servers_json_url: str
    project_root: str
    static_dir_name: str
    log_dir: str | None
    debug: bool
    exg_health_max_age_seconds: int


@dataclass(frozen=True)
class IngestSettings:
    bind_host: str
    bind_port: int
    ingest_token: str
    allowlist: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]
    max_bytes: int
    request_timeout_seconds: int


@dataclass(frozen=True)
class CnFetcherSettings:
    project_root: str
    log_dir: str | None
    exg_maplist_url: str
    overseas_ingest_url: str
    ingest_token: str
    debug: bool
    fetch_timeout_seconds: int
    retention_hours: int


def _get_env(name: str, default: str | None = None, allow_empty: bool = False) -> str | None:
    if name not in os.environ:
        return default
    value = os.environ.get(name) or ""
    value = value.strip()
    if value or allow_empty:
        return value
    return default


def load_settings() -> Settings:
    mysql_port = int(_get_env("MYSQL_PORT", "3306"))
    redis_port = _get_env("REDIS_PORT")
    redis_port_int = int(redis_port) if redis_port else None
    project_root = _get_env(
        "PROJECT_ROOT",
        "/opt/1panel/www/sites/www.cs2ze.org/NERV_CS2ZE",
    )
    static_dir_name = _get_env("STATIC_DIR_NAME", "static")
    log_dir = _get_env(
        "MAP_SIDECAR_LOG_DIR",
        os.path.join(project_root, "logs"),
        allow_empty=True,
    )
    if log_dir == "":
        log_dir = None

    return Settings(
        mysql_host=_get_env("MYSQL_HOST", ""),
        mysql_port=mysql_port,
        mysql_db=_get_env("MYSQL_DB", ""),
        mysql_user=_get_env("MYSQL_USER", ""),
        mysql_password=_get_env("MYSQL_PASSWORD", ""),
        redis_url=_get_env("REDIS_URL"),
        redis_host=_get_env("REDIS_HOST"),
        redis_port=redis_port_int,
        redis_password=_get_env("REDIS_PASSWORD"),
        main_servers_json_url=_get_env(
            "MAIN_SERVERS_JSON_URL",
            "https://www.cs2ze.org/servers.json",
        ),
        project_root=project_root,
        static_dir_name=static_dir_name,
        log_dir=log_dir,
        debug=str(_get_env("DEBUG", "false")).lower() in {"1", "true", "yes"},
        exg_health_max_age_seconds=int(_get_env("EXG_HEALTH_MAX_AGE_SECONDS", "7200")),
    )


def load_ingest_settings() -> IngestSettings:
    allowlist_raw = _get_env("INGEST_ALLOWLIST", "") or ""
    allowlist: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for entry in allowlist_raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        allowlist.append(ipaddress.ip_network(entry, strict=False))

    return IngestSettings(
        bind_host=_get_env("INGEST_BIND_HOST", "0.0.0.0"),
        bind_port=int(_get_env("INGEST_BIND_PORT", "8082")),
        ingest_token=_get_env("INGEST_TOKEN", ""),
        allowlist=tuple(allowlist),
        max_bytes=int(_get_env("INGEST_MAX_BYTES", "1048576")),
        request_timeout_seconds=int(_get_env("INGEST_REQUEST_TIMEOUT_SECONDS", "10")),
    )


def load_cn_fetcher_settings() -> CnFetcherSettings:
    project_root = _get_env("PROJECT_ROOT", os.getcwd())
    log_dir = _get_env(
        "MAP_SIDECAR_LOG_DIR",
        os.path.join(project_root, "logs"),
        allow_empty=True,
    )
    if log_dir == "":
        log_dir = None
    return CnFetcherSettings(
        project_root=project_root,
        log_dir=log_dir,
        exg_maplist_url=_get_env("EXG_MAPLIST_URL", "https://list.darkrp.cn:9000/serverlist/cs2maplist"),
        overseas_ingest_url=_get_env("OVERSEAS_INGEST_URL", ""),
        ingest_token=_get_env("INGEST_TOKEN", ""),
        debug=str(_get_env("DEBUG", "false")).lower() in {"1", "true", "yes"},
        fetch_timeout_seconds=int(_get_env("FETCH_TIMEOUT_SECONDS", "15")),
        retention_hours=int(_get_env("RETENTION_HOURS", "72")),
    )


def validate_settings(settings: Settings, require_mysql: bool = True) -> None:
    errors: list[str] = []
    if not settings.project_root:
        errors.append("PROJECT_ROOT is required")
    if settings.mysql_port <= 0 or settings.mysql_port > 65535:
        errors.append("MYSQL_PORT must be between 1 and 65535")
    if require_mysql:
        if not settings.mysql_host:
            errors.append("MYSQL_HOST is required")
        if not settings.mysql_db:
            errors.append("MYSQL_DB is required")
        if not settings.mysql_user:
            errors.append("MYSQL_USER is required")
        if not settings.mysql_password:
            errors.append("MYSQL_PASSWORD is required")
    if errors:
        raise ValueError("; ".join(errors))


def validate_ingest_settings(settings: IngestSettings) -> None:
    errors: list[str] = []
    if not settings.ingest_token:
        errors.append("INGEST_TOKEN is required")
    if settings.bind_port <= 0 or settings.bind_port > 65535:
        errors.append("INGEST_BIND_PORT must be between 1 and 65535")
    if settings.max_bytes <= 0:
        errors.append("INGEST_MAX_BYTES must be positive")
    if errors:
        raise ValueError("; ".join(errors))


def validate_cn_fetcher_settings(settings: CnFetcherSettings, dry_run: bool = False) -> None:
    errors: list[str] = []
    if not settings.project_root:
        errors.append("PROJECT_ROOT is required")
    if not settings.exg_maplist_url:
        errors.append("EXG_MAPLIST_URL is required")
    if not dry_run:
        if not settings.overseas_ingest_url:
            errors.append("OVERSEAS_INGEST_URL is required")
        if not settings.ingest_token:
            errors.append("INGEST_TOKEN is required")
    if errors:
        raise ValueError("; ".join(errors))
