#!/bin/bash
set -e

# 安装 uv（如果没有）
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# 安装依赖
uv sync

# 安装 Playwright 浏览器
uv run playwright install chromium

echo ""
echo "✅ 安装完成！"
echo ""
echo "用法:"
echo "  uv run autoteam --help"
echo "  uv run autoteam rotate"
