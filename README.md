# nonebot-plugin-quote-card

> 同系列插件与部署/架构文档：[`MortisBot/qqbot-plugins`](https://github.com/MortisBot/qqbot-plugins)（索引与文档仓）

引用一条群消息并发送「名言」，把被引用的内容渲染成「名人名言」风格图片（NoneBot2 / OneBot v11）。

被引用消息的发送者头像铺满左侧底图、向右渐变压黑；正文用「」包住被引用消息文本；
右下角是破折号 + 群名片署名。Unicode emoji 优先彩色渲染，QQ 经典表情显示为 `[微笑]`
这类文字占位；超长内容保留头尾、中间省略。

## 安装

```bash
# 方式一：作为 NoneBot 插件安装（需先装好 nonebot2 与 onebot 适配器）
nb plugin install nonebot-plugin-quote-card

# 方式二：从源码安装（本仓库 monorepo）
pip install -e packages/nonebot-plugin-quote-card
```

插件依赖 `nonebot2>=2.5,<3`、`nonebot-adapter-onebot>=2.4`、`httpx`、`pillow`。
适配器：**OneBot v11**（`~onebot.v11`，如 NapCat / go-cqhttp 的反向 WS）。

## 快速开始

1. 准备字体（见下节），放到 `data/quote_card/fonts/`，或自定义 `QUOTE_CARD_FONT_DIR`。
2. 在 NoneBot 环境变量（`.env` / `.env.prod` / 容器 env）里配置：

   ```dotenv
   QUOTE_CARD_ENABLED=true
   QUOTE_CARD_GROUPS=10000
   QUOTE_CARD_FONT_DIR=data/quote_card/fonts
   ```

3. 在群里**引用任意一条消息**，发送 `名言`（@bot 可选）。

> 默认 `QUOTE_CARD_ENABLED=false` 且群列表为空：不配置就不会响应任何群。

## 命令

| 触发方式 | 说明 |
|---|---|
| 引用一条消息 → 发送 `名言` | 生成名言卡片；`@bot 名言` 亦可 |
| 引用一条消息 → 发送其它内容 | 不触发 |

触发条件（全部满足）：插件已启用、群在 `QUOTE_CARD_GROUPS` 中、消息是引用回复、
正文（去首尾空白/全角空格后）严格等于 `QUOTE_CARD_COMMAND`、冷却已过。
被引用消息没有任何可渲染内容（纯图片/语音/合并转发等）时静默不回复。
同一群同一用户受冷却限制；渲染串行执行（单并发），避免 CPU 打满。

卡片版式：1280×720 PNG；文字上限 `QUOTE_CARD_MAX_CHARS` 个内容单元（emoji/表情各算 1，
超长时保留头尾、中间用 `……`）；署名优先取实时群名片（`get_group_member_info`，失败回退
消息内的 sender 名片/昵称）。

## 配置

所有配置通过环境变量读取，均有默认值。

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `QUOTE_CARD_ENABLED` | `false` | 插件总开关；`true/1/yes/on` 开启 |
| `QUOTE_CARD_GROUPS` | 空 | 生效群号列表，逗号/空格/分号分隔；**空 = 所有群都不响应** |
| `QUOTE_CARD_COMMAND` | `名言` | 触发命令文本（严格匹配，忽略首尾空白/全角空格） |
| `QUOTE_CARD_MAX_CHARS` | `100` | 内容单元上限（最小 10），超出保留头尾并中间省略 |
| `QUOTE_CARD_COOLDOWN_SECONDS` | `10` | 同群同用户冷却秒数（0 = 不限制） |
| `QUOTE_CARD_AVATAR_CACHE_DIR` | `data/quote_card/avatars` | 头像文件缓存目录（相对 bot 运行目录；可写绝对路径） |
| `QUOTE_CARD_AVATAR_TTL_HOURS` | `6` | 头像缓存有效期（小时，0 = 不过期） |
| `QUOTE_CARD_AVATAR_MAX_FILES` | `500` | 头像缓存文件上限（最小 10），超出按 mtime 清理最旧 |
| `QUOTE_CARD_AVATAR_TIMEOUT` | `10` | 头像下载超时秒数（最小 1） |
| `QUOTE_CARD_FONT_DIR` | `data/quote_card/fonts` | 字体目录（相对 bot 运行目录；可写绝对路径） |
| `QUOTE_CARD_ACCENT` | `gold` | 引号颜色：`gold`（暖金）或 `white`（白） |

## 字体

把字体放进 `QUOTE_CARD_FONT_DIR`，文件名需与下面一致（可换成任意 FreeType 字体后改
`render.py` 里的文件名常量）：

| 文件名 | 必需 | 用途 |
|---|---|---|
| `NotoSerifCJK-Bold.ttc` | 是 | 正文（TTC 集合 index=2，即简体中文；非 TTC 字体自动回退 index=0） |
| `NotoSerifCJK-Regular.ttc` | 是 | 右下角署名 |
| `NotoColorEmoji.ttf` | 否 | 彩色 emoji；缺失时 emoji 自动回退普通字体渲染，不影响出图 |

- 必需字体缺失时插件启动日志会报错并停用渲染，运行时报明确错误（提示 `QUOTE_CARD_FONT_DIR`）。
- 推荐字体：Noto Serif CJK SC（正文/署名）、Noto Color Emoji（彩色 emoji）。
- 字体文件较大且涉及各自许可，仓库不附带，请自行下载并遵守字体 License。

## 隐私说明

- 头像来自 `q.qlogo.cn` 的公开 QQ 头像接口，按被引用消息的发送者 QQ 号下载，
  仅缓存在本地 `QUOTE_CARD_AVATAR_CACHE_DIR`，不会上传到任何第三方。
- 除头像下载外，本插件不访问网络；生成卡片只使用被引用消息的文本/表情/发送者名片。
- 日志只输出群号、目标 QQ 号、内容单元数与耗时，不落盘消息原文；渲染图片仅在本次回复中发送。
- 卡片内容来自用户消息，请自行确认群规与隐私要求后再启用。

## 维护模式

本项目来自个人 bot 部署的开源整理版，按「被动维护」模式提供：
功能已满足自用需求，欢迎 issue/PR 修 bug 与适配新版本，但不保证持续功能开发。
生产环境自用配置为 NapCat + NoneBot2 + OneBot v11。

## License

MIT，见仓库根目录 [LICENSE](../../LICENSE)。
