"""Tests for the Nacos config-center env integration (hermes_cli/nacos_env.py)."""

from __future__ import annotations

import os
import shutil

import pytest

from hermes_cli import nacos_env


@pytest.fixture(autouse=True)
def _reset_nacos_cache():
    nacos_env.reset_nacos_config_cache()
    yield
    nacos_env.reset_nacos_config_cache()


# ── parsing ──────────────────────────────────────────────────────────────────


def test_parse_dotenv_content():
    content = (
        "# comment\n"
        "CHINT_API_KEY=sk-123\n"
        "API_SERVER_KEY=\"quoted value\"\n"
        "EMPTY=\n"
        "DOLLAR=$HOME/keep-me\n"
        "\n"
    )
    parsed = nacos_env.parse_config_content(content)
    assert parsed["CHINT_API_KEY"] == "sk-123"
    assert parsed["API_SERVER_KEY"] == "quoted value"
    assert parsed["EMPTY"] == ""
    assert parsed["DOLLAR"] == "$HOME/keep-me"


def test_parse_yaml_env_block():
    content = (
        "env:\n"
        "  CHINT_API_KEY: sk-456\n"
        "  API_SERVER_KEY: 8642\n"
        "  SKIP_ME: null\n"
        "  NESTED:\n"
        "    a: 1\n"
    )
    parsed = nacos_env.parse_config_content(content)
    assert parsed["CHINT_API_KEY"] == "sk-456"
    assert parsed["API_SERVER_KEY"] == "8642"
    assert "SKIP_ME" not in parsed
    assert "NESTED" not in parsed


def test_parse_content_with_utf8_bom():
    parsed = nacos_env.parse_config_content("\ufeffCHINT_API_KEY=sk-789\n")
    assert parsed["CHINT_API_KEY"] == "sk-789"


# ── os.environ injection ─────────────────────────────────────────────────────


def test_apply_to_os_environ_sets_values(monkeypatch):
    monkeypatch.setenv("API_SERVER_KEY", "old")
    nacos_env.apply_to_os_environ({"API_SERVER_KEY": "new", "EXTRA": "1"})
    assert os.getenv("API_SERVER_KEY") == "new"
    assert os.getenv("EXTRA") == "1"


# ── end-to-end apply_nacos_config (fetch monkeypatched) ─────────────────────


def test_apply_nacos_config_injects_and_persists(tmp_path, monkeypatch):
    home = tmp_path / "hermes"
    home.mkdir()
    env_file = home / ".env"
    env_file.write_text("CHINT_API_KEY=old\n", encoding="utf-8")
    monkeypatch.setenv("NACOS_SERVER_ADDRESSES", "127.0.0.1:8848")
    monkeypatch.setenv("NACOS_CONFIG_DATA_ID", "test.env")
    monkeypatch.setenv("CHINT_API_KEY", "old")
    monkeypatch.setenv("API_SERVER_KEY", "old-server")
    monkeypatch.setattr(
        nacos_env,
        "_fetch_config_text",
        lambda cfg: "CHINT_API_KEY=new-key\nAPI_SERVER_KEY=server-key\n",
    )

    assert nacos_env.apply_nacos_config(home) is True

    assert os.getenv("CHINT_API_KEY") == "new-key"
    assert os.getenv("API_SERVER_KEY") == "server-key"
    text = env_file.read_text(encoding="utf-8")
    assert "# === BEGIN NACOS-MANAGED ===" in text
    assert "# === END NACOS-MANAGED ===" in text
    assert "CHINT_API_KEY=new-key" in text
    assert "API_SERVER_KEY=server-key" in text


def test_apply_nacos_config_never_overrides_bootstrap(tmp_path, monkeypatch):
    home = tmp_path / "hermes"
    home.mkdir()
    monkeypatch.setenv("NACOS_SERVER_ADDRESSES", "127.0.0.1:8848")
    monkeypatch.setenv("NACOS_SERVICE_PORT", "8642")
    monkeypatch.setattr(
        nacos_env,
        "_fetch_config_text",
        lambda cfg: "NACOS_SERVICE_PORT=9999\nCHINT_API_KEY=sk-new\n",
    )

    assert nacos_env.apply_nacos_config(home) is True

    assert os.getenv("NACOS_SERVICE_PORT") == "8642"
    assert os.getenv("CHINT_API_KEY") == "sk-new"


def test_apply_nacos_config_never_overrides_denylisted(tmp_path, monkeypatch):
    home = tmp_path / "hermes"
    home.mkdir()
    monkeypatch.setenv("NACOS_SERVER_ADDRESSES", "127.0.0.1:8848")
    monkeypatch.setenv("HERMES_HOME", "/data/real")
    monkeypatch.setattr(
        nacos_env,
        "_fetch_config_text",
        lambda cfg: "HERMES_HOME=/evil\n",
    )

    assert nacos_env.apply_nacos_config(home) is False

    assert os.getenv("HERMES_HOME") == "/data/real"


def test_apply_nacos_config_skips_empty_values(tmp_path, monkeypatch):
    home = tmp_path / "hermes"
    home.mkdir()
    monkeypatch.setenv("NACOS_SERVER_ADDRESSES", "127.0.0.1:8848")
    monkeypatch.setenv("API_SERVER_KEY", "old")
    monkeypatch.setattr(
        nacos_env,
        "_fetch_config_text",
        lambda cfg: "API_SERVER_KEY=\nCHINT_API_KEY=sk-new\n",
    )

    assert nacos_env.apply_nacos_config(home) is True

    assert os.getenv("API_SERVER_KEY") == "old"
    assert os.getenv("CHINT_API_KEY") == "sk-new"


