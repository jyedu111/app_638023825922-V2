# student_agent.py —— 最终版（IP｜Firefox｜仅报有效URL｜10秒上报）
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
REPORT_INTERVAL = 10

# 获取学生机局域网IP
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

STUDENT_ID = socket.gethostname().lower()
STUDENT_IP = get_local_ip()

# ====== 黑名单缓存 ======
blacklist_cache = set()
def update_blacklist():
    global blacklist_cache
    while True:
        try:
            resp = requests.get(SERVER_URL.replace('/api/report', '/api/blacklist'), timeout=5)
            if resp.status_code == 200:
                blacklist_cache = set(resp.json())
                print(f"✅ 黑名单更新: {len(blacklist_cache)} 条")
        except Exception as e:
            print(f"⚠️ 黑名单更新失败: {e}")
        time.sleep(60)
threading.Thread(target=update_blacklist, daemon=True).start()

# ====== 仅允许可查验的公开网页 ======
def is_valid_public_url(url):
    if not url: return False
    u = url.strip().lower()
    invalid_prefixes = (
        'about:', 'chrome:', 'edge:', 'file:', 'moz-extension:',
        'javascript:', '', 'ftp:', 'mailto:', 'blob:'
    )
    if any(u.startswith(p) for p in invalid_prefixes):
        return False
    if 'localhost' in u or '127.0.0.1' in u:
        return False
    return u.startswith(('http://', 'https://'))

# ====== 获取浏览器活动（Chrome / Edge / Firefox）======
try:
    import win32gui, win32process, psutil
    def get_active_browser_info():
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd: return None, None
        title = win32gui.GetWindowText(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            proc = psutil.Process(pid)
            exe_name = os.path.basename(proc.exe()).lower()
        except: return None, None
        
        # 支持三大浏览器
        if not any(b in exe_name for b in ['chrome', 'msedge', 'firefox']):
            return None, None

        # 方法1：从标题提取 URL（Chromium/Firefox通用）
        match = re.search(r' - (https?://[^\s]+)$', title)
        if match:
            url = match.group(1).strip()
            if is_valid_public_url(url):
                title_part = title[:match.start()].strip()
                return url, title_part or "无标题"
        
        # 方法2：兜底返回 None（不报无效页）
        return None, None

except ImportError as e:
    print(f"⚠️ 缺少依赖: {e}. 使用模拟数据")
    def get_active_browser_info():
        return "https://www.zxxk.com", "学科网 - 初中数学"

# ====== 上报 ======
def report_once():
    url, title = get_active_browser_info()
    if not url or not is_valid_public_url(url):
        return  # 跳过无效页面

    # 黑名单匹配
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
        "student_ip": STUDENT_IP,  # ← 新增
        "url": url,
        "title": title,
        "blacklisted": is_blacklisted
    }

    try:
        resp = requests.post(SERVER_URL, json=payload, timeout=5)
        status = "🔴黑名单" if is_blacklisted else "🟢正常"
        print(f"[{time.strftime('%H:%M:%S')}] {STUDENT_ID}({STUDENT_IP}) | {status} | {url} | {title}")
    except Exception as e:
        print(f"❌ 上报失败: {e}")

if __name__ == '__main__':
    print(f"🧑 学生端启动 | ID: {STUDENT_ID} | IP: {STUDENT_IP} | 10秒/次")
    print("🔍 仅报送可查验的 http/https 页面")
    while True:
        report_once()
        time.sleep(REPORT_INTERVAL)