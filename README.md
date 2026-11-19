# nonebot-plugin-quote-card

_✨ 引用一条群消息并发送「名言」，把被引用内容渲染成名人名言风格图片。 ✨_

<a href="./LICENSE"><img src="https://img.shields.io/github/license/MortisBot/nonebot-plugin-quote-card.svg" alt="license"></a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-quote-card"><img src="https://img.shields.io/pypi/v/nonebot-plugin-quote-card.svg" alt="pypi"></a>
<img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="python">

## 安装

在 NoneBot2 项目根目录下执行：

```bash
nb plugin install nonebot-plugin-quote-card
```

或手动安装：

```bash
pip install nonebot-plugin-quote-card
```

并在 `pyproject.toml` 的 `[tool.nonebot]` 中追加：

```toml
plugins = ["nonebot_plugin_quote_card"]
```

## 配置

在 `.env` 中配置（环境变量名即配置项大写）：

| 配置项 | 必填 | 默认值 | 说明 |
|:---:|:---:|:---:|:---|
| `QUOTE_CARD_ENABLED` | 是 | `false` | 总开关 |
| `QUOTE_CARD_GROUPS` | 是 | 空 | 启用的群号，逗号分隔 |
| `QUOTE_CARD_COMMAND` | 否 | `名言` | 触发词 |
| `QUOTE_CARD_MAX_CHARS` | 否 | `100` | 正文最大字数（超出中间省略） |
| `QUOTE_CARD_COOLDOWN_SECONDS` | 否 | `10` | 同用户/群冷却秒数 |
| `QUOTE_CARD_FONT_DIR` | 否 | 内置 | 字体目录（Noto Serif CJK / Noto Color Emoji，OFL） |

## 使用

在启用的群里：

1. 引用任意一条群消息；
2. 发送 `名言`（@bot 可选）。

机器人会把被引用内容渲染成图片回复。

## 适配器

OneBot v11（`supported_adapters={"~onebot.v11"}`）。

## License

[MIT](./LICENSE)

> 维护模式：原项目已停止运营，本插件按 best-effort 维护，无 SLA。
