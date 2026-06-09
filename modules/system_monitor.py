import os
import psutil
import yaml
import requests
import subprocess
import time
from datetime import datetime, timedelta
import asyncio
import json
import pymysql
from pathlib import Path
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import GroupMessage
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Plain, Forward, ForwardNode
from graia.ariadne.model import Group, Member
from graia.saya import Channel
from graia.saya.builtins.broadcast.schema import ListenerSchema

channel = Channel.current()


def load_config():
    config_path = Path(__file__).parent / 'config' / 'psutil.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


from modules.config_loader import get_api_keys

config = load_config()
_api_keys = get_api_keys()
API_KEY = _api_keys.get('psutil') or _api_keys.get('deepseek') or ''
url = config['api']['deepseek']['balance_url']


def get_system_stats():
    stats = {}

    # 内存信息
    mem = psutil.virtual_memory()
    stats['memory_percent'] = mem.percent
    stats['memory_total'] = mem.total / (1024 * 1024 * 1024)  # GB
    stats['memory_used'] = mem.used / (1024 * 1024 * 1024)  # GB
    stats['memory_available'] = mem.available / (1024 * 1024 * 1024)  # GB

    # CPU信息
    stats['cpu_percent'] = psutil.cpu_percent(interval=1)
    stats['cpu_count'] = psutil.cpu_count()
    stats['cpu_freq'] = psutil.cpu_freq().current if psutil.cpu_freq() else 0  # MHz

    # 磁盘信息
    disk = psutil.disk_usage('/')
    stats['disk_percent'] = disk.percent
    stats['disk_total'] = disk.total / (1024 * 1024 * 1024)  # GB
    stats['disk_used'] = disk.used / (1024 * 1024 * 1024)  # GB
    stats['disk_free'] = disk.free / (1024 * 1024 * 1024)  # GB

    # 系统启动时间
    boot_time = psutil.boot_time()
    stats['boot_time'] = boot_time
    stats['system_uptime_seconds'] = time.time() - boot_time

    # 网络信息
    net_io = psutil.net_io_counters()
    stats['network_sent'] = net_io.bytes_sent / (1024 * 1024)  # MB
    stats['network_recv'] = net_io.bytes_recv / (1024 * 1024)  # MB

    # 系统负载（仅Unix系统）
    try:
        stats['load_avg'] = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
    except:
        stats['load_avg'] = None

    # 进程信息
    stats['process_count'] = len(psutil.pids())
    current_process = psutil.Process()
    stats['current_process_memory'] = current_process.memory_info().rss / (1024 * 1024)  # MB

    # bot服务运行时间
    try:
        output = subprocess.check_output(
            ['systemctl', 'show', 'bot.service', '--property=ActiveEnterTimestamp'],
            stderr=subprocess.DEVNULL,
            text=True
        )

        if 'ActiveEnterTimestamp=' in output:
            time_str = output.split('=')[1].strip()
            if time_str:
                start_time = datetime.strptime(time_str, '%a %Y-%m-%d %H:%M:%S %Z')
                uptime = datetime.now() - start_time
                stats['bot_service_uptime_seconds'] = uptime.total_seconds()
            else:
                stats['bot_service_uptime_seconds'] = None
        else:
            stats['bot_service_uptime_seconds'] = None

    except (subprocess.CalledProcessError, FileNotFoundError):
        stats['bot_service_uptime_seconds'] = None

    return stats


def deepseek_balance():
    payload = {}
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {API_KEY}'
    }

    response = requests.request("GET", url, headers=headers, data=payload)

    response_data = json.loads(response.text)

    if response_data.get("balance_infos"):
        for balance_info in response_data["balance_infos"]:
            if balance_info.get("currency") == "CNY":
                total_balance = balance_info.get("total_balance")
                return total_balance

    return None


