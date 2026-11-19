"""名言卡片触发解析、被引用内容抽取与文案处理。

纯标准库实现，不 import NoneBot；事件对象按 duck typing 使用，便于离线自检。

被引用消息内容会被整理成「单元（unit）」列表，供渲染层混排：
  - ``("text", 字/占位串)``：普通文字；QQ 表情会转成 ``[微笑]`` 这类文字占位
  - ``("emoji", 序列)``：Unicode emoji（含 ZWJ/肤色/旗帜/键帽序列），渲染成彩色 emoji
"""

from __future__ import annotations

import re
from typing import Any

ELLIPSIS = "……"

# QQ 经典表情 id -> 中文名（14..118），用于把 face 段转成 [微笑] 这种文字
FACE_NAMES: dict[int, str] = {
    14: "微笑",
    15: "撇嘴",
    16: "色",
    17: "发呆",
    18: "得意",
    19: "流泪",
    20: "害羞",
    21: "闭嘴",
    22: "睡",
    23: "大哭",
    24: "尴尬",
    25: "发怒",
    26: "调皮",
    27: "呲牙",
    28: "惊讶",
    29: "难过",
    30: "酷",
    31: "冷汗",
    32: "抓狂",
    33: "吐",
    34: "偷笑",
    35: "可爱",
    36: "白眼",
    37: "傲慢",
    38: "饥饿",
    39: "困",
    40: "惊恐",
    41: "流汗",
    42: "憨笑",
    43: "悠闲",
    44: "奋斗",
    45: "咒骂",
    46: "疑问",
    47: "嘘",
    48: "晕",
    49: "折磨",
    50: "衰",
    51: "骷髅",
    52: "敲打",
    53: "再见",
    54: "擦汗",
    55: "抠鼻",
    56: "鼓掌",
    57: "糗大了",
    58: "坏笑",
    59: "左哼哼",
    60: "右哼哼",
    61: "哈欠",
    62: "鄙视",
    63: "委屈",
    64: "快哭了",
    65: "阴险",
    66: "亲亲",
    67: "吓",
    68: "可怜",
    69: "菜刀",
    70: "西瓜",
    71: "啤酒",
    72: "篮球",
    73: "乒乓",
    74: "咖啡",
    75: "饭",
    76: "猪头",
    77: "玫瑰",
    78: "凋谢",
    79: "示爱",
    80: "爱心",
    81: "心碎",
    82: "蛋糕",
    83: "闪电",
    84: "炸弹",
    85: "刀",
    86: "足球",
    87: "瓢虫",
    88: "便便",
    89: "月亮",
    90: "太阳",
    91: "礼物",
    92: "拥抱",
    93: "强",
    94: "弱",
    95: "握手",
    96: "胜利",
    97: "抱拳",
    98: "勾引",
    99: "拳头",
    100: "差劲",
    101: "爱你",
    102: "NO",
    103: "OK",
    104: "爱情",
    105: "飞吻",
    106: "跳跳",
    107: "发抖",
    108: "怄火",
    109: "转圈",
    110: "磕头",
    111: "回头",
    112: "跳绳",
    113: "挥手",
    114: "激动",
    115: "街舞",
    116: "献吻",
    117: "左太极",
    118: "右太极",
}

# Emoji 主体范围（够用即可：覆盖常见 emoji、符号、旗帜；不在其中的按普通文字处理）
_EMOJI_RANGES = (
    (0x1F000, 0x1FAFF),  # 全部 emoji 主体块（含旗帜、符号、补充表情）
    (0x2600, 0x27BF),  # 杂项符号 + Dingbats
    (0x2B00, 0x2BFF),  # 星星/箭头等
    (0x2300, 0x23FF),  # ⌚⏰ 等
    (0x25A0, 0x25FF),  # 几何图形（部分 emoji）
    (0x2934, 0x2935),
    (0x3030, 0x3030),
    (0x303D, 0x303D),
    (0x3297, 0x3297),
    (0x3299, 0x3299),
    (0x00A9, 0x00A9),
    (0x00AE, 0x00AE),
    (0x203C, 0x203C),
    (0x2049, 0x2049),
    (0x2122, 0x2122),
    (0x2139, 0x2139),
)

_EMOJI_EXTENDS = "\ufe0f\u200d\u20e3"
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_UNIT = tuple[str, str]


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def get_original_message(event: Any) -> Any:
    original = _get(event, "original_message", None)
    if original is not None:
        return original
    return _get(event, "message", None)


