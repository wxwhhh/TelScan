import os
import json
import uuid
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

db_config = None
config_path = os.path.join(os.path.dirname(__file__), 'mysql.json')

try:
    with open(config_path, 'r') as f:
        db_config = json.load(f)
except FileNotFoundError:
    print(f"错误: 数据库配置文件 'mysql.json' 未找到。")
    print("请根据模板创建一个，并填入您的MySQL服务器信息。")
    exit()
except json.JSONDecodeError:
    print(f"错误: 'mysql.json' 文件格式不正确，请检查是否为有效的JSON。")
    exit()

DB_URI = (
    f"mysql+pymysql://{db_config['user']}:{db_config['password']}"
    f"@{db_config['host']}:{db_config['port']}/{db_config['database']}"
    "?charset=utf8mb4"
)

basedir = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(basedir, 'instance')
os.makedirs(instance_path, exist_ok=True)
db_path = os.path.join(instance_path, 'monitoring.sqlite')

db = SQLAlchemy()

def get_session():
    engine = create_engine(DB_URI)
    Session = sessionmaker(bind=engine)
    return Session()

class Config(db.Model):
    __tablename__ = 'config'
    id = db.Column(db.Integer, primary_key=True)
    api_id = db.Column(db.String(100), nullable=True)
    api_hash = db.Column(db.String(100), nullable=True)
    phone_number = db.Column(db.String(100), nullable=True)
    dingtalk_webhook = db.Column(db.String(255), nullable=True)
    dingtalk_secret = db.Column(db.String(100), nullable=True)
    notification_type = db.Column(db.String(20), default='none')  # none/dingtalk/wecom
    wecom_webhook = db.Column(db.String(255), nullable=True)

    __table_args__ = {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}

group_keyword_association = db.Table('group_keyword_association',
    db.Column('group_id', db.Integer, db.ForeignKey('monitored_group.id'), primary_key=True),
    db.Column('keyword_id', db.Integer, db.ForeignKey('keyword.id'), primary_key=True)
)

class MonitoredGroup(db.Model):
    __tablename__ = 'monitored_group'
    id = db.Column(db.Integer, primary_key=True)
    group_identifier = db.Column(db.String(191), unique=True, nullable=False)
    group_name = db.Column(db.String(255), nullable=True)
    logo_path = db.Column(db.String(255), nullable=True)
    keywords = db.relationship('Keyword', secondary=group_keyword_association, back_populates='groups')

    __table_args__ = {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}

class Keyword(db.Model):
    __tablename__ = 'keyword'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(191), unique=True, nullable=False)
    groups = db.relationship('MonitoredGroup', secondary=group_keyword_association, back_populates='keywords')

    __table_args__ = {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}

class MatchedMessage(db.Model):
    __tablename__ = 'matched_message'
    id = db.Column(db.Integer, primary_key=True)
    group_name = db.Column(db.String(255), nullable=False)
    message_content = db.Column(db.Text, nullable=False)
    sender = db.Column(db.String(255), nullable=True)
    message_date = db.Column(db.DateTime, nullable=False)
    matched_keyword = db.Column(db.String(100), nullable=False)

    __table_args__ = {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}


# 新增User模型，用于存储用户信息
class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(191), unique=True, nullable=False) # 191 for utf8mb4 index compatibility
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    sessions = db.relationship('Session', backref='user', lazy=True)

    __table_args__ = {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}

# 新增Session模型，用于存储用户登录会话信息
class Session(db.Model):
    __tablename__ = 'session'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4())) # UUID作为主键
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    expiration_time = db.Column(db.DateTime, nullable=False)

    __table_args__ = {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}


def auto_upgrade_database():
    """
    自动升级数据库结构
    检查并添加缺失的字段，确保数据库结构与模型定义一致
    """
    import pymysql
    
    try:
        # 连接数据库
        connection = pymysql.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database'],
            charset='utf8mb4'
        )
        
        print("[数据库] 开始检查数据库结构...")
        
        with connection.cursor() as cursor:
            # 检查 notification_type 字段是否存在
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'config' 
                AND COLUMN_NAME = 'notification_type'
            """, (db_config['database'],))
            
            notification_type_exists = cursor.fetchone()[0] > 0
            
            # 检查 wecom_webhook 字段是否存在
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
                print("[数据库] → 添加字段: notification_type")
                cursor.execute("""
                    ALTER TABLE config 
                    ADD COLUMN notification_type VARCHAR(20) DEFAULT 'none'
                    AFTER dingtalk_secret
                """)
                print("[数据库] ✓ 字段 notification_type 添加成功")
            
            # 添加 wecom_webhook 字段
            if not wecom_webhook_exists:
                print("[数据库] → 添加字段: wecom_webhook")
                cursor.execute("""
                    ALTER TABLE config 
                    ADD COLUMN wecom_webhook VARCHAR(255) NULL
                    AFTER notification_type
                """)
                print("[数据库] ✓ 字段 wecom_webhook 添加成功")
            
            # 提交更改
            connection.commit()
            
            if not notification_type_exists or not wecom_webhook_exists:
                print("[数据库] ✓ 数据库结构升级完成")
            else:
                print("[数据库] ✓ 数据库结构已是最新版本")
            
    except pymysql.Error as e:
        print(f"[数据库] ✗ 升级失败: {e}")
        print(f"[数据库] 提示: 请检查数据库权限或手动运行 upgrade_db.py")
    
    except Exception as e:
        print(f"[数据库] ✗ 发生错误: {e}")
    
    finally:
        if 'connection' in locals():
            connection.close()
