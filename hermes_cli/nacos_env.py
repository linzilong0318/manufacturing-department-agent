"""Nacos 配置中心接入：启动时拉取环境变量并注入 os.environ / .env。

与 ``docker/nacos_daemon.py``（服务注册/心跳）互补，本模块负责 Nacos 的
“配置中心”身份：

- 从 Nacos 拉取 data_id 对应的配置文本（KEY=VALUE 行或 YAML ``env:`` 块）；
- 按优先级规则注入 ``os.environ``（覆盖 docker -e 与 .env 的同名键）；
- 将托管区段原子写回 ``~/.hermes/.env``，让直接读文件的下游（如 skill
  脚本里的 ``open('/opt/data/.env')``）同样拿到最新值。

所有失败都是 fail-open：配置中心不可用绝不阻塞启动。

引导变量（必须保留在 ``docker run -e`` 里，无法由 Nacos 自身下发）：

    NACOS_SERVER_ADDRESSES  必填；无此变量则整体跳过
    NACOS_CONFIG_DATA_ID    配置 dataId，默认 ``hermes-agent.env``
    NACOS_CONFIG_GROUP      配置分组，默认取 ``NACOS_GROUP_NAME`` / DEFAULT_GROUP
    NACOS_CONFIG_ENABLED    设为 0/false/no/off 可显式关闭
    NACOS_CONFIG_TIMEOUT_MS 单次拉取超时（毫秒），默认 3000
    NACOS_CONFIG_FILE       落盘目标，默认 ``{HERMES_HOME}/.env``
    NACOS_NAMESPACE / NACOS_USERNAME / NACOS_PASSWORD  复用注册参数

优先级规则（R1-R7）：

    R1  Nacos 中存在的键覆盖 docker -e 与 .env 中的同名键
    R2  值为空串视为未配置，跳过（不覆盖已有值）
    R3  NACOS_* 引导变量不可被 Nacos 配置覆盖（鸡生蛋问题）
    R4  config.py 的 denylist 键（HERMES_HOME/PROFILE/CONFIG/ENV、PATH 等）
        不可被覆盖
    R5  managed scope 钉住的键优先，不可被 Nacos 覆盖
    R6  os.environ 与 .env 文件两个消费路径都注入，缺一不可
    R7  失败 fail-open、进程内幂等；热更新（add_config_watcher）为二期
"""

from __future__ import annotations

import logging
import os
import stat
import tempfile
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

from dotenv import dotenv_values
from utils import atomic_replace, fast_safe_load

logger = logging.getLogger("nacos-config")

# Env var name suffixes that indicate credential values — mirror the set in
# env_loader.py so non-ASCII keys injected from Nacos are sanitized exactly
# like .env-loaded credentials (HTTP headers must be pure ASCII).
_CREDENTIAL_SUFFIXES = ("_API_KEY", "_TOKEN", "_SECRET", "_KEY")

_BEGIN_MARKER = "# === BEGIN NACOS-MANAGED ==="
_END_MARKER = "# === END NACOS-MANAGED ==="

# HERMES_HOME paths already synced during this process.  load_hermes_dotenv()
# runs at import time from several hot modules and per-turn via the gateway
# reload hook; without this guard every reload would hit Nacos + rewrite the
# .env file.  Hot updates are a v2 item (add_config_watcher).
_APPLIED_HOMES: set[str] = set()

_DEFAULT_DATA_ID = "hermes-agent.env"
_DEFAULT_TIMEOUT_MS = 3000
_OFF_FLAGS = frozenset({"0", "false", "no", "off"})


@dataclass(frozen=True)
class _ConfigSource:
    server_addresses: str
    namespace: str
    group: str
    data_id: str
    username: str
    password: str
    timeout_ms: int
    env_path: Path


def reset_nacos_config_cache() -> None:
    """Forget which HERMES_HOME paths have already been synced from Nacos.

    The first ``apply_nacos_config(home_path)`` call in a process pulls the
    config, injects os.environ, and writes the managed .env section, then
    remembers ``home_path`` so subsequent calls are no-ops.  Call this to
    force the next call to re-pull — used by tests.
    """
    _APPLIED_HOMES.clear()


