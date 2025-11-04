#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库升级脚本 - 添加企业微信支持字段
执行此脚本以添加新的数据库字段：notification_type 和 wecom_webhook
"""

import pymysql
import json
import os

def upgrade_database():
    """升级数据库，添加企业微信相关字段"""
    
    # 读取数据库配置
    config_path = os.path.join(os.path.dirname(__file__), 'mysql.json')
    try:
        with open(config_path, 'r') as f:
            db_config = json.load(f)
    except FileNotFoundError:
        print("错误: 数据库配置文件 'mysql.json' 未找到。")
        return False
    except json.JSONDecodeError:
        print("错误: 'mysql.json' 文件格式不正确。")
        return False
    
    # 连接数据库
    try:
        connection = pymysql.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database'],
            charset='utf8mb4'
        )
        
        print(f"✓ 成功连接到数据库: {db_config['database']}")
        
        with connection.cursor() as cursor:
            # 检查字段是否已存在
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'config' 
                AND COLUMN_NAME = 'notification_type'
            """, (db_config['database'],))
            
            notification_type_exists = cursor.fetchone()[0] > 0
            
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'config' 
                AND COLUMN_NAME = 'wecom_webhook'
            """, (db_config['database'],))
            
            wecom_webhook_exists = cursor.fetchone()[0] > 0
            
            # 添加 notification_type 字段
            if not notification_type_exists:
                print("→ 添加字段: notification_type")
                cursor.execute("""
                    ALTER TABLE config 
                    ADD COLUMN notification_type VARCHAR(20) DEFAULT 'none'
                    AFTER dingtalk_secret
                """)
                print("✓ 字段 notification_type 添加成功")
            else:
                print("✓ 字段 notification_type 已存在，跳过")
            
            # 添加 wecom_webhook 字段
            if not wecom_webhook_exists:
                print("→ 添加字段: wecom_webhook")
                cursor.execute("""
                    ALTER TABLE config 
                    ADD COLUMN wecom_webhook VARCHAR(255) NULL
                    AFTER notification_type
                """)
                print("✓ 字段 wecom_webhook 添加成功")
            else:
                print("✓ 字段 wecom_webhook 已存在，跳过")
            
            # 提交更改
            connection.commit()
            print("\n✓ 数据库升级成功！")
            return True
            
    except pymysql.Error as e:
        print(f"✗ 数据库错误: {e}")
        return False
    
    finally:
        if 'connection' in locals():
            connection.close()
            print("✓ 数据库连接已关闭")

if __name__ == '__main__':
    print("=" * 50)
    print("数据库升级脚本")
    print("功能: 添加企业微信通知支持")
    print("=" * 50)
    print()
    
    success = upgrade_database()
    
    print()
    if success:
        print("✓ 升级完成！现在可以启动应用程序了。")
    else:
        print("✗ 升级失败，请检查错误信息。")

