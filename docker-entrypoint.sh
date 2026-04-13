#!/bin/bash
set -e

# 清理残留锁文件并启动虚拟显示器
rm -f /tmp/.X99-lock
Xvfb :99 -screen 0 1280x800x24 &
export DISPLAY=:99

# 确保数据目录存在
mkdir -p /app/data

# 软链数据文件到工作目录（始终创建软链，保证写入持久化到 data/）
for f in .env accounts.json state.json; do
    # 如果 data 里没有但容器内有，先复制过去
    if [ ! -f "/app/data/$f" ] && [ -f "/app/$f" ] && [ ! -L "/app/$f" ]; then
        cp "/app/$f" "/app/data/$f"
    fi
    # 如果 data 里没有，创建空文件
    if [ ! -f "/app/data/$f" ]; then
        touch "/app/data/$f"
    fi
    # 创建软链
    ln -sf "/app/data/$f" "/app/$f"
done

# 软链目录
for d in auths screenshots; do
    mkdir -p "/app/data/$d"
    if [ ! -L "/app/$d" ]; then
        rm -rf "/app/$d"
        ln -sf "/app/data/$d" "/app/$d"
    fi
done

# 执行命令
exec uv run autoteam "$@"
