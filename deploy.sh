#!/bin/bash
# LeBot2 部署脚本

PROJECT_DIR="/root/tgbot_Le"

echo "========================================="
echo "  LeBot2 部署脚本"
echo "========================================="

# 1. 拉取最新代码
echo "[1/3] 拉取最新代码..."
cd $PROJECT_DIR
git pull

# 2. 停止并删除旧容器
echo "[2/3] 停止旧容器..."
docker compose down

# 3. 重新构建并启动
echo "[3/3] 重新构建并启动..."
docker compose up -d --build

# 4. 查看状态
echo ""
echo "========================================="
echo "  服务状态"
echo "========================================="
docker compose ps

echo ""
echo "部署完成！"
echo "查看日志: docker compose logs -f"