def apply_nacos_config(home_path: str | os.PathLike) -> bool:
    """Pull env vars from Nacos and apply them to os.environ + the .env file.

    Fail-open: any error is logged and swallowed, returning False.  Returns
    True when a Nacos config was successfully applied (or was already applied
    earlier in this process).
    """
    home_key = str(Path(home_path).resolve())
    if home_key in _APPLIED_HOMES:
        return True

    cfg = _load_bootstrap_config(Path(home_path))
    if cfg is None:
        return False
    _APPLIED_HOMES.add(home_key)

    try:
        content = _fetch_config_text(cfg)
    except Exception:  # noqa: BLE001 — config center must never block startup
        logger.warning("Nacos 配置拉取失败（fail-open，忽略）", exc_info=True)
        return False
    if not content or not content.strip():
        logger.warning("Nacos 配置 %s/%s 为空，跳过", cfg.group, cfg.data_id)
        return False

    kv = parse_config_content(content)
    deny = _deny_keys()
    accepted: dict[str, str] = {}
    for key, value in kv.items():
        if not key or key.startswith("NACOS_"):
            continue
        if key in deny:
            continue
        if not value or not value.strip():
            continue
        accepted[key] = value
    if not accepted:
        logger.info("Nacos 配置 %s/%s 无可用的键", cfg.group, cfg.data_id)
        return False

    apply_to_os_environ(accepted)
    write_to_env_file(accepted, cfg.env_path, data_id=cfg.data_id, group=cfg.group)
    logger.info(
        "Nacos 配置已应用（dataId=%s, group=%s）：%d 个键",
        cfg.data_id,
        cfg.group,
        len(accepted),
    )
    return True


def parse_config_content(content: str) -> dict[str, str]:
    """Parse Nacos config text into a flat KEY -> value dict.

    Accepts two formats:

    - dotenv style: ``KEY=VALUE`` lines (quotes, ``#`` comments and blank
      lines handled by python-dotenv; interpolation disabled so ``$``/``%``
      in values are kept literally);
    - YAML with an ``env:`` block: ``env:\\n  KEY: value``.
    """
    text = content.lstrip("\ufeff").lstrip()
    if text.startswith("env:"):
        return _parse_yaml_env(text)
    return _parse_dotenv(text)


def apply_to_os_environ(kv: dict[str, str]) -> None:
    """Inject ``kv`` into os.environ, sanitizing non-ASCII credential values."""
    for key, value in kv.items():
        os.environ[key] = value
    _sanitize_credential_values(kv)


