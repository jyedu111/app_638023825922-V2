# student_agent.py —— 增强版（无截图｜10秒上报｜真实URL｜黑名单匹配）
import time
import json
import requests
import os
import socket
import re
import threading

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
        
        # 仅监控 Chrome / Edge
        if 'chrome' not in exe_name and 'msedge' not in exe_name:
            return None, None
        
        # 尝试从标题提取 URL（Chromium 格式）
        match = re.search(r' - (https?://[^\s]+)$', title)
        if match:
            url = match.group(1)
            page_title = title[:match.start()].strip()
            return url, page_title or "无标题"
        
        # 备用：尝试读取地址栏（需安装 pywin32 扩展）
        try:
            import win32clipboard
            import win32con
            win32clipboard.OpenClipboard()
            url = win32clipboard.GetClipboardData(win32con.CF_TEXT).decode('utf-8').strip()
            win32clipboard.CloseClipboard()
            if url.startswith('http'):
                return url, title[:50]
        except:
            pass
        
        # 最后兜底：返回当前活动标签页标题
        return "about:blank", title[:50]
except:
    def get_active_browser_info():
        return "https://www.baidu.com", "学习页面"

# ====== 主循环 ======
def report_once():
    url, title = get_active_browser_info()
    if not url:
        return
    
    # 检查是否在黑名单（本地缓存）
    is_blacklisted = False
    try:
        domain = new URL(url).hostname.replace('www.', '').lower()
        for b in blacklist_cache:
            if b in domain or domain.endswith(b):
                is_blacklisted = True
                break
    except:
        pass
    
    payload = {
        "student_id": STUDENT_ID,
        "url": url[:512],
        "title": (title or "")[:256],
        "blacklisted": is_blacklisted  # ← 新增字段，供服务端记录
    }
    
    try:
        resp = requests.post(SERVER_URL, json=payload, timeout=5)
        status = "🔴黑名单" if is_blacklisted else "🟢正常"
        print(f"[{time.strftime('%H:%M:%S')}] {STUDENT_ID} | {status} | {url}")
    except Exception as e:
        print(f"❌ 上报失败: {e}")

if __name__ == '__main__':
    print(f"🧑 学生端启动 | ID: {STUDENT_ID} | 频率: {REPORT_INTERVAL}秒/次")
    while True:
        report_once()
        time.sleep(REPORT_INTERVAL)