"""pytest 公共配置 / 全局 fixture。

插件模块顶层会注册 matcher，所以必须先 ``nonebot.init()`` 再 import 插件。
所有测试均离线：不启动 NoneBot、不连接 NapCat、不发消息。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# 在初始化/导入插件之前提供干净的假环境（默认关闭、群列表为空）
os.environ["QUOTE_CARD_ENABLED"] = "false"
os.environ["QUOTE_CARD_GROUPS"] = ""

import nonebot  # noqa: E402

nonebot.init(driver="~none")

# 系统字体（渲染测试用；缺失时相关测试 skip，不下载任何字体）
DEJAVU_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
DEJAVU_REGULAR = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


@pytest.fixture(autouse=True)
def _clean_quote_card_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """隔离宿主环境变量，避免影响配置默认值测试。"""
    for key in list(os.environ):
        if key.startswith("QUOTE_CARD_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture(scope="session")
def font_dir(tmp_path_factory: pytest.TempPathFactory) -> str:
    """把系统 DejaVu 字体按插件约定的文件名软链到临时目录（先检查存在）。"""
    if not DEJAVU_BOLD.is_file() or not DEJAVU_REGULAR.is_file():
        pytest.skip("系统 DejaVu 字体不存在，跳过渲染测试")
    root = tmp_path_factory.mktemp("quote_card_fonts")
    os.symlink(DEJAVU_BOLD, root / "NotoSerifCJK-Bold.ttc")
    os.symlink(DEJAVU_REGULAR, root / "NotoSerifCJK-Regular.ttc")
    return str(root)


@pytest.fixture(scope="session")
def font_dir_no_emoji(font_dir: str) -> str:
    """必需字体齐全、但**没有**彩色 emoji 字体的目录（验证 emoji 回退）。"""
    return font_dir
