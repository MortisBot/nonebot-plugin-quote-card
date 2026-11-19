"""触发解析 / 内容单元抽取单测（移植自原离线自检脚本）。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from nonebot_plugin_quote_card import parse


def seg(seg_type: str, **data: Any) -> SimpleNamespace:
    return SimpleNamespace(type=seg_type, data=data)


class FakeEvent:
    def __init__(
        self,
        *,
        text: str = "名言",
        self_id: int = 10000,
        at: bool = True,
        reply: Any = None,
        group_id: int = 10000,
        user_id: int = 10001,
    ) -> None:
        self.self_id = self_id
        self.group_id = group_id
        self.user_id = user_id
        self.message = [seg("text", text=text)] if text else []
        self.original_message = ([seg("at", qq=str(self_id))] if at else []) + self.message
        self.reply = reply

    def get_plaintext(self) -> str:
        return "".join(item.data.get("text", "") for item in self.message if item.type == "text")


def fake_reply(*segments: Any, user_id: int = 10001, card: Any = None, nickname: Any = None) -> Any:
    sender = SimpleNamespace(user_id=user_id, card=card, nickname=nickname)
    return SimpleNamespace(sender=sender, message=list(segments), message_id=1)


def fake_event(**kwargs: Any) -> FakeEvent:
    return FakeEvent(**kwargs)


# ---------------------------------------------------------------- 触发解析
def test_trigger_parsing() -> None:
    event = fake_event()
    assert parse.is_command(event, "名言") is True
    assert parse.is_command(fake_event(text="  名言\u3000"), "名言") is True
    assert parse.is_command(fake_event(text="名言哦"), "名言") is False
    assert parse.is_command(fake_event(text=""), "名言") is False
    assert parse.is_command(fake_event(), "") is False
    assert parse.has_at_self(event) is True
    assert parse.has_at_self(fake_event(at=False)) is False


# ---------------------------------------------------------------- 内容抽取
def test_text_units() -> None:
    units = parse.extract_quote_units(fake_reply(seg("text", text="周一开组会诗人吗")))
    assert len(units) == 8
    assert parse.units_to_text(units) == "周一开组会诗人吗"
    assert all(kind == "text" for kind, _ in units)


def test_emoji_units() -> None:
    units = parse.extract_quote_units(fake_reply(seg("text", text="笑死😭了")))
    assert len(units) == 4
    assert units[2] == ("emoji", "😭")
    assert parse.units_to_text(units) == "笑死😭了"

    cases = {
        "❤️": 1,
        "❤": 1,
        "🇨🇳": 1,
        "👨‍👩‍👧": 1,
        "👍🏻": 1,
        "1️⃣": 1,
        "⭐": 1,
        "©️": 1,
    }
    for text, expected in cases.items():
        units = parse.extract_quote_units(fake_reply(seg("text", text=text)))
        emoji_units = [unit for unit in units if unit[0] == "emoji"]
        assert len(emoji_units) == expected
        assert parse.units_to_text(units) == text


def test_qq_face_placeholder() -> None:
    units = parse.extract_quote_units(
        fake_reply(seg("text", text="笑死"), seg("face", id="14"), seg("text", text="真的"))
    )
    assert parse.units_to_text(units) == "笑死[微笑]真的"

    units = parse.extract_quote_units(fake_reply(seg("face", id="999")))
    assert parse.units_to_text(units) == "[表情]"

    units = parse.extract_quote_units(fake_reply(seg("face", id="999", raw={"faceText": "/酷"})))
    assert parse.units_to_text(units) == "[酷]"

    units = parse.extract_quote_units(fake_reply(seg("face", id="14")))
    assert len(units) == 1
    assert parse.units_to_text(units) == "[微笑]"


def test_unsupported_segments_ignored() -> None:
    assert parse.extract_quote_units(fake_reply(seg("image", file="x"))) == []
    units = parse.extract_quote_units(fake_reply(seg("at", qq="10000"), seg("text", text="你好")))
    assert parse.units_to_text(units) == "你好"


def test_whitespace_normalization() -> None:
    units = parse.extract_quote_units(fake_reply(seg("text", text="  第一  行\n第二行 ")))
    assert parse.units_to_text(units) == "第一 行 第二行"


def test_middle_ellipsis() -> None:
    many = [("text", chr(0x4E00 + i % 500)) for i in range(200)]
    clipped = parse.middle_ellipsis_units(many, 100)
    assert len(clipped) == 100
    full = parse.units_to_text(many)
    clipped_text = parse.units_to_text(clipped)
    assert clipped_text.startswith(full[:5])
    assert clipped_text.endswith(full[-5:])
    assert any(kind == "text" and value == parse.ELLIPSIS for kind, value in clipped)

    with_emoji = [("emoji", "😭")] * 150
    assert len(parse.middle_ellipsis_units(with_emoji, 100)) == 100
    assert parse.middle_ellipsis_units([], 100) == []
    assert parse.middle_ellipsis_units([("text", "a")], 1) == [("text", "a")]


def test_signature_units() -> None:
    sig = parse.signature_units("若叶睦")
    assert parse.units_to_text(sig) == "若叶睦"

    sig = parse.signature_units("群星怒♡")
    assert parse.units_to_text(sig) == "群星怒♡"
    assert any(kind == "emoji" for kind, _ in sig)

    sig = parse.signature_units("群星怒🥲🎉")
    assert parse.units_to_text(sig) == "群星怒🥲🎉"
    assert sum(1 for kind, _ in sig if kind == "emoji") == 2

    sig = parse.signature_units("长" * 40)
    assert len(sig) <= 28
    assert parse.units_to_text(sig).endswith("…")

    assert parse.units_to_text(parse.signature_units("")) == "群友"


def test_sender_helpers() -> None:
    assert parse.sender_name(fake_reply(card="若叶睦", nickname="mutsumi")) == "若叶睦"
    assert parse.sender_name(fake_reply(card="", nickname="mutsumi")) == "mutsumi"
    assert parse.sender_name(fake_reply(user_id=10001)) == "10001"
    assert parse.sender_user_id(fake_reply(user_id=10001)) == 10001
    assert parse.sender_user_id(SimpleNamespace(sender=None)) is None
    assert parse.sender_user_id(SimpleNamespace(sender=SimpleNamespace(user_id=0))) is None
    assert parse.sender_name(SimpleNamespace(sender=None)) == "群友"


def test_normalize_text() -> None:
    assert parse.normalize_text("\u3000 名言 \t") == "名言"
    assert parse.normalize_text(None) == ""
    assert parse.normalize_text("a\x00b") == "ab"
    assert parse.normalize_text("a   b") == "a b"
