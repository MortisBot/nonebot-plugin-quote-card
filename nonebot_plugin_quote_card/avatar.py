"""名言卡片头像下载与文件缓存。

只负责拿被引用消息发送者的 QQ 头像；任何失败都返回 None，由调用方静默处理。
网络访问集中在 :func:`_http_get`，便于测试 monkeypatch，不会在测试中发起真实请求。
"""

from __future__ import annotations

import time
from io import BytesIO
from pathlib import Path

import httpx
from nonebot import logger
from PIL import Image

from .config import QuoteCardConfig

AVATAR_URL = "https://q.qlogo.cn/g?b=qq&nk={uid}&s=640"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; nonebot-plugin-quote-card)"}


def _cache_path(cfg: QuoteCardConfig, user_id: int) -> Path:
    return Path(cfg.avatar_cache_dir) / f"u_{user_id}.img"


def _is_fresh(path: Path, ttl_seconds: float) -> bool:
    try:
        if not path.is_file() or path.stat().st_size < 100:
            return False
        return ttl_seconds <= 0 or (time.time() - path.stat().st_mtime) <= ttl_seconds
    except OSError:
        return False


def _valid_image(data: bytes) -> bool:
    try:
        with Image.open(BytesIO(data)) as im:
            im.verify()
        with Image.open(BytesIO(data)) as im:
            return im.width >= 32 and im.height >= 32
    except Exception:
        return False


def _read_cache(cfg: QuoteCardConfig, user_id: int) -> bytes | None:
    path = _cache_path(cfg, user_id)
    ttl = max(0.0, cfg.avatar_ttl_hours) * 3600.0
    if not _is_fresh(path, ttl):
        return None
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return data if _valid_image(data) else None


def _write_cache(cfg: QuoteCardConfig, user_id: int, data: bytes) -> None:
    path = _cache_path(cfg, user_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    except OSError:
        logger.debug("[quote_card] avatar cache write failed path={}", path)


def _prune_cache(cfg: QuoteCardConfig) -> None:
    root = Path(cfg.avatar_cache_dir)
    try:
        files = [path for path in root.glob("u_*.img") if path.is_file()]
    except OSError:
        return
    if len(files) <= cfg.avatar_max_files:
        return
    try:
        files.sort(key=lambda path: path.stat().st_mtime)
        for path in files[: len(files) - cfg.avatar_max_files]:
            path.unlink(missing_ok=True)
    except OSError:
        return


async def _http_get(url: str, timeout: float) -> bytes:
    """下载头像字节（单独成函数，测试里 monkeypatch 它即可完全离线）。"""
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        resp = await client.get(url, headers=_HEADERS)
        resp.raise_for_status()
        return resp.content


async def fetch_avatar(user_id: int, cfg: QuoteCardConfig) -> bytes | None:
    """优先读缓存；否则下载 QQ 头像。失败一律返回 None。"""
    cached = _read_cache(cfg, user_id)
    if cached is not None:
        return cached

    url = AVATAR_URL.format(uid=user_id)
    try:
        data = await _http_get(url, cfg.avatar_timeout)
    except Exception as exc:  # noqa: BLE001 - 头像失败不影响其它消息
        logger.warning("[quote_card] avatar download failed user={} err={!r}", user_id, exc)
        return None

    if not _valid_image(data):
        logger.warning("[quote_card] avatar invalid user={} bytes={}", user_id, len(data))
        return None

    _write_cache(cfg, user_id, data)
    _prune_cache(cfg)
    return data


__all__ = ["fetch_avatar"]
