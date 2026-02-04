import os
from dataclasses import dataclass


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
    log_dir: str
    debug: bool


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def load_settings() -> Settings:
    mysql_port = int(_get_env("MYSQL_PORT", "3306"))
    redis_port = _get_env("REDIS_PORT")
    redis_port_int = int(redis_port) if redis_port else None
    project_root = _get_env(
        "PROJECT_ROOT",
        "/opt/1panel/www/sites/www.cs2ze.org/NERV_CS2ZE",
    )
    static_dir_name = _get_env("STATIC_DIR_NAME", "static")
    log_dir = _get_env("MAP_SIDECAR_LOG_DIR", os.path.join(project_root, "logs"))

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
    )
