"""名言卡片图片渲染。

纯 Pillow 实现，不 import NoneBot，便于离线自检 / 预渲染。
版式（v3 定稿）：
  - 头像不画框，按画布高度铺满左侧当底图，向右渐变压黑；
  - 视觉居中补偿：右侧渐变压暗会让人觉得脸偏右，整体左移 AVATAR_X；
  - 正文用中文字体 Bold，``「」`` 包住被引用消息内容（引号暖金色点缀）；
  - 下方破折号 + 群名片小字用中文字体 Regular；
  - Unicode emoji 优先用彩色 emoji 字体渲染为内联图；QQ 表情由解析层转成 [微笑] 文本。

字体约定（可替换成任意 FreeType 字体，只需改成对应文件名/放到同一目录）::

    QUOTE_CARD_FONT_DIR（默认 data/quote_card/fonts）/
      NotoSerifCJK-Bold.ttc      必需，正文
      NotoSerifCJK-Regular.ttc   必需，署名
      NotoColorEmoji.ttf         可选；缺失时 emoji 回退为普通字体渲染

必需字体缺失时抛 :class:`RenderError`（带路径与配置提示）；彩色 emoji 字体缺失只降级不报错。
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from io import BytesIO

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

DEFAULT_FONT_DIR = os.environ.get("QUOTE_CARD_FONT_DIR", "data/quote_card/fonts")

# 思源宋体 = Noto Serif CJK（Adobe/Google 同一套字形）；TTC 内索引 2 = SC
QUOTE_FONT_FILE = "NotoSerifCJK-Bold.ttc"
QUOTE_FONT_INDEX = 2
ATTR_FONT_FILE = "NotoSerifCJK-Regular.ttc"
ATTR_FONT_INDEX = 2
# 彩色 emoji 字体（Noto Color Emoji，CBDT 位图字体，FreeType 只接受其固定字号 109）
EMOJI_FONT_FILE = "NotoColorEmoji.ttf"
EMOJI_NATIVE_SIZE = 109
EMOJI_SCALE = 1.0
EMOJI_GAP = 2

# 必需字体（缺失即渲染失败）；彩色 emoji 字体可选，缺失时 emoji 自动回退普通字体
REQUIRED_FONT_FILES = (QUOTE_FONT_FILE, ATTR_FONT_FILE)
OPTIONAL_FONT_FILES = (EMOJI_FONT_FILE,)

W, H = 1280, 720
MARGIN_RIGHT = 96
AVATAR_W = H  # 头像按画布高度缩放，铺满左侧
AVATAR_X = -50  # 视觉居中补偿：整体左移，抵消右侧渐变压暗造成的偏右感
GRAD_START = 120  # 从这个 x 开始压黑
GRAD_END = 600  # 到这里完全黑
TEXT_LEFT = 620
TEXT_RIGHT = W - MARGIN_RIGHT
TEXT_WIDTH = TEXT_RIGHT - TEXT_LEFT

QUOTE_MAX_FONT = 64
QUOTE_MIN_FONT = 28
LINE_SPACING = 1.46
ATTR_FONT_SIZE = 30
ATTR_EMOJI_SCALE = 1.0
ATTR_GAP = 40
BG_BRIGHTNESS = 0.95

ACCENTS = {
    "gold": (226, 188, 118, 255),
    "white": (242, 242, 242, 255),
}
QUOTE_COLOR = (243, 241, 238, 255)
ATTR_COLOR = (176, 178, 182, 255)

# 中文排版禁则：不让收尾标点出现在行首、不让开引号孤零零挂在行尾
NO_LINE_START = set("，。！？、；：」』）》〉…—·,.;:!?)]}")
NO_LINE_END = set("「『（《〈([{")

_UNIT = tuple[str, str]
_font_cache: dict[tuple[str, int, int], ImageFont.FreeTypeFont] = {}
_emoji_glyph_cache: dict[str, Image.Image] = {}


class RenderError(Exception):
    """图片渲染失败（输入不可用等）。"""


def validate_assets(font_dir: str | None = None) -> list[str]:
    """检查字体资源是否齐全，返回缺失文件名列表（含可选的彩色 emoji 字体）。"""
    root = font_dir or DEFAULT_FONT_DIR
    return [
        name
        for name in (QUOTE_FONT_FILE, ATTR_FONT_FILE, EMOJI_FONT_FILE)
        if not os.path.isfile(os.path.join(root, name))
    ]


def missing_required_fonts(font_dir: str | None = None) -> list[str]:
    """检查**必需**字体是否齐全；彩色 emoji 字体缺失不算错误（会自动回退）。"""
    root = font_dir or DEFAULT_FONT_DIR
    return [name for name in REQUIRED_FONT_FILES if not os.path.isfile(os.path.join(root, name))]


def _font_paths(font_dir: str | None = None) -> tuple[str, str, str]:
    root = font_dir or DEFAULT_FONT_DIR
    return (
        os.path.join(root, QUOTE_FONT_FILE),
        os.path.join(root, ATTR_FONT_FILE),
        os.path.join(root, EMOJI_FONT_FILE),
    )


def _load_font(path: str, size: int, index: int = 0) -> ImageFont.FreeTypeFont:
    """加载字体；TTC 集合索引不可用时回退到 index=0。

    字体缺失/损坏时抛出带路径与配置提示的 RenderError，而不是底层 OSError。
    """
    key = (path, size, index)
    font = _font_cache.get(key)
    if font is not None:
        return font

    def _fail() -> RenderError:
        return RenderError(
            f"无法加载字体 {path!r}（size={size}, index={index}）：文件缺失或不是有效字体。"
            "请把字体放到 QUOTE_CARD_FONT_DIR 指向的目录（默认 data/quote_card/fonts）。"
        )

    try:
        font = ImageFont.truetype(path, size, index=index)
    except OSError:
        if index == 0:
            raise _fail() from None
        try:
            font = ImageFont.truetype(path, size, index=0)
        except OSError:
            raise _fail() from None
    _font_cache[key] = font
    return font


def _emoji_glyph(sequence: str, emoji_font_path: str) -> Image.Image | None:
    """把 emoji 序列渲染成原生尺寸的 RGBA 图（带缓存）。

    彩色字体缺失/没有该字形时（如 ``♡``/``★``）返回 None，调用方回退普通字体绘制；
    不会因为可选字体缺失而让整张卡片渲染失败。
    """
    if sequence in _emoji_glyph_cache:
        return _emoji_glyph_cache[sequence]

    glyph: Image.Image | None = None
    if os.path.isfile(emoji_font_path):
        try:
            font = _load_font(emoji_font_path, EMOJI_NATIVE_SIZE)
            canvas = Image.new("RGBA", (EMOJI_NATIVE_SIZE * 4, EMOJI_NATIVE_SIZE * 2), (0, 0, 0, 0))
            draw = ImageDraw.Draw(canvas)
            draw.text((2, 2), sequence, font=font, embedded_color=True)
            bbox = canvas.getbbox()
            glyph = canvas.crop(bbox) if bbox else None
        except Exception:  # noqa: BLE001 - 彩色字体异常一律回退普通字体
            glyph = None

    if len(_emoji_glyph_cache) > 1000:
        _emoji_glyph_cache.clear()
    _emoji_glyph_cache[sequence] = glyph
    return glyph


# ---------------------------------------------------------------- 排版
def _emoji_aspect(sequence: str, emoji_font_path: str) -> float | None:
    """emoji 宽高比（国旗/ZWJ 序列比单 emoji 宽）；无字形返回 None。"""
    glyph = _emoji_glyph(sequence, emoji_font_path)
    if glyph is None:
        return None
    width, height = glyph.size
    return (width / height) if height else 1.0


def _unit_width(unit: _UNIT, font: ImageFont.FreeTypeFont, size: int, emoji_font_path: str) -> float:
    kind, value = unit
    if kind == "emoji":
        aspect = _emoji_aspect(value, emoji_font_path)
        if aspect is None:  # 彩色字体没有该字形，按普通文字回退
            return font.getlength(value)
        return int(size * EMOJI_SCALE * aspect) + EMOJI_GAP
    return font.getlength(value)


def _layout_units(
    units: Sequence[_UNIT],
    font: ImageFont.FreeTypeFont,
    size: int,
    emoji_font_path: str,
) -> list[list[_UNIT]]:
    """按宽度折行，并做简单中文标点禁则处理。"""
    lines: list[list[_UNIT]] = []
    current: list[_UNIT] = []
    current_width = 0.0
    for unit in units:
        width = _unit_width(unit, font, size, emoji_font_path)
        if current and current_width + width > TEXT_WIDTH:
            kind, value = unit
            if kind == "text" and len(value) == 1 and value in NO_LINE_START:
                # 行首标点：勉强放进当前行，避免标点顶头
                current.append(unit)
                current_width += width
                continue
            lines.append(current)
            current = [unit]
            current_width = width
        else:
            current.append(unit)
            current_width += width
    if current:
        lines.append(current)

    # 行尾的开引号/开括号挪到下一行行首
    for i in range(len(lines) - 1):
        while (
            len(lines[i]) > 1
            and lines[i][-1][0] == "text"
            and len(lines[i][-1][1]) == 1
            and lines[i][-1][1] in NO_LINE_END
        ):
            lines[i + 1].insert(0, lines[i].pop())
    return lines


def _fit_units(
    units: list[_UNIT], quote_font_path: str, emoji_font_path: str
) -> tuple[ImageFont.FreeTypeFont, list[list[_UNIT]], int]:
    """从大到小选字号：行数不超过按单元数估算的理想行数。"""
    display = [("text", "「")] + list(units) + [("text", "」")]
    total = len(display)
    ideal_lines = max(1, min(5, -(-total // 10)))

    size = QUOTE_MAX_FONT
    while size > QUOTE_MIN_FONT:
        font = _load_font(quote_font_path, size, QUOTE_FONT_INDEX)
        lines = _layout_units(display, font, size, emoji_font_path)
        line_h = int(size * LINE_SPACING)
        if len(lines) <= ideal_lines and len(lines) * line_h <= int(H * 0.62):
            return font, lines, line_h
        size -= 2

    font = _load_font(quote_font_path, QUOTE_MIN_FONT, QUOTE_FONT_INDEX)
    lines = _layout_units(display, font, QUOTE_MIN_FONT, emoji_font_path)
    line_h = int(QUOTE_MIN_FONT * LINE_SPACING)
    if len(lines) > 6:  # 兜底：裁到 6 行以内，保留首尾引号
        trimmed = list(units)
        while len(trimmed) > 2:
            trimmed = trimmed[:-1]
            candidate = [("text", "「")] + trimmed + [("text", "…"), ("text", "」")]
            lines = _layout_units(candidate, font, QUOTE_MIN_FONT, emoji_font_path)
            if len(lines) <= 6:
                return font, lines, line_h
    return font, lines, line_h


# ---------------------------------------------------------------- 绘制
def _build_background(avatar: Image.Image) -> Image.Image:
    """头像铺满画布左侧，向右渐变压成纯黑。"""
    base = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    side = avatar.resize((AVATAR_W, AVATAR_W), Image.LANCZOS)
    side = ImageEnhance.Brightness(side).enhance(BG_BRIGHTNESS).convert("RGBA")
    base.paste(side, (AVATAR_X, 0))

    alpha = Image.new("L", (W, 1), 0)
    px = alpha.load()
    for x in range(W):
        if x <= GRAD_START:
            a = 0
        elif x >= GRAD_END:
            a = 255
        else:
            t = (x - GRAD_START) / (GRAD_END - GRAD_START)
            t = t * t * (3 - 2 * t)  # smoothstep
            a = int(255 * t)
        px[x, 0] = a
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grad.putalpha(alpha.resize((W, H)))
    return Image.alpha_composite(base, grad)


def _card_units(card: object) -> list[_UNIT]:
    """兼容旧调用：字符串按逐字文本处理；已是单元列表则原样使用。"""
    if isinstance(card, str):
        text = card.strip() or "群友"
        return [("text", char) for char in text]
    units = [tuple(unit) for unit in card if unit]  # type: ignore[union-attr]
    return units or [("text", "群友")]


def _draw_attr_units(
    base: Image.Image,
    card_units: list[_UNIT],
    attr_font: ImageFont.FreeTypeFont,
    emoji_font_path: str,
    y: int,
) -> None:
    """右下角「—— 群名片」：支持群名片里的 emoji，整体右对齐。"""
    units = [("text", "—— ")] + list(card_units)
    emoji_px = max(16, int(ATTR_FONT_SIZE * ATTR_EMOJI_SCALE))
    widths: list[int] = []
    for unit in units:
        kind, value = unit
        if kind == "emoji":
            aspect = _emoji_aspect(value, emoji_font_path)
            if aspect is None:
                widths.append(int(attr_font.getlength(value)))
            else:
                widths.append(int(emoji_px * aspect) + EMOJI_GAP)
        else:
            widths.append(int(attr_font.getlength(value)))
    x = TEXT_RIGHT - sum(widths)
    draw = ImageDraw.Draw(base)
    for unit, width in zip(units, widths, strict=False):
        kind, value = unit
        if kind == "emoji":
            glyph = _emoji_glyph(value, emoji_font_path)
            if glyph is None:
                draw.text((int(x), y), value, font=attr_font, fill=ATTR_COLOR)
            else:
                g_width, g_height = glyph.size
                new_w = max(1, width - EMOJI_GAP)
                glyph = glyph.resize((new_w, emoji_px), Image.LANCZOS)
                base.alpha_composite(glyph, (int(x), y + (ATTR_FONT_SIZE - emoji_px) // 2))
            x += width
        else:
            draw.text((int(x), y), value, font=attr_font, fill=ATTR_COLOR)
            x += width


def _draw_text_block(
    base: Image.Image,
    units: list[_UNIT],
    card_units: list[_UNIT],
    quote_font_path: str,
    attr_font_path: str,
    emoji_font_path: str,
    accent_name: str,
) -> None:
    accent = ACCENTS.get(accent_name, ACCENTS["gold"])
    font, lines, line_h = _fit_units(units, quote_font_path, emoji_font_path)
    emoji_px = max(18, int(font.size * EMOJI_SCALE))
    attr_font = _load_font(attr_font_path, ATTR_FONT_SIZE, ATTR_FONT_INDEX)

    block_h = len(lines) * line_h
    total_h = block_h + ATTR_GAP + ATTR_FONT_SIZE
    y = (H - total_h) // 2

    draw = ImageDraw.Draw(base)
    first_unit = lines[0][0] if lines and lines[0] else None
    last_unit = lines[-1][-1] if lines and lines[-1] else None

    for row, line in enumerate(lines):
        line_y = y + row * line_h
        x = float(TEXT_LEFT)
        run: list[str] = []
        run_x = x
        for unit in line:
            kind, value = unit
            if kind == "emoji":
                glyph = _emoji_glyph(value, emoji_font_path)
                if glyph is None:  # 彩色字体无字形 -> 用正文宋体当普通字符画
                    if not run:
                        run_x = x
                    run.append(value)
                    x += font.getlength(value)
                    continue
                if run:
                    draw.text((int(run_x), line_y), "".join(run), font=font, fill=QUOTE_COLOR)
                    run = []
                g_width, g_height = glyph.size
                scale = emoji_px / g_height if g_height else 1.0
                new_w = max(1, int(round(g_width * scale)))
                glyph = glyph.resize((new_w, emoji_px), Image.LANCZOS)
                base.alpha_composite(glyph, (int(x), line_y + (line_h - emoji_px) // 2))
                x += new_w + EMOJI_GAP
                run_x = x
                continue

            color = QUOTE_COLOR
            if accent_name == "gold" and (unit is first_unit or unit is last_unit) and value in ("「", "」"):
                color = accent
            if color != QUOTE_COLOR:
                if run:
                    draw.text((int(run_x), line_y), "".join(run), font=font, fill=QUOTE_COLOR)
                    run = []
                draw.text((int(x), line_y), value, font=font, fill=color)
                x += font.getlength(value)
                run_x = x
                continue
            if not run:
                run_x = x
            run.append(value)
            x += font.getlength(value)
        if run:
            draw.text((int(run_x), line_y), "".join(run), font=font, fill=QUOTE_COLOR)

    _draw_attr_units(
        base,
        card_units,
        attr_font,
        emoji_font_path,
        y + block_h + ATTR_GAP,
    )


def render_quote_card(
    avatar_bytes: bytes,
    units: Sequence[_UNIT],
    card: object = "群友",
    accent: str = "gold",
    font_dir: str | None = None,
) -> bytes:
    """渲染名言卡片，返回 PNG 字节；输入不可用时抛 RenderError。

    ``units`` 为解析层产出的内容单元列表：``("text", 文本)`` / ``("emoji", emoji序列)``。
    """
    units = list(units or [])
    if not units:
        raise RenderError("quote content is empty")
    card_units = _card_units(card)

    missing = missing_required_fonts(font_dir)
    if missing:
        raise RenderError(
            "缺少必需字体: "
            + ", ".join(missing)
            + f"（字体目录 {font_dir or DEFAULT_FONT_DIR!r}；可用环境变量 QUOTE_CARD_FONT_DIR 配置）"
        )

    try:
        with Image.open(BytesIO(avatar_bytes)) as im:
            avatar = ImageOps.fit(im.convert("RGB"), (AVATAR_W, AVATAR_W), Image.LANCZOS)
    except Exception as exc:  # noqa: BLE001 - 头像损坏统一视为输入不可用
        raise RenderError(f"invalid avatar image: {exc!r}") from exc

    quote_font_path, attr_font_path, emoji_font_path = _font_paths(font_dir)
    base = _build_background(avatar)
    _draw_text_block(
        base,
        units,
        card_units,
        quote_font_path,
        attr_font_path,
        emoji_font_path,
        accent,
    )

    buf = BytesIO()
    # 不做 optimize（压缩耗时 ~500ms），默认压缩级别约 130ms，体积只大 ~2%
    base.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


__all__ = [
    "DEFAULT_FONT_DIR",
    "EMOJI_FONT_FILE",
    "RenderError",
    "missing_required_fonts",
    "render_quote_card",
    "validate_assets",
]
