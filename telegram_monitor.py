import asyncio
import threading
from datetime import datetime
import requests
import time
import hmac
import hashlib
import base64
import urllib.parse
from urllib.parse import urlparse
from telethon import TelegramClient, events
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import ahocorasick
from concurrent.futures import ThreadPoolExecutor
import os

from database import Config, MonitoredGroup, Keyword, MatchedMessage, DB_URI

client_instance = None
client_thread = None
is_running = False
main_loop = None
client_ready = threading.Event()
stop_event = threading.Event() #  <-- 新增: 用于控制线程停止

# 性能优化: AC自动机缓存
keyword_automatons = {}  # {group_id: automaton} 缓存每个群组的AC自动机
automatons_lock = threading.Lock()  # 线程安全锁

# OCR异步处理: 线程池（最多2个OCR任务并发）
ocr_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="OCR")

# WebSocket消息推送回调函数（由 app.py 设置）
websocket_broadcast_callback = None

def get_db_session():
    engine = create_engine(DB_URI)
    Session = sessionmaker(bind=engine)
    return Session()

def process_ocr_sync(photo_path):
    """
    同步OCR处理函数（在线程池中运行）
    返回: (ocr_text, error)
    """
    try:
        from PIL import Image
        import pytesseract
        
        image = Image.open(photo_path)
        ocr_text = pytesseract.image_to_string(image, lang='chi_sim+eng')
        print(f"[OCR异步] 识别完成: {ocr_text[:100]}...")
        
        # 删除临时文件
        if os.path.exists(photo_path):
            os.remove(photo_path)
        
        return (ocr_text, None)
    except ImportError as e:
        print(f"[OCR异步] 警告: 未安装 pytesseract 或 Pillow - {e}")
        return (None, "未安装OCR依赖")
    except Exception as e:
        print(f"[OCR异步] 识别失败: {e}")
        return (None, str(e))

def handle_ocr_result(future, event_data, group_obj, automaton):
    """
    OCR结果回调函数（在线程池完成后调用）
    """
    try:
        ocr_text, error = future.result()
        
        if error:
            print(f"[OCR异步] 处理失败，跳过: {error}")
            return
        
        if not ocr_text or not ocr_text.strip():
            print(f"[OCR异步] 未识别到文字")
            return
        
        # 组合消息文本
        message_text = event_data['original_text']
        if message_text:
            message_text = f"{message_text}\n[图片文字]: {ocr_text}".strip()
        else:
            message_text = f"[图片文字]: {ocr_text}".strip()
        
        # 使用AC自动机匹配关键词
        message_lower = message_text.lower()
        matched_keyword_text = None
        
        for end_index, keyword_text in automaton.iter(message_lower):
            # automaton 现在返回字符串，不是对象
            matched_keyword_text = keyword_text
            break
        
        if matched_keyword_text:
            print(f"[OCR异步] 在图片文字中找到关键词 '{matched_keyword_text}'")
            
            # 保存匹配结果
            session = get_db_session()
            try:
                new_message = MatchedMessage(
                    group_name=event_data['group_name'],
                    message_content=message_text,
                    sender=event_data['sender'],
                    message_date=datetime.now(),
                    matched_keyword=matched_keyword_text
                )
                session.add(new_message)
                session.commit()
                print(f"[OCR异步] 保存成功: 群组 '{event_data['group_name']}' 关键词 '{matched_keyword_text}'")
                
                # WebSocket 实时推送
                if websocket_broadcast_callback:
                    try:
                        websocket_broadcast_callback({
                            'group_name': event_data['group_name'],
                            'sender': event_data['sender'] or 'N/A',
                            'matched_keyword': matched_keyword_text,
                            'message_content': message_text[:200] + '...' if len(message_text) > 200 else message_text,
                            'message_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'is_image': True
                        })
                    except Exception as e:
                        print(f"[OCR异步] WebSocket推送失败: {e}")
                
                # 发送通知
                config = session.query(Config).first()
                if config:
                    title = f"关键词 '{matched_keyword_text}' 触发"
                    notification_message = (
                        f"#### **关键词监控提醒（图片识别）**\n\n"
                        f"> **群组**: {event_data['group_name']}\n\n"
                        f"> **发送人**: {event_data['sender'] or 'N/A'}\n\n"
                        f"> **关键词**: {matched_keyword_text}\n\n"
                        f"> **消息内容**: {message_text}\n"
                    )
                    
                    # 根据配置发送到不同的通知渠道
                    if config.notification_type == 'dingtalk' and config.dingtalk_webhook:
                        send_to_dingtalk(config.dingtalk_webhook, config.dingtalk_secret, title, notification_message)
                    elif config.notification_type == 'wecom' and config.wecom_webhook:
                        send_to_wecom(config.wecom_webhook, title, notification_message)
            finally:
                session.close()
        else:
            print(f"[OCR异步] 图片文字中未找到关键词")
            
    except Exception as e:
        print(f"[OCR异步] 回调处理失败: {e}")

