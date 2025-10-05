# name: SystemInfo
# version: 1.0.0
# developer: @gemeguardian (ported for Maxli)
# dependencies: psutil
# min-maxli: 26

import os
import platform
import subprocess
import sys
import time
from datetime import timedelta

import psutil

strings = {
    "ru": {
        "loading": "🕒 Собираю данные о сервере...",
        "info": (
            "🏠 Информация о сервере\n\n"
            "⚙️ CPU и RAM\n"
            "• CPU: {cpu_count} ядер @ {cpu_usage}%\n"
            "• RAM: {ram_used} / {ram_total} ({ram_percent}%)\n\n"
            "📂 Хранилище\n"
            "• Диск: {disk_used} / {disk_total} ({disk_percent}%)\n"
            "• Swap: {swap_used} / {swap_total} ({swap_percent}%)\n\n"
            "ℹ️ Система\n"
            "• OS: {os_name}\n"
            "• Arch: {arch_emoji} {arch}\n"
            "• Kernel: {kernel}\n"
            "• Uptime: {uptime}\n"
            "• Load Avg: {load_avg}\n\n"
            "🤖 Процесс\n"
            "• Активных сервисов: {running_services}\n"
            "• Всего процессов (PID): {proc_total}\n"
            "• RAM бота: {proc_ram}\n"
            "• CPU бота: {proc_cpu}%\n\n"
            "📊 Python: {python_version}"
        ),
    }
}

def format_bytes(size):
    if not size:
        return "0.0 B"
    power = 1024
    n = 0
    power_labels = {0: "B", 1: "KB", 2: "MB", 3: "GB", 4: "TB"}
    while size > power and n < len(power_labels) - 1:
        size /= power
        n += 1
    return f"{size:.1f} {power_labels[n]}"

def format_uptime(seconds):
    delta = timedelta(seconds=seconds)
    d = delta.days
    h, rem = divmod(delta.seconds, 3600)
    m, _ = divmod(rem, 60)
    return f"{d}d {h}h {m}m"

def get_os_name():
    if sys.platform == "linux":
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=")[1].strip().strip('"')
        except FileNotFoundError:
            pass
    return f"{platform.system()} {platform.release()}"

def get_running_services():
    if sys.platform != "linux":
        return "N/A"
    try:
        command = "systemctl list-units --state=running --type=service --no-legend --no-pager | wc -l"
        result = subprocess.check_output(
            command, shell=True, text=True, stderr=subprocess.DEVNULL
        )
        return result.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "N/A"

async def sysinfo_command(api, message, args):
    """Показать информацию о системе/сервере (CPU, RAM, диск, аптайм и др.)"""
    lang = "ru" if hasattr(api, "lang") and api.lang == "ru" else "en"
    await api.edit(message, strings[lang]["loading"])
    try:
        current_process = psutil.Process(os.getpid())
        cpu_count = psutil.cpu_count(logical=True)
        cpu_usage = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        ram_total = format_bytes(ram.total)
        ram_used = format_bytes(ram.used)
        ram_percent = ram.percent
        disk = psutil.disk_usage("/")
        disk_total = format_bytes(disk.total)
        disk_used = format_bytes(disk.used)
        disk_percent = disk.percent
        swap = psutil.swap_memory()
        swap_total = format_bytes(swap.total)
        swap_used = format_bytes(swap.used)
        swap_percent = swap.percent
        arch = platform.machine()
        arch_emoji = "🔫" if "64" in platform.architecture()[0] else ""
        kernel = platform.release()
        uptime = format_uptime(time.time() - psutil.boot_time())
        try:
            load_avg_tuple = psutil.getloadavg()
            load_avg = ", ".join([f"{avg:.2f}" for avg in load_avg_tuple])
        except (AttributeError, OSError):
            load_avg = "N/A"
        proc_total = len(psutil.pids())
        proc_ram = format_bytes(current_process.memory_info().rss)
        proc_cpu = current_process.cpu_percent()
        running_services = get_running_services()
        python_version = platform.python_version()
        os_name = get_os_name()
        info = {
            "cpu_count": cpu_count,
            "cpu_usage": cpu_usage,
            "ram_total": ram_total,
            "ram_used": ram_used,
            "ram_percent": ram_percent,
            "disk_total": disk_total,
            "disk_used": disk_used,
            "disk_percent": disk_percent,
            "swap_total": swap_total,
            "swap_used": swap_used,
            "swap_percent": swap_percent,
            "os_name": os_name,
            "arch": arch,
            "arch_emoji": arch_emoji,
            "kernel": kernel,
            "uptime": uptime,
            "load_avg": load_avg,
            "running_services": running_services,
            "proc_total": proc_total,
            "proc_ram": proc_ram,
            "proc_cpu": proc_cpu,
            "python_version": python_version,
        }
        await api.edit(message, strings[lang]["info"].format(**info))
    except Exception as e:
        await api.edit(message, f"❌ Ошибка получения системной информации: {str(e)}")

async def register(api):
    api.register_command("sysinfo", sysinfo_command)
