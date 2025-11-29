# student_agent.py —— 纯净版（无截图｜10秒上报）
import time
import json
import requests
import os
import socket
import re

# ====== 配置 ======
SERVER_URL = "http://10.1.82.202:3000/api/report"
REPORT_INTERVAL = 10  # ← 10秒上报一次
STUDENT_ID = socket.gethostname().lower() or f"pc_{int(time.time()) % 1000}"

# ====== 获取当前浏览器活动（Chrome/Edge）======
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
        if 'chrome' not in exe_name and 'msedge' not in exe_name:
            return None, None
        match = re.search(r' - (https?://[^\s]+)$', title)
        if match:
            return match.group(1), title[:match.start()].strip()
        return "about:blank", title[:50]
except:
    def get_active_browser_info():
        return "https://www.baidu.com", "学习页面"

# ====== 主循环 ======
def report_once():
    url, title = get_active_browser_info()
    if not url:
        return
    payload = {
        "student_id": STUDENT_ID,
        "url": url[:512],
        "title": (title or "")[:256]
    }
    try:
        resp = requests.post(SERVER_URL, json=payload, timeout=5)
        status = "🔴黑名单" if resp.json().get('blacklisted') else "🟢正常"
        print(f"[{time.strftime('%H:%M:%S')}] {STUDENT_ID} | {status} | {url}")
    except Exception as e:
        print(f"❌ 上报失败: {e}")

if __name__ == '__main__':
    print(f"🧑 学生端启动 | ID: {STUDENT_ID} | 频率: {REPORT_INTERVAL}秒/次")
    while True:
        report_once()
        time.sleep(REPORT_INTERVAL)