def build_keyword_automaton(keywords):
    """
    为一组关键词构建Aho-Corasick自动机
    性能优化: 将多个关键词编译成状态机,实现O(n)时间复杂度的多模式匹配
    
    Args:
        keywords: 关键词对象列表
    
    Returns:
        automaton: 构建好的AC自动机
    """
    automaton = ahocorasick.Automaton()
    
    for keyword in keywords:
        # 将关键词的小写形式和文本字符串关联（不存储对象，避免会话分离）
        keyword_text = keyword.text  # 立即提取字符串
        automaton.add_word(keyword_text.lower(), keyword_text)
    
    # 构建失败指针,完成自动机
    automaton.make_automaton()
    
    return automaton

def is_safe_url(url):
    try:
        parsed_url = urlparse(url)
        if parsed_url.scheme not in ['http', 'https']:
            return False
        # 限制为钉钉的官方域名
        allowed_domains = ['oapi.dingtalk.com']
        if parsed_url.netloc not in allowed_domains:
            return False
        return True
    except Exception:
        return False

def send_to_dingtalk(webhook_url, secret, title, message, is_test=False):
    if not webhook_url:
        if is_test: return "钉钉Webhook未配置。"
        print("钉钉Webhook未配置，跳过发送。")
        return
    
    if not is_safe_url(webhook_url):
        error_msg = f"检测到不安全的Webhook URL: {webhook_url}"
        print(error_msg)
        if is_test: return error_msg
        return

    if secret:
        timestamp = str(round(time.time() * 1000))
        secret_enc = secret.encode('utf-8')
        string_to_sign = '{}\n{}'.format(timestamp, secret)
        string_to_sign_enc = string_to_sign.encode('utf-8')
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        webhook_url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"

    headers = {'Content-Type': 'application/json;charset=utf-8'}
    data = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": message
        }
    }
    try:
        response = requests.post(webhook_url, headers=headers, json=data)
        if response.status_code == 200 and response.json().get("errcode") == 0:
            print("成功发送钉钉通知。")
            if is_test: return "测试消息发送成功！"
        else:
            print(f"发送钉钉通知失败: {response.text}")
            if is_test: return f"发送失败: {response.text}"
    except Exception as e:
        print(f"发送钉钉通知时发生异常: {e}")
        if is_test: return f"发生异常: {e}"

def send_to_wecom(webhook_url, title, message, is_test=False):
    """
    发送消息到企业微信机器人
    
    参数:
        webhook_url: 企业微信机器人webhook地址
        title: 消息标题
        message: 消息内容（markdown格式）
        is_test: 是否为测试消息
    
    返回:
        如果is_test=True，返回发送结果信息字符串
    """
    if not webhook_url:
        if is_test:
            return "企业微信Webhook未配置。"
        print("企业微信Webhook未配置，跳过发送。")
        return
    
    # 安全检查：验证URL格式
    try:
        parsed_url = urlparse(webhook_url)
        if parsed_url.scheme not in ['http', 'https']:
            error_msg = "企业微信Webhook URL协议不正确（必须是http/https）"
            print(error_msg)
            if is_test:
                return error_msg
            return
        # 限制为企业微信的官方域名
        allowed_domains = ['qyapi.weixin.qq.com']
        if parsed_url.netloc not in allowed_domains:
            error_msg = f"检测到不安全的Webhook URL: {webhook_url}"
            print(error_msg)
            if is_test:
                return error_msg
            return
    except Exception as e:
        error_msg = f"Webhook URL格式错误: {e}"
        print(error_msg)
        if is_test:
            return error_msg
        return
    
    # 构造企业微信markdown消息格式
    headers = {'Content-Type': 'application/json;charset=utf-8'}
    data = {
        "msgtype": "markdown",
        "markdown": {
            "content": f"### {title}\n{message}"
        }
    }
    
    try:
        response = requests.post(webhook_url, headers=headers, json=data, timeout=5)
        if response.status_code == 200:
            result = response.json()
            if result.get("errcode") == 0:
                print("成功发送企业微信通知。")
                if is_test:
                    return "测试消息发送成功！"
            else:
                error_msg = f"发送失败: {result.get('errmsg', '未知错误')}"
                print(f"发送企业微信通知失败: {error_msg}")
                if is_test:
                    return error_msg
        else:
            error_msg = f"HTTP状态码: {response.status_code}"
            print(f"发送企业微信通知失败: {error_msg}")
            if is_test:
                return f"发送失败: {error_msg}"
    except Exception as e:
        print(f"发送企业微信通知时发生异常: {e}")
        if is_test:
            return f"发生异常: {e}"

