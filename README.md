<div align="center">

# nonebot-plugin-quote-card

_✨ 引用一条群消息，生成一张「名人名言」风格卡片 ✨_

[![LICENSE](https://img.shields.io/github/license/MortisBot/nonebot-plugin-quote-card.svg)](./LICENSE)
[![pypi](https://img.shields.io/pypi/v/nonebot-plugin-quote-card.svg)](https://pypi.python.org/pypi/nonebot-plugin-quote-card)
![python](https://img.shields.io/badge/python-3.10+-blue.svg)

</div>

## 📖 介绍

在群里**引用任意一条消息**，再发送 `名言`，机器人会把被引用的内容做成图片：发送者头像铺满左侧、向右渐变压黑，正文用宋体「」包住，右下角是群名片署名；Unicode emoji 彩色渲染，QQ 经典表情显示为 `[微笑]` 这类文字。

## 💿 安装

<details open>
<summary>使用 nb-cli 安装</summary>

在 NoneBot2 项目根目录下执行：

```bash
nb plugin install nonebot-plugin-quote-card --upgrade
```

国内网络可换镜像源：

```bash
nb plugin install nonebot-plugin-quote-card --upgrade -i "https://pypi.tuna.tsinghua.edu.cn/simple"
```

</details>

<details>
<summary>使用包管理器安装</summary>

在 NoneBot2 项目根目录下执行其一：

```bash
uv add nonebot-plugin-quote-card
# 或
pdm add nonebot-plugin-quote-card
# 或
poetry add nonebot-plugin-quote-card
```

直接装仓库主分支（PyPI 包发布前可用）：

```bash
uv add git+https://github.com/MortisBot/nonebot-plugin-quote-card@main
```

然后在 `pyproject.toml` 的 `[tool.nonebot]` 中追加：

```toml
plugins = ["nonebot_plugin_quote_card"]
```

</details>

## ⚙️ 配置

在 NoneBot2 项目的 `.env` 中配置（配置项即环境变量名，大写）：

| 配置项 | 必填 | 默认值 | 说明 |
|:---:|:---:|:---:|:---|
| `QUOTE_CARD_ENABLED` | 是 | `false` | 总开关 |
| `QUOTE_CARD_GROUPS` | 是 | 空 | 启用的群号，逗号分隔 |
| `QUOTE_CARD_COMMAND` | 否 | `名言` | 触发词 |
| `QUOTE_CARD_MAX_CHARS` | 否 | `100` | 正文最大字数（超出中间省略） |
| `QUOTE_CARD_COOLDOWN_SECONDS` | 否 | `10` | 同用户/群冷却秒数 |
| `QUOTE_CARD_ACCENT` | 否 | `gold` | 引号颜色：`gold` / `white` |
| `QUOTE_CARD_FONT_DIR` | 否 | 内置 | 字体目录（Noto Serif CJK / Noto Color Emoji，OFL） |

## 🎉 使用

| 操作 | 权限 | 需要 @ | 范围 | 说明 |
|:---:|:---:|:---:|:---:|:---|
| 引用消息 + `名言` | 群员 | 否 | 群聊 | 生成卡片 |
| 引用消息 + `@bot 名言` | 群员 | 是 | 群聊 | 同上 |

## 🔌 适配器

OneBot v11（`supported_adapters={"~onebot.v11"}`）。发送图片依赖 Pillow；字体缺失时会抛出可读的 `RenderError`。

## 📄 License

[MIT](./LICENSE) · 维护模式（best-effort，无 SLA）
