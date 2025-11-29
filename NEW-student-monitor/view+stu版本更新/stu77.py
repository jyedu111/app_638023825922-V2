# student_agent.py —— 微调升级版（+IP｜+Firefox｜仅报有效URL｜10秒上报）
import time
import json
import requests
import os
import socket
import re
import threading
from urllib.parse import urlparse  # ← 新增导入

# ====== 配置 ======
SERVER_URL = "http://10.1.82.202:3000/api/report"
REPORT_INTERVAL = 10
STUDENT_ID = socket.gethostname().lower() or f"pc_{int(time.time()) % 1000}"

# ====== 新增：获取本机 IP ======
STUDENT_IP = socket.gethostbyname(socket.gethostname())  # ← 关键：获取IP

# ====== 黑名单本地缓存 ======
blacklist_cache = set()
last_blacklist_update = 0

def update_blacklist():
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
        time.sleep(60)
threading.Thread(target=update_blacklist, daemon=True).start()

# ====== 获取当前浏览器活动（Chrome/Edge/Firefox）======
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
        # 支持 Firefox！
        if not any(b in exe_name for b in ['chrome', 'msedge', 'firefox']):
            return None, None
        match = re.search(r' - (https?://[^\s]+)$', title)
        if match:
            url = match.group(1)
            page_title = title[:match.start()].strip()
            return url, page_title or "无标题"
        return "about:blank", title[:50]
except:
    def get_active_browser_info():
        return "https://www.baidu.com", "学习页面"

# ====== 主循环 ======
def report_once():
    url, title = get_active_browser_info()
    if not url:
        return

    # ✅ 新增：仅报送可查验的 HTTP/HTTPS 页面
    if not url.startswith(('http://', 'https://')) or '://localhost' in url or '://127.0.0.1' in url:
        return  # ← 直接跳过无效页

    # ✅ 修复：Python 中没有 new URL，改用 urlparse
    is_blacklisted = False
    try:
        parsed = urlparse(url)
        domain = parsed.hostname.lower().replace('www.', '') if parsed.hostname else ''
        for b in blacklist_cache:
            b = b.strip().lower()
            if b and (domain == b or domain.endswith('.' + b)):
                is_blacklisted = True
                break
    except:
        pass

    # ✅ 新增：上报 student_ip
    payload = {
        "student_id": STUDENT_ID,
        "student_ip": STUDENT_IP,  # ← 关键新增
        "url": url[:512],
        "title": (title or "")[:256],
        "blacklisted": is_blacklisted
    }

    try:
        resp = requests.post(SERVER_URL, json=payload, timeout=5)
        status = "🔴黑名单" if is_blacklisted else "🟢正常"
        print(f"[{time.strftime('%H:%M:%S')}] {STUDENT_ID}({STUDENT_IP}) | {status} | {url}")
    except Exception as e:
        print(f"❌ 上报失败: {e}")

if __name__ == '__main__':
    print(f"🧑 学生端启动 | ID: {STUDENT_ID} | IP: {STUDENT_IP} | 10秒/次")
    while True:
        report_once()
        time.sleep(REPORT_INTERVAL)