@channel.use(ListenerSchema(listening_events=[GroupMessage]))
async def setu(app: Ariadne, group: Group, message: MessageChain, member: Member):
    if message.display == "yb查询状态":
        total_balance = deepseek_balance()
        stats = get_system_stats()

        # 计算运行时间
        bot_uptime = timedelta(seconds=int(stats['bot_service_uptime_seconds'])) if stats[
            'bot_service_uptime_seconds'] else "未知"
        system_uptime = timedelta(seconds=int(stats['system_uptime_seconds']))

        # 创建合并消息节点
        fwd_nodeList = []

        # 标题节点
        fwd_nodeList.append(
            ForwardNode(
                target=member,
                time=datetime.now(),
                message=MessageChain("📊 系统状态 📊"),
            )
        )

        # 内存信息节点
        memory_info = f"💾 内存信息:\n"
        memory_info += f"  总内存: {stats['memory_total']:.1f} GB\n"
        memory_info += f"  已使用: {stats['memory_used']:.1f} GB\n"
        memory_info += f"  可用: {stats['memory_available']:.1f} GB\n"
        memory_info += f"  使用率: {stats['memory_percent']:.1f}%"
        fwd_nodeList.append(
            ForwardNode(
                target=member,
                time=datetime.now(),
                message=MessageChain(memory_info),
            )
        )

        # CPU信息节点
        cpu_info = f"⚡ CPU信息:\n"
        cpu_info += f"  使用率: {stats['cpu_percent']:.1f}%\n"
        cpu_info += f"  核心数: {stats['cpu_count']}\n"
        cpu_info += f"  频率: {stats['cpu_freq']:.1f} MHz"
        fwd_nodeList.append(
            ForwardNode(
                target=member,
                time=datetime.now(),
                message=MessageChain(cpu_info),
            )
        )

        # 磁盘信息节点
        disk_info = f"💿 磁盘信息:\n"
        disk_info += f"  总空间: {stats['disk_total']:.1f} GB\n"
        disk_info += f"  已使用: {stats['disk_used']:.1f} GB\n"
        disk_info += f"  可用: {stats['disk_free']:.1f} GB\n"
        disk_info += f"  使用率: {stats['disk_percent']:.1f}%"
        fwd_nodeList.append(
            ForwardNode(
                target=member,
                time=datetime.now(),
                message=MessageChain(disk_info),
            )
        )

        # 运行时间节点
        uptime_info = f"⏰ 运行时间:\n"
        uptime_info += f"  系统启动: {datetime.fromtimestamp(stats['boot_time']).strftime('%Y-%m-%d %H:%M:%S')}\n"
        uptime_info += f"  系统运行: {system_uptime}\n"
        uptime_info += f"  Bot运行: {bot_uptime}"
        fwd_nodeList.append(
            ForwardNode(
                target=member,
                time=datetime.now(),
                message=MessageChain(uptime_info),
            )
        )

        # 网络信息节点
        network_info = f"🌐 网络信息:\n"
        network_info += f"  发送: {stats['network_sent']:.1f} MB\n"
        network_info += f"  接收: {stats['network_recv']:.1f} MB"
        fwd_nodeList.append(
            ForwardNode(
                target=member,
                time=datetime.now(),
                message=MessageChain(network_info),
            )
        )

        # 系统负载节点
        if stats['load_avg']:
            load_info = f"📈 系统负载:\n"
            load_info += f"  1分钟: {stats['load_avg'][0]:.2f}\n"
            load_info += f"  5分钟: {stats['load_avg'][1]:.2f}\n"
            load_info += f"  15分钟: {stats['load_avg'][2]:.2f}"
            fwd_nodeList.append(
                ForwardNode(
                    target=member,
                    time=datetime.now(),
                    message=MessageChain(load_info),
                )
            )

        # 进程信息节点
        process_info = f"🔄 进程信息:\n"
        process_info += f"  总进程数: {stats['process_count']}\n"
        process_info += f"  当前进程内存: {stats['current_process_memory']:.1f} MB"
        fwd_nodeList.append(
            ForwardNode(
                target=member,
                time=datetime.now(),
                message=MessageChain(process_info),
            )
        )

        # 账户余额节点
        balance_info = f"💰 叶布小荷包: {total_balance}"
        fwd_nodeList.append(
            ForwardNode(
                target=member,
                time=datetime.now(),
                message=MessageChain(balance_info),
            )
        )

        # 创建并发送合并消息
        forward_message = MessageChain(Forward(nodeList=fwd_nodeList))
        await app.send_message(group, forward_message)
