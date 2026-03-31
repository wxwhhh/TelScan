#!/bin/bash
# TelScan 管理员密码重置脚本
# 用法: bash reset_password.sh [新密码]
# 不传参数则自动生成随机密码

CONTAINER="telscan-mysql"
DB_USER="telegram1"
DB_PASS="telegram&m910"
DB_NAME="telegram1"

if [ -n "$1" ]; then
    NEW_PW="$1"
else
    NEW_PW=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
fi

HASH=$(python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('$NEW_PW'))")

docker exec "$CONTAINER" mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" \
  -e "UPDATE user SET password_hash='$HASH' WHERE username='admin';" 2>/dev/null

echo "============================================"
echo "✅ 管理员密码已更新！"
echo "   用户名: admin"
echo "   密码:   $NEW_PW"
echo "============================================"
