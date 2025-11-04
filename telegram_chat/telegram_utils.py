import os
import asyncio
from telethon import TelegramClient
from urllib.parse import urlparse
import concurrent.futures
import time
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.errors import (
    ChannelPrivateError, ChannelInvalidError, UserBannedInChannelError,
    ChannelsTooMuchError, UserAlreadyParticipantError
)

import telegram_monitor

# from app import batch_join_tasks, tasks_lock  <-- This line is removed from here

basedir = os.path.abspath(os.path.dirname(__file__))

async def get_group_details_async(group_identifier):
    client = telegram_monitor.client_instance
    if not (client and client.is_connected()):
        return {'error': '监控客户端未运行或未连接。'}

    try:
        path = urlparse(group_identifier).path.strip('/')
        if '/' in path:
            identifier = path.split('/')[-1]
        else:
            identifier = path
            
        try:
            entity = await client.get_entity(identifier)
        except (ValueError, TypeError):
            return {'error': f"找不到群组 '{identifier}'。请检查链接或用户名。"}

        group_id = entity.id
        group_name = entity.title

        logo_dir = os.path.join(basedir, 'static', 'logos')
        os.makedirs(logo_dir, exist_ok=True)
        logo_filename = f"{group_id}.jpg"
        logo_abs_path = os.path.join(logo_dir, logo_filename)
        
        path = await client.download_profile_photo(entity, file=logo_abs_path)
        
        logo_rel_path = f"logos/{logo_filename}" if path else None

        return {
            'success': True,
            'identifier': str(group_id),
            'name': group_name,
            'logo_path': logo_rel_path
        }

    except Exception as e:
        return {'error': f'发生未知错误: {e}'}

def get_group_details(group_identifier):
    for _ in range(10): 
        if telegram_monitor.client_instance and telegram_monitor.client_instance.is_connected() and telegram_monitor.main_loop:
            break
        time.sleep(1)
    else:
        return {'error': '监控客户端未能成功连接或启动超时。请检查网络、API凭据或重启程序。'}
    
    current_loop = telegram_monitor.main_loop
    if not current_loop:
        return {'error': '事件循环丢失，这是一个严重错误，请重启程序。'}
    
    future = asyncio.run_coroutine_threadsafe(
        get_group_details_async(group_identifier), 
        current_loop
    )
    
    try:
        return future.result(timeout=20)
    except concurrent.futures.TimeoutError:
        return {'error': '操作超时，无法连接到Telegram。可能是网络问题。'}
    except Exception as e:
        return {'error': f'执行时发生错误: {e}'}

async def get_my_groups_async():
    client = telegram_monitor.client_instance
    if not (client and client.is_connected()):
        return {'error': '监控客户端未运行或未连接。'}

    groups = []
    try:
        all_dialogs = await client.get_dialogs()
        for dialog in all_dialogs:
            if dialog.is_group or dialog.is_channel:
                logo_rel_path = None
                logo_dir = os.path.join(basedir, 'static', 'logos')
                os.makedirs(logo_dir, exist_ok=True)
                logo_filename = f"{dialog.id}.jpg"
                logo_abs_path = os.path.join(logo_dir, logo_filename)
                
                try:
                    path = await client.download_profile_photo(dialog.entity, file=logo_abs_path)
                    if path:
                        logo_rel_path = f"logos/{logo_filename}"
                except Exception:
                    pass 

                groups.append({
                    'id': str(dialog.id),
                    'name': dialog.name,
                    'logo_path': logo_rel_path
                })
        return {'success': True, 'groups': groups}
    except Exception as e:
        return {'error': f'获取群组列表时发生错误: {e}'}

def get_my_groups():
    if not telegram_monitor.main_loop:
        return {'error': '事件循环未准备好。'}
    
    future = asyncio.run_coroutine_threadsafe(
        get_my_groups_async(), 
        telegram_monitor.main_loop
    )
    
    try:
        return future.result(timeout=60)
    except Exception as e:
        return {'error': f'执行时发生错误: {e}'}

