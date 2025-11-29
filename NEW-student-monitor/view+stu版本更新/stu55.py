# student_agent.py —— 最终版（仅报可查验域名｜支持 Chrome/Edge/Firefox｜10秒上报）
import time
import json
import requests
import os
import socket
import re
import threading
from urllib.parse import urlparse

# ====== 配置 ======
SERVER_URL = "http://10.1.82.202:3000/api/report"
REPORT_INTERVAL = 10  # ← 10秒上报一次
STUDENT_ID = socket.gethostname().lower() or f"pc_{int(time.time()) % 1000}"

# ====== 黑名单本地缓存 ======
blacklist_cache = set()
last_blacklist_update = 0

def update_blacklist():
    """定时从服务端拉取最新黑名单"""
    global blacklist_cache, last_blacklist_update
    while True:
        try:
            resp = requests.get(f"{SERVER_URL.replace('/api/report', '/api/blacklist')}", timeout=5)
            if resp.status_code == 200:
                blacklist_cache = set(resp.json())
                last_blacklist_update = time.time()
                print(f"✅ 黑名单已更新（{len(blacklist_cache)} 条）")
        except Exception as e:
            print(f"⚠️ 黑名单更新失败: {e}")
        time.sleep(60)  # 每分钟更新一次

# 启动黑名单更新线程
threading.Thread(target=update_blacklist, daemon=True).start()

# ====== 判断是否为可查验的公开网页 URL ======
def is_valid_public_url(url):
    if not url:
        return False
    url = url.strip().lower()
    # 排除内部协议、扩展页、本地文件等
    invalid_prefixes = (
        'about:', 'chrome:', 'edge:', 'file:', 'moz-extension:',
        'javascript:', 'data:', 'ftp:', 'mailto:', 'blob:'
    )
    if any(url.startswith(p) for p in invalid_prefixes):
        return False
    # 仅允许 http/https
    return url.startswith(('http://', 'https://'))

# ====== 获取当前浏览器活动（Chrome / Edge / Firefox）======
try:
    import win32gui
    import win32process
    import psutil

    def get_active_browser_info():
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None, None

        title = win32gui.GetWindowText(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)

        try:
            proc = psutil.Process(pid)
            exe_name = os.path.basename(proc.exe()).lower()
        except:
            return None, None

        # 支持三大浏览器
        if not any(browser in exe_name for browser in ['chrome', 'msedge', 'firefox']):
            return None, None

        # 方法1：从标题提取 URL（Chromium/Firefox）
        # 示例：'百度一下，你就知道 - https://www.baidu.com/'
        match = re.search(r' - (https?://[^\s]+)$', title)
        if match:
            url = match.group(1).strip()
            if is_valid_public_url(url):
                title_part = title[:match.start()].strip()
                return url, title_part or "无标题"

        # 方法2：尝试从剪贴板获取（模拟 Ctrl+L + Ctrl+C）
        try:
            import win32clipboard
            import win32con
            win32clipboard.OpenClipboard()
            clip_data = win32clipboard.GetClipboardData(win32con.CF_TEXT).decode('utf-8', errors='ignore').strip()
            win32clipboard.CloseClipboard()
            if is_valid_public_url(clip_data):
                return clip_data, title[:60]
        except:
            pass

        # 方法3：兜底返回标题（不报无效URL）
        return None, None

except ImportError as e:
    print(f"⚠️ 缺少依赖: {e}. 使用模拟数据")
    def get_active_browser_info():
        return "https://www.zxxk.com", "学科网 - 初中数学"

# ====== 主循环 ======
def report_once():
    url, title = get_active_browser_info()
    
    # ✅ 关键：仅当是可查验的 public URL 时才上报
    if not url or not is_valid_public_url(url):
        print(f"🚫 跳过无效/内部页面: {url or 'None'}")
        return

    # 检查黑名单（本地缓存匹配）
    is_blacklisted = False
    try:
        parsed = urlparse(url)
        domain = parsed.hostname.lower() if parsed.hostname else ''
        domain = domain.replace('www.', '')
        for b in blacklist_cache:
            b = b.strip().lower()
            if b and (domain == b or domain.endswith('.' + b)):
                is_blacklisted = True
                break
    except Exception as e:
        print(f"⚠️ 黑名单匹配异常: {e}")

    payload = {
        "student_id": STUDENT_ID,
        "url": url[:512],
        "title": (title or "")[:256],
        "blacklisted": is_blacklisted
    }

    try:
        resp = requests.post(SERVER_URL, json=payload, timeout=5)
        status = "🔴黑名单" if is_blacklisted else "🟢正常"
        print(f"[{time.strftime('%H:%M:%S')}] {STUDENT_ID} | {status} | {url}")
    except Exception as e:
        print(f"❌ 上报失败: {e}")

if __name__ == '__main__':
    print(f"🧑 学生端启动 | ID: {STUDENT_ID} | 频率: {REPORT_INTERVAL}秒/次")
    print("🔍 仅报送可查验的 HTTP/HTTPS 网址｜支持 Chrome/Edge/Firefox")
    while True:
        report_once()
        time.sleep(REPORT_INTERVAL)