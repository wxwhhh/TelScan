#!/bin/bash

# ========================================================
# Ubuntu 一键安装 MySQL 并配置 telegram1 数据库（使用默认端口 3306）
# 数据库：telegram1
# 用户：telegram1，密码：telegram&m910
# 字符集：utf8mb4
# 主机：localhost（仅本地访问）
# ========================================================

set -e

echo "🚀 开始安装并配置 MySQL + telegram1 数据库（使用默认端口 3306）..."

# 1. 更新系统
echo "🔄 更新包列表..."
sudo apt update -y

# 2. 安装 MySQL 服务器
echo "📦 安装 MySQL 服务器..."
sudo apt install -y mysql-server

# 3. 启动并启用服务
echo "⚙️ 启动 MySQL 服务..."
sudo systemctl start mysql
sudo systemctl enable mysql

# 4. 检查状态
if ! sudo systemctl is-active --quiet mysql; then
    echo "❌ MySQL 服务启动失败，请检查日志：sudo journalctl -u mysql"
    exit 1
fi

echo "✅ MySQL 服务已启动并设置为开机自启（端口：3306）"

# 5. 创建数据库和用户
echo "🔧 创建数据库 'telegram1' 和用户 'telegram1'..."

sudo mysql << 'EOF'
CREATE DATABASE IF NOT EXISTS telegram1
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'telegram1'@'localhost' 
IDENTIFIED BY 'telegram&m910';

GRANT ALL PRIVILEGES ON telegram1.* TO 'telegram1'@'localhost';

FLUSH PRIVILEGES;
EOF

echo "✅ 数据库和用户创建完成"

# 6. 打印连接信息
echo
echo "=============================================="
echo "🎉 安装与配置完成！"
echo "=============================================="
echo "📊 数据库信息："
echo "   名称: telegram1"
echo "   字符集: utf8mb4"
echo "   主机: 127.0.0.1"
echo "   端口: 3306"
echo "   用户: telegram1"
echo "   密码: telegram&m910"
echo "💡 提示："
echo "   - root 用户可执行 'sudo mysql -u root' 无密码登录"
echo "   - 用户仅允许本地连接，安全"
echo "=============================================="