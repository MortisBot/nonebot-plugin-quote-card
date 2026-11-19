# nonebot-plugin-quote-card

_✨ 引用一条群消息，生成一张「名人名言」风格卡片 ✨_

![license](https://img.shields.io/github/license/MortisBot/nonebot-plugin-quote-card)
![pypi](https://img.shields.io/pypi/v/nonebot-plugin-quote-card)
![python](https://img.shields.io/badge/python-3.10%2B-blue)

在群里**引用任意一条消息**，再发送 `名言`，机器人会把被引用的内容做成图片：
发送者头像铺满左侧、向右渐变压黑，正文用宋体「」包住，右下角是群名片署名；Unicode emoji 彩色渲染，QQ 经典表情显示为 `[微笑]` 这类文字。

## 安装

```bash
# 在 NoneBot2 项目根目录
nb plugin install nonebot-plugin-quote-card
```

手动安装：`pip install nonebot-plugin-quote-card`，然后在 `pyproject.toml` 的 `[tool.nonebot]` 中加：

```toml
plugins = ["nonebot_plugin_quote_card"]
```

## 怎么用

| 操作 | 说明 |
|:---:|:---|
| 引用消息 + `名言` | 触发生成（@bot 可选） |
| 引用消息 + `@bot 名言` | 同上 |

## 配置

| 配置项 | 必填 | 默认 | 说明 |
|:---:|:---:|:---:|:---|
| `QUOTE_CARD_ENABLED` | 是 | `false` | 总开关 |
| `QUOTE_CARD_GROUPS` | 是 | 空 | 启用的群号 |
| `QUOTE_CARD_COMMAND` | 否 | `名言` | 触发词 |
| `QUOTE_CARD_MAX_CHARS` | 否 | `100` | 正文上限，超出中间省略 |
| `QUOTE_CARD_COOLDOWN_SECONDS` | 否 | `10` | 冷却时间 |
| `QUOTE_CARD_ACCENT` | 否 | `gold` | 引号颜色：`gold`/`white` |
| `QUOTE_CARD_FONT_DIR` | 否 | 内置 | 字体目录（OFL 字体需自备/下载） |

## 兼容性

- 适配器：OneBot v11（`~onebot.v11`）
- 发图依赖 Pillow；字体缺失时会抛出可读的 `RenderError`

## License

[MIT](./LICENSE) · 维护模式（best-effort，无 SLA）
