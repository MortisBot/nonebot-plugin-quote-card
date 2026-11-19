"""插件入口/触发规则单测：metadata、候选判定、冷却、群名片解析。

不启动 NoneBot 事件循环、不连接适配器、不发消息。
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

import pytest
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message
from nonebot.adapters.onebot.v11.event import Reply, Sender

import nonebot_plugin_quote_card as plugin
from nonebot_plugin_quote_card import parse


def make_event(
    *,
    text: str = "名言",
    group_id: int = 10000,
    user_id: int = 10000,
    reply: Any = None,
    to_me: bool = False,
) -> GroupMessageEvent:
    return GroupMessageEvent(
        time=1,
        self_id=10000,
        post_type="message",
        sub_type="normal",
        user_id=user_id,
        message_type="group",
        message_id=1,
        message=Message(text),
        raw_message=text,
        font=0,
        sender=Sender(user_id=user_id, nickname="群友"),
        group_id=group_id,
        to_me=to_me,
        reply=reply,
    )


def make_reply(text: str = "被引用的消息", user_id: int = 10001) -> Reply:
    return Reply(
        time=1,
        message_type="group",
        message_id=2,
        real_id=2,
        sender=Sender(user_id=user_id, nickname="被引用的人"),
        message=Message(text),
    )


@pytest.fixture()
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """启用插件并放行群 10000，字体资源视为齐全。"""
    monkeypatch.setattr(plugin, "CFG", replace(plugin.CFG, enabled=True, groups=frozenset({10000})))
    monkeypatch.setattr(plugin, "_missing_assets", [])


def test_plugin_metadata() -> None:
    meta = plugin.__plugin_meta__
    assert meta.name
    assert meta.homepage == "https://github.com/MortisBot/nonebot-plugin-quote-card"
    assert meta.supported_adapters == {"~onebot.v11"}
    assert "~onebot-v11" not in repr(meta)
    assert "引用" in (meta.usage or "")
    assert "群" in (meta.description or "")
    # 不应出现任何真实群号形式的硬编码
    assert not re.findall(r"\d{6,12}", repr(meta))


def test_candidate_requires_enabled_and_group(monkeypatch: pytest.MonkeyPatch) -> None:
    # 默认配置：关闭 + 群列表为空
    assert plugin._candidate(make_event(reply=make_reply())) is False

    monkeypatch.setattr(plugin, "CFG", replace(plugin.CFG, enabled=False, groups=frozenset({10000})))
    monkeypatch.setattr(plugin, "_missing_assets", [])
    assert plugin._candidate(make_event(reply=make_reply())) is False


def test_candidate_accepts_reply_command(enabled: None) -> None:
    assert plugin._candidate(make_event(reply=make_reply())) is True
    assert plugin._candidate(make_event(reply=make_reply(), text="  名言\u3000")) is True
    assert plugin._candidate(make_event(reply=make_reply(), to_me=True)) is True


def test_candidate_rejects_bad_input(enabled: None) -> None:
    assert plugin._candidate(make_event(reply=None)) is False  # 非引用消息
    assert plugin._candidate(make_event(reply=make_reply(), text="名言哦")) is False  # 命令不严格
    assert plugin._candidate(make_event(reply=make_reply(), group_id=10001)) is False  # 非开放群
    assert plugin._candidate(object()) is False  # 非群消息事件


def test_candidate_rejects_missing_fonts(enabled: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plugin, "_missing_assets", ["NotoSerifCJK-Bold.ttc"])
    assert plugin._candidate(make_event(reply=make_reply())) is False


def test_group_allowed() -> None:
    assert plugin._group_allowed(10000) is False  # 默认群列表为空
    assert plugin._group_allowed("10000") is False
    assert plugin._group_allowed("not-a-number") is False
    assert plugin._group_allowed(None) is False


def test_cooldown(enabled: None, monkeypatch: pytest.MonkeyPatch) -> None:
    plugin._cooldowns.clear()
    event = make_event(reply=make_reply())
    monkeypatch.setattr(plugin, "CFG", replace(plugin.CFG, cooldown_seconds=60.0))
    assert plugin._allow_cooldown(event) is True
    assert plugin._allow_cooldown(event) is False  # 冷却中
    # 其他用户不受影响
    assert plugin._allow_cooldown(make_event(user_id=10001, reply=make_reply())) is True
    plugin._cooldowns.clear()

    monkeypatch.setattr(plugin, "CFG", replace(plugin.CFG, cooldown_seconds=0.0))
    assert plugin._allow_cooldown(event) is True
    assert plugin._allow_cooldown(event) is True


async def test_resolve_card_units_prefers_live_card() -> None:
    class FakeBot:
        async def get_group_member_info(self, **kwargs: Any) -> dict[str, Any]:
            assert kwargs["group_id"] == 10000
            assert kwargs["user_id"] == 10001
            return {"card": "新群名片", "nickname": "旧昵称"}

    units = await plugin._resolve_card_units(FakeBot(), 10000, make_reply(), "回退名")
    assert parse.units_to_text(units) == "新群名片"


async def test_resolve_card_units_fallback_on_error() -> None:
    class BrokenBot:
        async def get_group_member_info(self, **kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("api failed")

    units = await plugin._resolve_card_units(BrokenBot(), 10000, make_reply(), "回退名")
    assert parse.units_to_text(units) == "回退名"