def write_to_env_file(
    kv: dict[str, str],
    env_path: str | os.PathLike,
    *,
    data_id: str,
    group: str,
) -> None:
    """Persist ``kv`` into a NACOS-MANAGED section of the .env file.

    Existing managed sections are replaced in place; non-managed lines
    (user edits, other keys) are preserved.  Writes atomically via a temp
    file + ``utils.atomic_replace`` so a crash mid-write can't corrupt the
    .env, and keeps the original file mode (default 0600).
    """
    env_path = Path(env_path)
    env_path.parent.mkdir(parents=True, exist_ok=True)

    section_lines = [
        _BEGIN_MARKER,
        f"# Source: dataId={data_id}, group={group} — auto-managed by hermes nacos-config.",
        "# 本区段由程序从 Nacos 配置中心拉取并自动维护，手动修改会被覆盖。",
    ]
    section_lines.extend(f"{key}={value}" for key, value in sorted(kv.items()))
    section_lines.append(_END_MARKER)

    old_text = ""
    if env_path.exists():
        old_text = env_path.read_text(encoding="utf-8", errors="replace")

    if not old_text.strip():
        new_lines = section_lines
    else:
        existing = old_text.splitlines()
        begin_idx = next(
            (i for i, ln in enumerate(existing) if ln.startswith(_BEGIN_MARKER)), None
        )
        end_idx = next(
            (i for i, ln in enumerate(existing) if ln.strip() == _END_MARKER), None
        )
        if begin_idx is not None and end_idx is not None and end_idx > begin_idx:
            new_lines = existing[:begin_idx] + section_lines + existing[end_idx + 1 :]
        elif begin_idx is not None:
            new_lines = existing[:begin_idx] + section_lines
        else:
            if existing and existing[-1].strip():
                new_lines = existing + [""] + section_lines
            else:
                new_lines = existing + section_lines

    final_text = "\n".join(new_lines)
    if final_text and not final_text.endswith("\n"):
        final_text += "\n"
    if final_text == old_text:
        return

    fd, tmp = tempfile.mkstemp(dir=str(env_path.parent), prefix=".env_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(final_text)
            f.flush()
            os.fsync(f.fileno())
        mode = 0o600
        try:
            mode = stat.S_IMODE(env_path.stat().st_mode)
        except FileNotFoundError:
            pass
        os.chmod(tmp, mode)
        atomic_replace(tmp, env_path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _load_bootstrap_config(home_path: Path) -> _ConfigSource | None:
    """Build the config-source descriptor from NACOS_* bootstrap env vars."""
    server = os.environ.get("NACOS_SERVER_ADDRESSES", "").strip()
    if not server:
        return None
    enabled = os.environ.get("NACOS_CONFIG_ENABLED", "").strip().lower()
    if enabled in _OFF_FLAGS:
        return None

    data_id = os.environ.get("NACOS_CONFIG_DATA_ID", "").strip() or _DEFAULT_DATA_ID
    group = (
        os.environ.get("NACOS_CONFIG_GROUP", "").strip()
        or os.environ.get("NACOS_GROUP_NAME", "").strip()
        or "DEFAULT_GROUP"
    )
    raw_timeout = os.environ.get("NACOS_CONFIG_TIMEOUT_MS", "").strip()
    try:
        timeout_ms = int(raw_timeout)
    except ValueError:
        timeout_ms = _DEFAULT_TIMEOUT_MS
    env_path = Path(
        os.environ.get("NACOS_CONFIG_FILE", "").strip() or home_path / ".env"
    )
    return _ConfigSource(
        server_addresses=server,
        namespace=os.environ.get("NACOS_NAMESPACE", "").strip(),
        group=group,
        data_id=data_id,
        username=os.environ.get("NACOS_USERNAME", "").strip() or "nacos",
        password=os.environ.get("NACOS_PASSWORD", "").strip() or "nacos",
        timeout_ms=timeout_ms,
        env_path=env_path,
    )


def _fetch_config_text(cfg: _ConfigSource) -> str | None:
    try:
        from nacos import NacosClient
    except ImportError:
        logger.debug("nacos-sdk-python 未安装，跳过 Nacos 配置拉取")
        return None
    client = NacosClient(
        server_addresses=cfg.server_addresses,
        namespace=cfg.namespace or None,
        username=cfg.username,
        password=cfg.password,
    )
    return client.get_config(
        data_id=cfg.data_id, group=cfg.group, timeout=cfg.timeout_ms
    )


def _deny_keys() -> frozenset[str]:
    """Keys that must never be overridden by Nacos config (R3/R4/R5).

    Best-effort: any failure (module not importable, managed dir missing)
    shrinks the deny set but never blocks startup.
    """
    keys: set[str] = set()
    try:
        from hermes_cli.config import _ENV_VAR_NAME_DENYLIST

        keys.update(_ENV_VAR_NAME_DENYLIST)
    except Exception:  # noqa: BLE001 — best-effort
        pass
    try:
        from hermes_cli import managed_scope

        managed_dir = managed_scope.get_managed_dir()
        if managed_dir is not None:
            managed_env = Path(managed_dir) / ".env"
            if managed_env.exists():
                keys.update(dotenv_values(dotenv_path=managed_env, interpolate=False))
    except Exception:  # noqa: BLE001 — best-effort
        pass
    return frozenset(keys)


def _parse_dotenv(text: str) -> dict[str, str]:
    values = dotenv_values(stream=StringIO(text), interpolate=False)
    return {key: str(value) for key, value in values.items() if key and value is not None}


def _parse_yaml_env(text: str) -> dict[str, str]:
    data = fast_safe_load(text) or {}
    env = data.get("env") if isinstance(data, dict) else None
    if not isinstance(env, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in env.items():
        if value is None or isinstance(value, (dict, list)):
            continue
        out[str(key)] = str(value)
    return out


def _sanitize_credential_values(kv: dict[str, str]) -> None:
    for key, value in kv.items():
        if not any(key.endswith(suffix) for suffix in _CREDENTIAL_SUFFIXES):
            continue
        try:
            value.encode("ascii")
        except UnicodeEncodeError:
            os.environ[key] = value.encode("ascii", errors="ignore").decode("ascii")
