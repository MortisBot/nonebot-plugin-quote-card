"""图片渲染单测：系统 DejaVu 字体、纯 Pillow、不联网。

conftest 的 ``font_dir`` fixture 会把 DejaVu 字体按插件约定文件名软链到临时目录；
彩色 emoji 字体缺失时走普通字体回退（与开源版默认部署一致）。
"""

from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from nonebot_plugin_quote_card import parse, render


def fake_avatar(size: int = 640) -> bytes:
    image = Image.new("RGB", (size, size), (206, 220, 205))
    draw = ImageDraw.Draw(image)
    for y in range(size):
        draw.line([(0, y), (size, y)], fill=(206 - y // 12, 220 - y // 16, 205 - y // 14))
    draw.ellipse([140, 120, 500, 480], fill=(246, 233, 226))
    draw.ellipse([215, 300, 275, 360], fill=(140, 120, 90))
    draw.ellipse([365, 300, 425, 360], fill=(140, 120, 90))
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def assert_png(png: bytes) -> None:
    assert isinstance(png, bytes)
    assert len(png) > 2_000  # 非空 PNG
    with Image.open(BytesIO(png)) as im:
        assert im.size == (render.W, render.H) == (1280, 720)
        im.verify()


def quote_units(text: str) -> list[tuple[str, str]]:
    reply = type("Reply", (), {"message": [type("Seg", (), {"type": "text", "data": {"text": text}})()]})()
    return parse.extract_quote_units(reply)


def test_validate_assets(font_dir: str, tmp_path: Path) -> None:
    # 软链目录里只有必需字体，没有彩色 emoji 字体
    assert render.missing_required_fonts(font_dir) == []
    assert render.validate_assets(font_dir) == [render.EMOJI_FONT_FILE]
    missing_dir = tmp_path / "no-fonts"
    assert len(render.validate_assets(str(missing_dir))) == 3
    assert len(render.missing_required_fonts(str(missing_dir))) == 2


def test_font_missing_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(render.RenderError, match="字体"):
        render.render_quote_card(fake_avatar(), quote_units("测试"), "群友", font_dir=str(tmp_path / "no-fonts"))


def test_render_text_gold(font_dir: str) -> None:
    png = render.render_quote_card(
        fake_avatar(), quote_units("周一开组会诗人吗"), "若叶睦", accent="gold", font_dir=font_dir
    )
    assert_png(png)


def test_render_text_white(font_dir: str) -> None:
    png = render.render_quote_card(
        fake_avatar(), quote_units("周一开组会诗人吗"), "若叶睦", accent="white", font_dir=font_dir
    )
    assert_png(png)


def test_render_emoji_fallback(font_dir: str) -> None:
    """彩色 emoji 字体缺失：emoji 单元回退普通字体，仍能正常出图。"""
    units = quote_units("笑死😭这也太真实了🎉")
    assert any(kind == "emoji" for kind, _ in units)
    png = render.render_quote_card(fake_avatar(), units, "若叶睦", font_dir=font_dir)
    assert_png(png)
    # 缺失的 emoji 字体路径不应抛异常，只返回 None（走回退）
    assert render._emoji_glyph("😭", os.path.join(font_dir, "NotoColorEmoji.ttf")) is None


def test_render_qq_face_placeholder(font_dir: str) -> None:
    units = quote_units("笑死[微笑]真的")
    png = render.render_quote_card(fake_avatar(), units, "若叶睦", font_dir=font_dir)
    assert_png(png)


def test_render_signature_units(font_dir: str) -> None:
    card_units = parse.signature_units("群星怒，请随意使用♡")
    png = render.render_quote_card(fake_avatar(), quote_units("测试署名"), card_units, font_dir=font_dir)
    assert_png(png)


def test_render_long_text(font_dir: str) -> None:
    long_text = (
        "今天晚上谁去教三上有机化学，顺便帮我带一份夜宵，我要加辣，谢谢兄弟们，"
        "另外记得带上实验报告，明天早上八点之前要交，不然就要被老师点名了，"
        "大家互相提醒一下，别忘了😭"
    )
    units = parse.middle_ellipsis_units(quote_units(long_text), 100)
    png = render.render_quote_card(fake_avatar(), units, "若叶睦", font_dir=font_dir)
    assert_png(png)


def test_render_empty_raises(font_dir: str) -> None:
    with pytest.raises(render.RenderError, match="empty"):
        render.render_quote_card(fake_avatar(), [], "群友", font_dir=font_dir)


def test_render_bad_avatar_raises(font_dir: str) -> None:
    with pytest.raises(render.RenderError, match="invalid avatar"):
        render.render_quote_card(b"not an image", quote_units("测试"), "群友", font_dir=font_dir)


def test_font_index_fallback(font_dir: str) -> None:
    """软链的 TTC 名字 + TTF 内容：index=2 失败时自动回退 index=0。"""
    font = render._load_font(os.path.join(font_dir, render.QUOTE_FONT_FILE), 32, render.QUOTE_FONT_INDEX)
    assert font.getlength("测试") > 0