def test_apply_nacos_config_fail_open_when_fetch_raises(tmp_path, monkeypatch):
    home = tmp_path / "hermes"
    home.mkdir()
    monkeypatch.setenv("NACOS_SERVER_ADDRESSES", "127.0.0.1:8848")
    monkeypatch.setenv("CHINT_API_KEY", "old")
    def fetch(cfg):
        raise RuntimeError("nacos down")

    monkeypatch.setattr(nacos_env, "_fetch_config_text", fetch)

    assert nacos_env.apply_nacos_config(home) is False
    assert os.getenv("CHINT_API_KEY") == "old"


def test_apply_nacos_config_skips_when_server_missing(tmp_path, monkeypatch):
    home = tmp_path / "hermes"
    home.mkdir()
    monkeypatch.delenv("NACOS_SERVER_ADDRESSES", raising=False)

    assert nacos_env.apply_nacos_config(home) is False


def test_apply_nacos_config_disabled_explicitly(tmp_path, monkeypatch):
    home = tmp_path / "hermes"
    home.mkdir()
    monkeypatch.setenv("NACOS_SERVER_ADDRESSES", "127.0.0.1:8848")
    monkeypatch.setenv("NACOS_CONFIG_ENABLED", "0")

    assert nacos_env.apply_nacos_config(home) is False


def test_apply_nacos_config_idempotent_within_process(tmp_path, monkeypatch):
    home = tmp_path / "hermes"
    home.mkdir()
    calls: list[str] = []

    def fetch(cfg):
        calls.append(cfg.data_id)
        return "CHINT_API_KEY=sk-new\n"

    monkeypatch.setenv("NACOS_SERVER_ADDRESSES", "127.0.0.1:8848")
    monkeypatch.setattr(nacos_env, "_fetch_config_text", fetch)

    assert nacos_env.apply_nacos_config(home) is True
    assert nacos_env.apply_nacos_config(home) is True
    assert calls == ["hermes-agent.env"]


def test_apply_nacos_config_uses_custom_data_id(tmp_path, monkeypatch):
    home = tmp_path / "hermes"
    home.mkdir()
    calls: list[str] = []

    def fetch(cfg):
        calls.append(cfg.data_id)
        return "CHINT_API_KEY=sk-new\n"

    monkeypatch.setenv("NACOS_SERVER_ADDRESSES", "127.0.0.1:8848")
    monkeypatch.setenv("NACOS_CONFIG_DATA_ID", "manufacturing.env")
    monkeypatch.setattr(nacos_env, "_fetch_config_text", fetch)

    assert nacos_env.apply_nacos_config(home) is True
    assert calls == ["manufacturing.env"]


# ── .env managed-section persistence ─────────────────────────────────────────


def test_write_to_env_file_creates_managed_section(tmp_path):
    env_path = tmp_path / ".env"
    nacos_env.write_to_env_file(
        {"B": "2", "A": "1"}, env_path, data_id="x.env", group="DEFAULT_GROUP"
    )
    text = env_path.read_text(encoding="utf-8")
    assert text.startswith("# === BEGIN NACOS-MANAGED ===")
    assert "A=1" in text
    assert "B=2" in text
    assert text.rstrip().endswith("# === END NACOS-MANAGED ===")


def test_write_to_env_file_replaces_existing_section(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "# === BEGIN NACOS-MANAGED ===\nOLD=1\n# === END NACOS-MANAGED ===\nKEEP=2\n",
        encoding="utf-8",
    )
    nacos_env.write_to_env_file({"NEW": "3"}, env_path, data_id="x", group="DEFAULT_GROUP")
    text = env_path.read_text(encoding="utf-8")
    assert "NEW=3" in text
    assert "OLD=1" not in text
    assert "KEEP=2" in text
    assert text.count("# === BEGIN NACOS-MANAGED ===") == 1


def test_write_to_env_file_preserves_user_lines_when_appending(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("USER_SETTING=1\n", encoding="utf-8")
    nacos_env.write_to_env_file(
        {"NACOS_KEY": "v"}, env_path, data_id="x", group="DEFAULT_GROUP"
    )
    text = env_path.read_text(encoding="utf-8")
    assert "USER_SETTING=1" in text
    assert "NACOS_KEY=v" in text
    assert text.count("# === BEGIN NACOS-MANAGED ===") == 1


def test_write_to_env_file_skips_rewrite_when_unchanged(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("KEEP=1\n", encoding="utf-8")
    calls: list[tuple] = []

    def fake_atomic_replace(tmp, target):
        calls.append(1)
        shutil.copyfile(tmp, target)

    monkeypatch.setattr(nacos_env, "atomic_replace", fake_atomic_replace)

    nacos_env.write_to_env_file(
        {"A": "1"}, env_path, data_id="x", group="DEFAULT_GROUP"
    )
    nacos_env.write_to_env_file(
        {"A": "1"}, env_path, data_id="x", group="DEFAULT_GROUP"
    )
    assert len(calls) == 1