async def batch_join_groups_async(task_id, links, delay, tasks_dict, lock_obj):
    client = telegram_monitor.client_instance
    if not (client and client.is_connected()):
        with lock_obj:
            task = tasks_dict[task_id]
            task['status'] = 'error'
            task['log'].append('[ERROR] 监控客户端未连接，任务无法执行。')
        return

    total_links = len(links)
    with lock_obj:
        task = tasks_dict[task_id]
        task['status'] = 'running'
        task['log'].append(f'[INFO] 任务开始，共 {total_links} 个群组链接。')
        if total_links > 20:
            task['log'].append(f'[WARN] 本次任务包含 {total_links} 个群组，超过20个。请注意，单日大量加群可能会增加账户风险。')
        if delay < 20:
            task['log'].append(f'[WARN] 用户设置间隔低于安全阈值，已强制使用20秒间隔。')
            delay = 20


    for i, link in enumerate(links):
        with lock_obj:
            task = tasks_dict[task_id]
            if task['stop_requested']:
                task['log'].append('[INFO] 检测到停止信号，任务已中止。')
                task['status'] = 'stopped'
                break
            task['current'] = i + 1
            task['log'].append(f'[ATTEMPT] ({i+1}/{total_links}) 正在尝试加入: {link}')
        
        try:
            parsed_link = urlparse(link)
            identifier = parsed_link.path.strip('/').split('/')[-1]
            if not identifier:
                with lock_obj:
                    tasks_dict[task_id]['log'].append('[ERROR] 链接格式不正确，已跳过。')
                continue

            entity = await client.get_entity(identifier)
            await client(JoinChannelRequest(entity))
            
            with lock_obj:
                task = tasks_dict[task_id]
                task['log'].append(f'[SUCCESS] 成功加入群组: {getattr(entity, "title", identifier)}')

        except (ChannelPrivateError, UserBannedInChannelError):
            with lock_obj:
                tasks_dict[task_id]['log'].append('[ERROR] 加入失败：群组是私有的或您被禁止加入。')
        except ChannelsTooMuchError:
            with lock_obj:
                task = tasks_dict[task_id]
                task['log'].append('[ERROR] 加入失败：您已加入过多的群组或频道。任务已中止。')
                task['status'] = 'error'
            break 
        except UserAlreadyParticipantError:
             with lock_obj:
                tasks_dict[task_id]['log'].append('[INFO] 您已经在这个群组里了，跳过。')
        except (ValueError, TypeError, ChannelInvalidError):
             with lock_obj:
                tasks_dict[task_id]['log'].append(f'[ERROR] 找不到群组 "{identifier}"，请检查链接是否正确。')
        except Exception as e:
            with lock_obj:
                tasks_dict[task_id]['log'].append(f'[ERROR] 发生未知错误: {str(e)}')
        
        if i < total_links - 1:
            with lock_obj:
                tasks_dict[task_id]['log'].append(f'[WAIT] 暂停 {delay} 秒...')
            time.sleep(delay)

    with lock_obj:
        task = tasks_dict[task_id]
        if task['status'] == 'running': 
            task['status'] = 'completed'
            task['log'].append('[INFO] 所有链接已处理完毕，任务完成！')

def batch_join_groups(task_id, links, delay, tasks_dict, lock_obj):
    loop = telegram_monitor.main_loop
    if not loop:
        with lock_obj:
            task = tasks_dict[task_id]
            task['status'] = 'error'
            task['log'].append('[ERROR] 事件循环丢失，这是一个严重错误，请重启程序。')
        return
    
    future = asyncio.run_coroutine_threadsafe(
        batch_join_groups_async(task_id, links, delay, tasks_dict, lock_obj), 
        loop
    )
    
    try:
        future.result()
    except Exception as e:
        with lock_obj:
            task = tasks_dict[task_id]
            task['status'] = 'error'
            task['log'].append(f'[FATAL] 执行时发生致命错误: {e}')