async def start_client_async(api_id, api_hash, phone_number):
    global client_instance, is_running
    
    client = TelegramClient('telegram_session', api_id, api_hash, system_version="4.16.30-vxCUSTOM")
    client_instance = client
        
    @client.on(events.NewMessage)
    async def handler(event):
        chat = await event.get_chat()
        print(f"[调试] 收到新消息, 来自群组: '{getattr(chat, 'title', '未知群组')}' (ID: {chat.id})")

        session_handler = get_db_session() 
        try:
            sender = await event.get_sender()

            group_name = getattr(chat, 'title', '未知群组')
            sender_name = None 
            if sender:
                sender_name = getattr(sender, 'username', None)
                if not sender_name: 
                    first_name = getattr(sender, 'first_name', '') or ''
                    last_name = getattr(sender, 'last_name', '') or ''
                    sender_name = f"{first_name} {last_name}".strip()
            
            if sender_name is None and hasattr(chat, 'title'):
                sender_name = chat.title

            standard_chat_id = str(chat.id)
            if standard_chat_id.startswith('-100'):
                standard_chat_id = standard_chat_id[4:]
            
            all_monitored_ids = [g.group_identifier for g in session_handler.query(MonitoredGroup).all()]
            
            standard_monitored_ids = []
            for mid in all_monitored_ids:
                if mid.startswith('-100'):
                    standard_monitored_ids.append(mid[4:])
                else:
                    standard_monitored_ids.append(mid)

            current_group_obj = None
            
            if standard_chat_id in standard_monitored_ids:
                original_id = None
                for mid in all_monitored_ids:
                    if mid.endswith(standard_chat_id):
                        original_id = mid
                        break
                if original_id:
                    current_group_obj = session_handler.query(MonitoredGroup).filter_by(group_identifier=original_id).first()

            if not current_group_obj and hasattr(chat, 'username') and chat.username in all_monitored_ids:
                current_group_obj = session_handler.query(MonitoredGroup).filter_by(group_identifier=chat.username).first()


            if current_group_obj:
                print(f"[调试] 群组 '{getattr(chat, 'title', '未知')}' 在监控列表中。开始检查关键词...")
                keywords_to_check = current_group_obj.keywords
                
                if not keywords_to_check:
                    print(f"[调试] 注意: 群组 '{getattr(chat, 'title', '未知')}' 没有配置任何关键词。")
                else:
                    keyword_texts = [k.text for k in keywords_to_check]
                    print(f"[调试] 为该群组配置的关键词: {keyword_texts}")

                    # 获取要匹配的文本内容
                    message_text = event.message.message or ""
                    
                    # 性能优化: 使用AC自动机进行高效匹配
                    # 获取或构建该群组的自动机（带缓存）
                    with automatons_lock:
                        if current_group_obj.id not in keyword_automatons:
                            print(f"[性能优化] 首次为群组 '{group_name}' 构建AC自动机...")
                            keyword_automatons[current_group_obj.id] = build_keyword_automaton(keywords_to_check)
                        
                        automaton = keyword_automatons[current_group_obj.id]
                    
                    # 先处理文本消息（不阻塞）
                    message_lower = message_text.lower()
                    matched_keyword_text = None
                    
                    for end_index, keyword_text in automaton.iter(message_lower):
                        # automaton 现在返回字符串，不是对象
                        matched_keyword_text = keyword_text
                        break
                    
                    if matched_keyword_text:
                        print(f"[调试] 成功! 在消息中找到关键词 '{matched_keyword_text}'。")
                        new_message = MatchedMessage(
                            group_name=group_name,
                            message_content=message_text,
                            sender=sender_name,
                            message_date=datetime.now(),
                            matched_keyword=matched_keyword_text
                        )
                        session_handler.add(new_message)
                        session_handler.commit()
                        print(f"在群组 '{group_name}' 中匹配到关键词 '{matched_keyword_text}'")
                        
                        # WebSocket 实时推送
                        if websocket_broadcast_callback:
                            try:
                                websocket_broadcast_callback({
                                    'group_name': group_name,
                                    'sender': sender_name or 'N/A',
                                    'matched_keyword': matched_keyword_text,
                                    'message_content': message_text[:200] + '...' if len(message_text) > 200 else message_text,
                                    'message_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'is_image': False
                                })
                            except Exception as e:
                                print(f"[WebSocket] 推送失败: {e}")

                        config = session_handler.query(Config).first()
                        if config:
                            title = f"关键词 '{matched_keyword_text}' 触发"
                            notification_message = (
                                f"#### **关键词监控提醒**\n\n"
                                f"> **群组**: {group_name}\n\n"
                                f"> **发送人**: {sender_name or 'N/A'}\n\n"
                                f"> **关键词**: {matched_keyword_text}\n\n"
                                f"> **消息内容**: {message_text}\n"
                            )
                            
                            # 根据配置发送到不同的通知渠道
                            if config.notification_type == 'dingtalk' and config.dingtalk_webhook:
                                send_to_dingtalk(config.dingtalk_webhook, config.dingtalk_secret, title, notification_message)
                            elif config.notification_type == 'wecom' and config.wecom_webhook:
                                send_to_wecom(config.wecom_webhook, title, notification_message)
                    
                    # OCR异步处理: 如果消息包含图片，提交到线程池处理（不阻塞）
                    if event.message.photo:
                        print(f"[OCR异步] 检测到图片消息，提交到线程池处理...")
                        try:
                            # 下载图片（这是异步操作，但下载必须在这里完成）
                            photo_path = await event.message.download_media()
                            if photo_path:
                                # 准备事件数据
                                event_data = {
                                    'group_name': group_name,
                                    'sender': sender_name,
                                    'original_text': message_text
                                }
                                
                                # 提交到线程池进行OCR处理（不阻塞主流程）
                                future = ocr_executor.submit(process_ocr_sync, photo_path)
                                # 添加回调函数
                                future.add_done_callback(
                                    lambda f: handle_ocr_result(f, event_data, current_group_obj, automaton)
                                )
                                print(f"[OCR异步] 图片已提交到线程池，继续处理下一条消息...")
                        except Exception as e:
                            print(f"[OCR异步] 下载图片失败: {e}")
            else:
                print(f"[调试] 群组 '{getattr(chat, 'title', '未知')}' (ID: {chat.id}) 不在监控列表中，已忽略。")
        finally:
            session_handler.close() 

    while not stop_event.is_set():
        try:
            print("正在尝试连接到Telegram...")
            await client.connect()
            if not await client.is_user_authorized():
                await client.send_code_request(phone_number)
                try:
                    await client.sign_in(phone_number, input('请输入telegram发来的验证码: '))
                except Exception:
                    await client.sign_in(password=input('请输入两步验证密码: '))

            is_running = True
            print("Telegram客户端已成功连接并开始监听...")
            client_ready.set()
            
            await client.run_until_disconnected()

        except ConnectionError:
            print("与Telegram的连接丢失。将在60秒后尝试重新连接...")
        
        except Exception as e:
            print(f"监控时发生未知错误: {e}。将在60秒后尝试重新连接...")

        finally:
            is_running = False
            client_ready.clear()
            if client.is_connected():
                await client.disconnect()
            print("客户端连接已断开。")

            if not stop_event.is_set():
                await asyncio.sleep(60)
    
    print("监控线程已正常停止。")


