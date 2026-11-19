"""配置解析单测：默认值安全化（默认关闭、群列表为空、相对数据目录）与环境变量覆盖。"""

from __future__ import annotations

import pytest

from nonebot_plugin_quote_card import config


def test_defaults_are_safe() -> None:
    cfg = config.load_config()
    assert cfg.enabled is False
    assert cfg.groups == frozenset()
    assert cfg.command == "名言"
    assert cfg.max_chars == 100
    assert cfg.cooldown_seconds == 10.0
    assert cfg.avatar_ttl_hours == 6.0
    assert cfg.avatar_max_files == 500
    assert cfg.avatar_timeout == 10.0
    assert cfg.accent == "gold"
    # 默认路径必须是相对路径（不写死任何部署机绝对路径）
    assert cfg.font_dir == "data/quote_card/fonts"
    assert cfg.avatar_cache_dir == "data/quote_card/avatars"
    assert not cfg.font_dir.startswith("/")


def test_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUOTE_CARD_ENABLED", "true")
    monkeypatch.setenv("QUOTE_CARD_GROUPS", "10000, 10001; 10002")
    monkeypatch.setenv("QUOTE_CARD_COMMAND", "引用一下")
    monkeypatch.setenv("QUOTE_CARD_MAX_CHARS", "50")
    monkeypatch.setenv("QUOTE_CARD_COOLDOWN_SECONDS", "3")
    monkeypatch.setenv("QUOTE_CARD_AVATAR_CACHE_DIR", "/tmp/qc-avatars")
    monkeypatch.setenv("QUOTE_CARD_AVATAR_TTL_HOURS", "1.5")
    monkeypatch.setenv("QUOTE_CARD_AVATAR_MAX_FILES", "20")
    monkeypatch.setenv("QUOTE_CARD_AVATAR_TIMEOUT", "2.5")
    monkeypatch.setenv("QUOTE_CARD_FONT_DIR", "/tmp/qc-fonts")
    monkeypatch.setenv("QUOTE_CARD_ACCENT", "white")
    cfg = config.load_config()
    assert cfg.enabled is True
    assert cfg.groups == frozenset({10000, 10001, 10002})
    assert cfg.command == "引用一下"
    assert cfg.max_chars == 50
    assert cfg.cooldown_seconds == 3.0
    assert cfg.avatar_cache_dir == "/tmp/qc-avatars"
    assert cfg.avatar_ttl_hours == 1.5
    assert cfg.avatar_max_files == 20
    assert cfg.avatar_timeout == 2.5
    assert cfg.font_dir == "/tmp/qc-fonts"
    assert cfg.accent == "white"


def test_clamping_and_invalid_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUOTE_CARD_MAX_CHARS", "1")
    monkeypatch.setenv("QUOTE_CARD_COOLDOWN_SECONDS", "-5")
    monkeypatch.setenv("QUOTE_CARD_AVATAR_MAX_FILES", "1")
    monkeypatch.setenv("QUOTE_CARD_AVATAR_TIMEOUT", "0")
    monkeypatch.setenv("QUOTE_CARD_ACCENT", "purple")
    cfg = config.load_config()
    assert cfg.max_chars == 10  # 最小 10
    assert cfg.cooldown_seconds == 0.0  # 负数归零
    assert cfg.avatar_max_files == 10  # 最小 10
    assert cfg.avatar_timeout == 1.0  # 最小 1
    assert cfg.accent == "gold"  # 非法颜色回退


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", True),
        ("1", True),
        ("YES", True),
        ("on", True),
        ("false", False),
        ("0", False),
        ("off", False),
        ("", False),
        ("whatever", False),
    ],
)
def test_parse_bool(raw: str, expected: bool) -> None:
    assert config.parse_bool(raw, default=False) is expected


def test_parse_id_set() -> None:
    assert config.parse_id_set("10000,10001; 10002") == frozenset({10000, 10001, 10002})
    assert config.parse_id_set("") == frozenset()
    assert config.parse_id_set("abc, -3, 0") == frozenset()
    assert config.parse_id_set("10000 10000") == frozenset({10000})