def iter_segments(message: Any) -> list[Any]:
    if message is None or isinstance(message, str):
        return []
    try:
        return list(message)
    except TypeError:
        return []


def segment_type(segment: Any) -> str:
    return str(_get(segment, "type", "") or "")


def segment_data(segment: Any) -> dict:
    data = _get(segment, "data", None)
    return data if isinstance(data, dict) else {}


def normalize_text(value: object) -> str:
    """清理控制字符、半角空白，返回 strip 后的单行文本（命令判定用）。"""
    text = str(value or "").replace("\u3000", " ")
    text = _CONTROL_RE.sub("", text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    return re.sub(r"^[\s\u3000]+|[\s\u3000]+$", "", text)


def has_at_self(event: Any) -> bool:
    """扫描触发消息本身（original_message）是否显式 @ 了 bot。

    说明：quote_card 当前不强制 @（引用消息 + 名言即可），此函数保留作通用工具。
    """
    self_id = str(_get(event, "self_id", "") or "")
    if not self_id:
        return False
    for segment in iter_segments(get_original_message(event)):
        if segment_type(segment) != "at":
            continue
        if str(segment_data(segment).get("qq", "")) == self_id:
            return True
    return False


def event_plaintext(event: Any) -> str:
    getter = getattr(event, "get_plaintext", None)
    if callable(getter):
        try:
            text = getter()
        except Exception:
            text = ""
        if isinstance(text, str):
            return normalize_text(text)
    parts: list[str] = []
    for segment in iter_segments(_get(event, "message", None)):
        if segment_type(segment) == "text":
            parts.append(str(segment_data(segment).get("text", "") or ""))
    return normalize_text("".join(parts))


def is_command(event: Any, command: str) -> bool:
    """命令文本必须严格等于配置的命令（忽略首尾空白/全角空格）。"""
    expected = normalize_text(command)
    if not expected:
        return False
    return event_plaintext(event) == expected


# ---------------------------------------------------------------- QQ 表情
def face_to_text(data: dict) -> str:
    """QQ face 段 -> 文字占位，例如 [微笑]；未知表情回退 [表情]。"""
    raw_id = data.get("id", data.get("face_id"))
    try:
        face_id = int(raw_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        face_id = None
    if face_id is not None and face_id in FACE_NAMES:
        return f"[{FACE_NAMES[face_id]}]"
    raw = data.get("raw")
    if isinstance(raw, dict):
        face_text = str(raw.get("faceText") or raw.get("face_text") or "").strip()
        face_text = face_text.lstrip("/")
        if face_text and len(face_text) <= 8:
            return f"[{face_text}]"
    return "[表情]"


# ---------------------------------------------------------------- emoji / 文本单元
def _is_emoji_base(ch: str) -> bool:
    code = ord(ch)
    return any(low <= code <= high for low, high in _EMOJI_RANGES)


def _is_emoji_skin(ch: str) -> bool:
    return 0x1F3FB <= ord(ch) <= 0x1F3FF


def _is_region(ch: str) -> bool:
    return 0x1F1E6 <= ord(ch) <= 0x1F1FF


def split_text_units(text: str) -> list[_UNIT]:
    """把文本拆成 text 单元（逐字）和 emoji 单元（整段序列）。"""
    units: list[_UNIT] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in _EMOJI_EXTENDS:
            i += 1
            continue
        # 键帽 1️⃣ / #️⃣ 等
        if ch in "0123456789#*":
            if i + 2 < n and text[i + 1] == "\ufe0f" and text[i + 2] == "\u20e3":
                units.append(("emoji", text[i : i + 3]))
                i += 3
                continue
            if i + 1 < n and text[i + 1] == "\u20e3":
                units.append(("emoji", text[i : i + 2]))
                i += 2
                continue
        # 旗帜（两个 Regional Indicator）
        if _is_region(ch) and i + 1 < n and _is_region(text[i + 1]):
            units.append(("emoji", text[i : i + 2]))
            i += 2
            continue
        # 普通 emoji（含肤色、VS16、ZWJ 组合）
        if _is_emoji_base(ch):
            j = i + 1
            while j < n and (_is_emoji_skin(text[j]) or text[j] == "\ufe0f"):
                j += 1
            while j + 1 < n and text[j] == "\u200d" and _is_emoji_base(text[j + 1]):
                j += 2
                while j < n and (_is_emoji_skin(text[j]) or text[j] == "\ufe0f"):
                    j += 1
            units.append(("emoji", text[i:j]))
            i = j
            continue
        units.append(("text", ch))
        i += 1
    return units


def _normalize_units(units: list[_UNIT]) -> list[_UNIT]:
    """空白归一化：换行/连续空格合并成单个空格，去掉首尾空格。"""
    out: list[_UNIT] = []
    prev_space = True
    for kind, value in units:
        if kind == "emoji":
            out.append((kind, value))
            prev_space = False
            continue
        if len(value) > 1:  # [微笑] 这类占位串整体保留
            out.append((kind, value))
            prev_space = False
            continue
        char = value
        if char in "\n\r\t\f\v":
            char = " "
        if char == " ":
            if not prev_space:
                out.append(("text", " "))
                prev_space = True
            continue
        out.append(("text", char))
        prev_space = False
    while out and out[-1] == ("text", " "):
        out.pop()
    return out


def extract_quote_units(reply: Any) -> list[_UNIT]:
    """从被引用消息抽取可渲染的内容单元（文字 + emoji + QQ 表情占位）。"""
    message = _get(reply, "message", None)
    raw_units: list[_UNIT] = []
    if isinstance(message, str):
        raw_units.extend(split_text_units(_clean_segment_text(message)))
    else:
        for segment in iter_segments(message):
            seg_type = segment_type(segment)
            data = segment_data(segment)
            if seg_type == "text":
                raw_units.extend(split_text_units(_clean_segment_text(str(data.get("text", "") or ""))))
            elif seg_type == "face":
                raw_units.append(("text", face_to_text(data)))
            # 图片/语音/合并转发等段暂不支持，直接忽略
    return _normalize_units(raw_units)


def _clean_segment_text(text: str) -> str:
    text = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x0b", " ").replace("\x0c", " ")
    return _CONTROL_RE.sub("", text)


def units_to_text(units: list[_UNIT]) -> str:
    """单元列表转回可读文本（日志/调试用）。"""
    return "".join(value for _, value in units)


def signature_units(value: object, max_units: int = 28) -> list[_UNIT]:
    """群名片/署名 -> 内容单元（支持名片里的 emoji，超长尾部省略）。"""
    text = _clean_segment_text(str(value or ""))
    units = _normalize_units(split_text_units(text))
    limit = max(4, int(max_units))
    if len(units) > limit:
        units = units[: limit - 1] + [("text", "…")]
    return units or [("text", "群友")]


def middle_ellipsis_units(units: list[_UNIT], max_chars: int) -> list[_UNIT]:
    """超长内容保留头尾、中间用省略号；按单元个数计数（emoji/表情各算 1）。"""
    units = list(units or [])
    limit = max(2, int(max_chars))
    if len(units) <= limit:
        return units
    if limit < 3:
        return units[:limit]
    keep = limit - 1  # 省略号本身占 1 个单元
    head = keep // 2
    tail = keep - head
    return units[:head] + [("text", ELLIPSIS)] + units[-tail:]


def sender_user_id(reply: Any) -> int | None:
    sender = _get(reply, "sender", None)
    raw = _get(sender, "user_id", None) if sender is not None else None
    try:
        uid = int(raw)
    except (TypeError, ValueError):
        return None
    return uid if uid > 0 else None


def sender_name(reply: Any, fallback: str = "群友") -> str:
    """群名片优先，其次昵称，最后回退。"""
    sender = _get(reply, "sender", None)
    card = _get(sender, "card", None) if sender is not None else None
    nickname = _get(sender, "nickname", None) if sender is not None else None
    for candidate in (card, nickname):
        name = normalize_text(candidate)
        if name:
            return name
    uid = sender_user_id(reply)
    if uid is not None:
        return str(uid)
    return fallback


__all__ = [
    "ELLIPSIS",
    "FACE_NAMES",
    "event_plaintext",
    "extract_quote_units",
    "face_to_text",
    "get_original_message",
    "has_at_self",
    "is_command",
    "iter_segments",
    "middle_ellipsis_units",
    "normalize_text",
    "segment_data",
    "segment_type",
    "sender_name",
    "signature_units",
    "sender_user_id",
    "split_text_units",
    "units_to_text",
]
