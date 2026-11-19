"""名言卡片插件配置。

纯标准库实现，不依赖 NoneBot，便于离线自检。

所有配置通过 ``QUOTE_CARD_*`` 环境变量读取，全部有默认值：
默认**关闭**、群列表为空（开源版必须显式配置启用群），字体/头像缓存目录默认是相对路径
``data/quote_card/...``（相对于 bot 运行目录），可用环境变量绝对路径覆盖。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_GROUPS = frozenset()  # 开源版默认不开放任何群：必须显式配置 QUOTE_CARD_GROUPS
DEFAULT_COMMAND = "名言"
DEFAULT_MAX_CHARS = 100
DEFAULT_COOLDOWN_SECONDS = 10.0
DEFAULT_AVATAR_CACHE_DIR = "data/quote_card/avatars"
DEFAULT_AVATAR_TTL_HOURS = 6.0
DEFAULT_AVATAR_MAX_FILES = 500
DEFAULT_AVATAR_TIMEOUT = 10.0
DEFAULT_FONT_DIR = "data/quote_card/fonts"
DEFAULT_ACCENT = "gold"

_TRUE_VALUES = {"1", "true", "yes", "y", "on", "enable", "enabled"}
_FALSE_VALUES = {"0", "false", "no", "n", "off", "disable", "disabled"}
_ACCENTS = {"gold", "white"}


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip()


def parse_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return default
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    return default


def parse_int(value: object, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def parse_float(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def parse_id_set(value: object) -> frozenset[int]:
    ids: set[int] = set()
    text = str(value or "")
    for token in text.replace(",", " ").replace(";", " ").split():
        number = parse_int(token, 0)
        if number > 0:
            ids.add(number)
    return frozenset(ids)


@dataclass(frozen=True, slots=True)
class QuoteCardConfig:
    enabled: bool
    groups: frozenset[int]
    command: str
    max_chars: int
    cooldown_seconds: float
    avatar_cache_dir: str
    avatar_ttl_hours: float
    avatar_max_files: int
    avatar_timeout: float
    font_dir: str
    accent: str


def load_config() -> QuoteCardConfig:
    command = _env("QUOTE_CARD_COMMAND", DEFAULT_COMMAND) or DEFAULT_COMMAND
    accent = _env("QUOTE_CARD_ACCENT", DEFAULT_ACCENT).lower()
    if accent not in _ACCENTS:
        accent = DEFAULT_ACCENT
    return QuoteCardConfig(
        enabled=parse_bool(_env("QUOTE_CARD_ENABLED", "false"), False),
        groups=parse_id_set(_env("QUOTE_CARD_GROUPS", "")),
        command=command,
        max_chars=max(10, parse_int(_env("QUOTE_CARD_MAX_CHARS", str(DEFAULT_MAX_CHARS)), DEFAULT_MAX_CHARS)),
        cooldown_seconds=max(
            0.0,
            parse_float(_env("QUOTE_CARD_COOLDOWN_SECONDS", str(DEFAULT_COOLDOWN_SECONDS)), DEFAULT_COOLDOWN_SECONDS),
        ),
        avatar_cache_dir=_env("QUOTE_CARD_AVATAR_CACHE_DIR", DEFAULT_AVATAR_CACHE_DIR),
        avatar_ttl_hours=max(
            0.0,
            parse_float(_env("QUOTE_CARD_AVATAR_TTL_HOURS", str(DEFAULT_AVATAR_TTL_HOURS)), DEFAULT_AVATAR_TTL_HOURS),
        ),
        avatar_max_files=max(
            10, parse_int(_env("QUOTE_CARD_AVATAR_MAX_FILES", str(DEFAULT_AVATAR_MAX_FILES)), DEFAULT_AVATAR_MAX_FILES)
        ),
        avatar_timeout=max(
            1.0, parse_float(_env("QUOTE_CARD_AVATAR_TIMEOUT", str(DEFAULT_AVATAR_TIMEOUT)), DEFAULT_AVATAR_TIMEOUT)
        ),
        font_dir=_env("QUOTE_CARD_FONT_DIR", DEFAULT_FONT_DIR),
        accent=accent,
    )


__all__ = [
    "QuoteCardConfig",
    "load_config",
    "parse_bool",
    "parse_float",
    "parse_id_set",
    "parse_int",
]
