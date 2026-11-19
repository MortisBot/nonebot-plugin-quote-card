"""头像下载与缓存单测：网络全部 monkeypatch，禁止真实请求。"""

from __future__ import annotations

from dataclasses import replace
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from nonebot_plugin_quote_card import avatar
from nonebot_plugin_quote_card.config import load_config


def _png_bytes(size: int = 128) -> bytes:
    image = Image.new("RGB", (size, size), (200, 210, 220))
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _cfg(tmp_path: Path):
    return replace(load_config(), avatar_cache_dir=str(tmp_path / "avatars"), avatar_ttl_hours=1.0)


async def test_download_and_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(tmp_path)
    calls: list[str] = []

    async def fake_get(url: str, timeout: float) -> bytes:
        calls.append(url)
        return _png_bytes()

    monkeypatch.setattr(avatar, "_http_get", fake_get)
    data = await avatar.fetch_avatar(10001, cfg)
    assert data is not None
    assert len(data) == len(_png_bytes())
    assert calls and "nk=10001" in calls[0]

    # 第二次命中文件缓存，不再发起下载
    data2 = await avatar.fetch_avatar(10001, cfg)
    assert data2 == data
    assert len(calls) == 1
    assert any(Path(cfg.avatar_cache_dir).glob("u_10001.img"))


async def test_download_failure_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(tmp_path)

    async def boom(url: str, timeout: float) -> bytes:
        raise RuntimeError("network down")

    monkeypatch.setattr(avatar, "_http_get", boom)
    assert await avatar.fetch_avatar(10002, cfg) is None


async def test_invalid_image_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(tmp_path)

    async def garbage(url: str, timeout: float) -> bytes:
        return b"not an image"

    monkeypatch.setattr(avatar, "_http_get", garbage)
    assert await avatar.fetch_avatar(10003, cfg) is None
    # 无效数据不应写入缓存
    assert not any(Path(cfg.avatar_cache_dir).glob("u_10003.img"))


def test_cache_freshness(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    avatar._write_cache(cfg, 10004, _png_bytes())
    assert avatar._read_cache(cfg, 10004) is not None
    # TTL=0 表示不过期
    never_expire = replace(cfg, avatar_ttl_hours=0)
    assert avatar._read_cache(never_expire, 10004) is not None
    # 文件过小视为无效
    small = Path(cfg.avatar_cache_dir) / "u_10005.img"
    small.write_bytes(b"tiny")
    assert avatar._read_cache(cfg, 10005) is None


def test_prune_cache(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    for index in range(12):
        avatar._write_cache(cfg, 20000 + index, _png_bytes())
    pruned = replace(cfg, avatar_max_files=10)
    avatar._prune_cache(pruned)
    files = list(Path(cfg.avatar_cache_dir).glob("u_*.img"))
    assert len(files) == 10
