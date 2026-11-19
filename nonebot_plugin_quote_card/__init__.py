"""名言卡片插件（nonebot-plugin-quote-card）。

用法：在 ``QUOTE_CARD_GROUPS`` 配置的群里，引用任意一条消息并发送 ``名言``（@bot 可选）。
例：回复某条消息 → 名言；也可以 → @bot 名言

被引用消息的发送者头像铺满左侧底图，向右渐变压黑，正文用「」包住被引用消息文本，
右下角是破折号 + 群名片署名。Unicode emoji 优先彩色渲染，QQ 表情显示为 [微笑] 这类文字。
不含任何可渲染内容的消息 / 其它输入一律静默不回复。

默认关闭（``QUOTE_CARD_ENABLED=false``）且群列表为空，必须显式配置后才会响应。
"""

from __future__ import annotations

import asyncio
import base64
import time

from nonebot import logger, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageSegment
from nonebot.plugin import PluginMetadata
from nonebot.rule import Rule

from .avatar import fetch_avatar
from .config import load_config
from .parse import (
    extract_quote_units,
    is_command,
    middle_ellipsis_units,
    sender_name,
    sender_user_id,
    signature_units,
)
from .render import RenderError, missing_required_fonts, render_quote_card

__plugin_meta__ = PluginMetadata(
    name="名言卡片",
    description=(
        "引用一条消息并发送「名言」（@bot 可选），把被引用消息做成名人名言风格图片："
        "发送者头像铺左侧、渐变压黑、中文字体「」正文、emoji 彩色渲染、破折号+群名片署名。"
        "需在 QUOTE_CARD_GROUPS 中显式配置启用的群。"
    ),
    usage="引用消息 + 名言（@bot 可选）；需先配置 QUOTE_CARD_ENABLED=true 与 QUOTE_CARD_GROUPS",
    type="application",
    homepage="https://github.com/MortisBot/nonebot-plugin-quote-card",
    supported_adapters={"~onebot.v11"},
)

CFG = load_config()
logger.info(
    "[quote_card] enabled={} groups={} command={!r} max_chars={} cooldown={}s avatar_ttl={}h accent={} fonts={}",
    CFG.enabled,
    sorted(CFG.groups),
    CFG.command,
    CFG.max_chars,
    CFG.cooldown_seconds,
    CFG.avatar_ttl_hours,
    CFG.accent,
    CFG.font_dir,
)
# 只有「必需字体」缺失才禁用插件；彩色 emoji 字体缺失时 render 会自动回退
_missing_assets = missing_required_fonts(CFG.font_dir)
if _missing_assets:
    logger.error(
        "[quote_card] 缺少必需字体: {}（QUOTE_CARD_FONT_DIR={}）",
        ", ".join(_missing_assets),
        CFG.font_dir,
    )

_render_semaphore = asyncio.Semaphore(1)
_cooldowns: dict[tuple[int, int], float] = {}


def _group_allowed(group_id: object) -> bool:
    try:
        return int(group_id) in CFG.groups
    except (TypeError, ValueError):
        return False


def _candidate(event) -> bool:
    try:
        if not CFG.enabled or _missing_assets:
            return False
        if not isinstance(event, GroupMessageEvent):
            return False
        if not _group_allowed(event.group_id):
            return False
        if getattr(event, "reply", None) is None:
            return False
        # 不强制 @bot：引用消息 + 命令文本即可；带了 @ 也能触发
        return is_command(event, CFG.command)
    except Exception:
        logger.exception("[quote_card] 命令匹配规则异常")
        return False


matcher = on_message(rule=Rule(_candidate), priority=6, block=True)


def _allow_cooldown(event: GroupMessageEvent) -> bool:
    now = time.monotonic()
    key = (int(event.group_id), int(event.user_id))
    last = _cooldowns.get(key)
    if last is not None and now - last < CFG.cooldown_seconds:
        return False
    _cooldowns[key] = now
    if len(_cooldowns) > 1024:
        cutoff = now - max(60.0, CFG.cooldown_seconds * 6)
        for item_key, last_time in list(_cooldowns.items()):
            if last_time < cutoff:
                _cooldowns.pop(item_key, None)
    return True


async def _resolve_card_units(bot: Bot, group_id: int, reply, fallback_name: str) -> list[tuple[str, str]]:
    """群名片实时取：优先 get_group_member_info（no_cache），失败回退消息里的 sender。"""
    name = fallback_name
    user_id = sender_user_id(reply)
    if user_id is not None:
        try:
            info = await bot.get_group_member_info(group_id=int(group_id), user_id=user_id, no_cache=True)
            fresh = str(info.get("card") or "").strip() or str(info.get("nickname") or "").strip()
            if fresh:
                name = fresh
        except Exception:
            logger.debug(
                "[quote_card] get_group_member_info failed group={} user={}",
                group_id,
                user_id,
            )
    return signature_units(name)


@matcher.handle()
async def _handle_quote_card(bot: Bot, event: GroupMessageEvent) -> None:
    payload: Message | None = None
    try:
        reply = event.reply
        if reply is None:  # 适配器 get_msg 失败时可能为空，静默
            return
        target_id = sender_user_id(reply)
        if target_id is None:
            logger.debug("[quote_card] anchor sender missing group={}", event.group_id)
            return
        units = extract_quote_units(reply)
        if not units:
            logger.info(
                "[quote_card] anchor has no renderable content, ignored group={} target={}",
                event.group_id,
                target_id,
            )
            return

        units = middle_ellipsis_units(units, CFG.max_chars)
        if not _allow_cooldown(event):
            logger.info("[quote_card] cooldown group={} user={}", event.group_id, event.user_id)
            return

        # 头像（多数命中缓存/网络）与群名片（实时 no_cache）并发，互相抵消延迟
        started = time.monotonic()
        avatar, card_units = await asyncio.gather(
            fetch_avatar(target_id, CFG),
            _resolve_card_units(bot, event.group_id, reply, sender_name(reply)),
        )
        io_ms = (time.monotonic() - started) * 1000.0
        if avatar is None:
            return

        render_started = time.monotonic()
        async with _render_semaphore:
            png = await asyncio.to_thread(render_quote_card, avatar, units, card_units, CFG.accent, CFG.font_dir)
        render_ms = (time.monotonic() - render_started) * 1000.0
        encoded = base64.b64encode(png).decode("ascii")
        payload = Message(MessageSegment.image("base64://" + encoded))
        logger.info(
            "[quote_card] generated group={} target={} units={} bytes={} io_ms={:.0f} render_ms={:.0f}",
            event.group_id,
            target_id,
            len(units),
            len(png),
            io_ms,
            render_ms,
        )
    except RenderError:
        logger.exception("[quote_card] 渲染失败 group={}", getattr(event, "group_id", "?"))
    except Exception:
        logger.exception("[quote_card] 生成名言卡片异常 group={}", getattr(event, "group_id", "?"))

    if payload is not None:
        await matcher.finish(payload)


__all__ = ["CFG", "matcher"]