def run_in_thread(loop, coro):
    global main_loop
    main_loop = loop 
    asyncio.set_event_loop(loop)
    loop.run_until_complete(coro)

def start_monitoring():
    global client_thread, is_running, main_loop
    
    if client_thread and client_thread.is_alive():
        print("监控已经在运行中。")
        return
    
    stop_event.clear() # <-- 新增: 重置停止事件
    client_ready.clear() 
    session = get_db_session()
    config = session.query(Config).first()
    session.close()

    if not (config and config.api_id and config.api_hash and config.phone_number):
        return
    
    loop = asyncio.new_event_loop()
    main_loop = loop
    
    coro = start_client_async(config.api_id, config.api_hash, config.phone_number)
    
    client_thread = threading.Thread(target=run_in_thread, args=(loop, coro))
    client_thread.daemon = True
    client_thread.start()

def stop_monitoring():
    global client_instance, is_running, client_thread, main_loop
    if not (client_thread and client_thread.is_alive()):
        return

    stop_event.set() # <-- 新增: 设置停止事件

    if main_loop and main_loop.is_running():
        main_loop.call_soon_threadsafe(
            lambda: asyncio.create_task(client_instance.disconnect())
        )
    
    client_thread.join(timeout=5)
    
    is_running = False
    main_loop = None
    client_thread = None