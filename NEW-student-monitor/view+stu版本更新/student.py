import os
import json
import time
import socket
import platform
import shutil
import sqlite3
import schedule
import pygetwindow as gw
import requests
import webbrowser
import socketio
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin
from threading import Thread
import uiautomation as auto

# -------------------------- 配置项 --------------------------
CONFIG = {
    "SERVER": {
        "api_url": "http://10.1.82.202:3000", # 替换为你的服务端IP
        "socketio_url": "http://10.1.82.202:3000"
    },
    "COLLECT": {
        "interval": 3,
        "browser_history_limit": 50
    },
    "URL_BLOCK": {
        "block_page_path": os.path.join(os.getcwd(), "block_page.html"),
        "check_window_interval": 2,
        "blacklist_pull_interval": 60
    }
}

# 全局变量
student_id = None
url_blacklist = []
blocked_url_cache = set()
sio = socketio.Client()
is_connected = False

# -------------------------- 初始化 --------------------------
def init():
    global student_id
    init_block_page()
    
    # 尝试从本地文件加载 student_id
    if os.path.exists('student_id.txt'):
        with open('student_id.txt', 'r') as f:
            student_id = f.read().strip()
            print(f"ℹ️ 从本地加载学生机ID: {student_id}")

    # 启动 Socket.io 和 API 拉取黑名单
    Thread(target=start_communication, daemon=True).start()

    # 等待黑名单初始化
    time.sleep(2) 

    Thread(target=start_check_browser_window, daemon=True).start()
    schedule.every(CONFIG["COLLECT"]["interval"]).minutes.do(collect_and_upload_data)
    schedule.every(CONFIG["URL_BLOCK"]["blacklist_pull_interval"]).seconds.do(pull_blacklist_from_server)
    
    collect_and_upload_data() # 立即执行一次
    
    print(f"✅ 学生机客户端初始化完成（采集间隔：{CONFIG['COLLECT']['interval']}分钟）")
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 客户端已退出")

def start_communication():
    """启动 Socket.io 客户端并处理重连"""
    global is_connected
    while True:
        if not is_connected:
            try:
                sio.connect(CONFIG["SERVER"]["socketio_url"],transports=["websocket"])
                is_connected = True
            except Exception as e:
                print(f"❌ Socket.io 连接失败, 5秒后重试...: {e}")
                time.sleep(5)
        else:
            time.sleep(1) # 保持线程 alive

# -------------------------- 数据采集 --------------------------
def get_system_info():
    hostname = socket.gethostname()
    ip = socket.gethostbyname(hostname)
    os_info = f"{platform.system()} {platform.release()}"
    
    active_window = "未知窗口"
    try:
        active_win = gw.getActiveWindow()
        if active_win:
            active_window = active_win.title
    except Exception as e:
        active_window = f"获取失败: {str(e)[:20]}"
    
    return {
        "hostname": hostname,
        "ip": ip,
        "os": os_info,
        "active_window": active_window,
        "collect_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def get_browser_history():
    history = []  # 用于存储所有浏览器历史
    user_home = str(Path.home())
    system = platform.system()
    browser_paths = {  # 浏览器历史文件路径（不变）
        "Chrome": {"Windows": f"{user_home}\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\History"},
        "Edge": {"Windows": f"{user_home}\\AppData\\Local\\Microsoft\\Edge\\User Data\\Default\\History"},
        "Firefox": {"Windows": f"{user_home}\\AppData\\Roaming\\Mozilla\\Firefox\\Profiles"}
    }

    # 步骤2：完善 Chrome/Edge 历史读取逻辑（补充实际采集代码）
    def read_chrome_edge_history(path, browser):
        nonlocal history  # 允许函数修改外部的 history 列表
        if not os.path.exists(path):
            return
        temp_path = f"{path}.temp"  # 临时文件（避免原文件被浏览器锁定）
        max_retries = 3  # 重试次数（解决文件占用问题）
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                shutil.copy2(path, temp_path)  # 复制原文件到临时路径
                conn = sqlite3.connect(temp_path)
                cursor = conn.cursor()
                # 读取Chrome/Edge历史（SQLite数据库）
                cursor.execute("""
                    SELECT url, title, last_visit_time 
                    FROM urls 
                    ORDER BY last_visit_time DESC 
                    LIMIT ?
                """, (CONFIG["COLLECT"]["browser_history_limit"],))
                # 解析历史数据并添加到 history 列表
                for row in cursor.fetchall():
                    url, title, visit_time = row
                    if visit_time != 0:
                        # Chrome时间戳转换（1601-01-01起的微秒）
                        visit_dt = datetime(1601, 1, 1) + datetime.timedelta(microseconds=visit_time)
                        history.append({
                            "browser": browser, "url": url, "title": title or "无标题",
                            "visit_time": visit_dt.strftime("%Y-%m-%d %H:%M:%S")
                        })
                conn.close()
                os.remove(temp_path)  # 删除临时文件
                break
            except PermissionError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    print(f"❌ 读取{browser}历史失败：文件被占用（已重试{max_retries}次）")
            except Exception as e:
                print(f"❌ 读取{browser}历史失败：{str(e)[:50]}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                break

    # 步骤3：定义 Firefox 历史读取函数
    def read_firefox_history(profile_dir):
        nonlocal history
        if not os.path.exists(profile_dir):
            return
        # 遍历Firefox配置文件夹，找到 places.sqlite（历史数据库）
        for root, _, files in os.walk(profile_dir):
            if "places.sqlite" in files:
                db_path = os.path.join(root, "places.sqlite")
                temp_path = f"{db_path}.temp"
                try:
                    shutil.copy2(db_path, temp_path)
                    conn = sqlite3.connect(temp_path)
                    cursor = conn.cursor()
                    # 读取Firefox历史
                    cursor.execute("""
                        SELECT p.url, p.title, v.visit_date 
                        FROM moz_places p 
                        JOIN moz_historyvisits v ON p.id = v.place_id 
                        ORDER BY v.visit_date DESC 
                        LIMIT ?
                    """, (CONFIG["COLLECT"]["browser_history_limit"],))
                    for row in cursor.fetchall():
                        url, title, visit_date = row
                        if visit_date != 0:
                            # Firefox时间戳转换（1970-01-01起的微秒）
                            visit_dt = datetime.fromtimestamp(visit_date / 1000000)
                            history.append({
                                "browser": "Firefox", "url": url, "title": title or "无标题",
                                "visit_time": visit_dt.strftime("%Y-%m-%d %H:%M:%S")
                            })
                    conn.close()
                    os.remove(temp_path)
                except Exception as e:
                    print(f"❌ 读取Firefox历史失败：{str(e)[:30]}")
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                break

    # 步骤4：调用采集函数（按系统区分）
    if system == "Windows":
        read_chrome_edge_history(browser_paths["Chrome"]["Windows"], "Chrome")
        read_chrome_edge_history(browser_paths["Edge"]["Windows"], "Edge")
        read_firefox_history(browser_paths["Firefox"]["Windows"])

    # 关键：返回采集到的历史列表
    return history
    

def collect_and_upload_data():
    print(f"\n📅 开始采集（{datetime.now().strftime('%H:%M:%S')}）")
    try:
        system_info = get_system_info()
        browser_history = get_browser_history()
        data = {"system_info": system_info, "browser_history": browser_history}
        
        response = requests.post(
            f"{CONFIG['SERVER']['api_url']}/api/student/upload",
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                global student_id
                if student_id != result.get("student_id"):
                    student_id = result.get("student_id")
                    with open('student_id.txt', 'w') as f:
                        f.write(str(student_id))
                    print(f"✅ 注册/更新成功，学生机ID: {student_id}")
                else:
                    print(f"✅ 数据上传成功")
            else:
                print(f"❌ 数据上传失败: {result.get('error', '未知错误')}")
        else:
            print(f"❌ 数据上传失败，状态码: {response.status_code}, 响应: {response.text[:50]}")

    except Exception as e:
        print(f"❌ 采集或上传任务异常: {e}")

# -------------------------- URL 拦截 --------------------------
def init_block_page():
    block_page_content = """
    <!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>访问被拦截</title><style>body { margin: 0; padding: 0; height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; background: #f8f9fa; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; } .block-box { text-align: center; padding: 50px; background: white; border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,0.15); } .icon { font-size: 70px; color: #dc3545; margin-bottom: 20px; } .title { font-size: 28px; color: #333; margin-bottom: 15px; } .desc { font-size: 16px; color: #666; margin: 10px 0; max-width: 500px; word-break: break-all; } .time { font-size: 14px; color: #999; margin-top: 20px; }</style></head><body><div class="block-box"><div class="icon">🚫</div><h1 class="title">访问被管理员限制</h1><p class="desc">您尝试访问的网站因违反网络使用规范而被拦截。</p><p class="desc" id="url"></p><p class="time" id="time"></p></div><script>const params = new URLSearchParams(window.location.search); document.getElementById('url').textContent = '被拦截URL: ' + (params.get('url') || '未知'); document.getElementById('time').textContent = '拦截时间: ' + new Date().toLocaleString(); </script></body></html>
    """
    with open(CONFIG["URL_BLOCK"]["block_page_path"], "w", encoding="utf-8") as f:
        f.write(block_page_content)

def is_url_blocked(url):
    if not url or not url_blacklist: return False
    parsed = urlparse(url)
    domain = parsed.netloc.split(':')[0]

    for pattern in url_blacklist:
        pattern = pattern.strip()
        if not pattern: continue
        if pattern == url: return True
        if pattern.startswith('*.') and domain.endswith(pattern[2:]): return True
        if pattern.endswith('/') and url.startswith(pattern): return True
    return False

def report_blocked_url(url):
    global student_id, blocked_url_cache
    if not student_id or not url: return
    cache_key = f"{url}_{int(time.time() / 60)}"
    if cache_key in blocked_url_cache: return
    blocked_url_cache.add(cache_key)

    try:
        response = requests.post(
            f"{CONFIG['SERVER']['api_url']}/api/student/block-log",
            json={"student_id": student_id, "url": url},
            timeout=5
        )
        if response.status_code == 200 and response.json().get("success"):
            print(f"ℹ️ 上报拦截记录: {url}")
    except Exception as e:
        print(f"❌ 上报拦截记录失败: {e}")

def open_block_page(url):
    encoded_url = requests.utils.quote(url)
    block_page_url = urljoin(f"file://{CONFIG['URL_BLOCK']['block_page_path']}", f"?url={encoded_url}")
    webbrowser.open(block_page_url)
    time.sleep(1)
    for win in gw.getWindowsWithTitle("访问被拦截"):
        if win.isMinimized: win.restore()
        win.activate()

def get_browser_url_uia(window_title):
    """使用 UI Automation 尝试获取浏览器地址栏 URL"""
    # 尝试定位 Chrome/Edge 地址栏
    address_bar = auto.WindowControl(searchDepth=10, Name="地址和搜索栏")
    if address_bar.Exists(0, 0):
        try:
            # 获取地址栏的完整文本，这可能包含额外信息
            full_text = address_bar.GetValuePattern().Value
            # 通常 URL 是文本的第一部分，或者可以直接获取
            if full_text.startswith(('http://', 'https://')):
                return full_text.split(' ')[0] # 简单处理，取第一个空格前的部分
            return full_text
        except Exception:
            pass

    # 尝试定位 Firefox 地址栏
    firefox_address_bar = auto.EditControl(searchDepth=10, Name="位置")
    if firefox_address_bar.Exists(0, 0):
        try:
            return firefox_address_bar.GetValuePattern().Value
        except Exception:
            pass
            
    return None

def get_browser_url(window):
    """获取浏览器窗口的当前URL（优先使用UI Automation）"""
    if platform.system() != "Windows": return None
    
    url = get_browser_url_uia(window.title)
    if url:
        return url

    # 如果 UI Automation 失败，可以回退到旧的方法作为备用
    try:
        import win32gui
        import win32process
        from ctypes import windll, create_string_buffer

        hwnd = window._hWnd
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process_handle = windll.kernel32.OpenProcess(0x10 | 0x400, False, pid)
        if not process_handle: return None

        url = None
        browser_title_lower = window.title.lower()
        
        # 这是一个备用方案，可靠性较低
        if "chrome" in browser_title_lower or "edge" in browser_title_lower:
            buffer = create_string_buffer(1024)
            # 地址可能存放在不同的位置，这里只是示例
            windll.kernel32.ReadProcessMemory(process_handle, 0x0000000004000000, buffer, 1024, None)
            url = buffer.value.decode('utf-8', errors='ignore').strip()
        
        windll.kernel32.CloseHandle(process_handle)
        if url and (url.startswith('http://') or url.startswith('https://')):
            return url
    except Exception as e:
        print(f"❌ 备用方法获取URL失败: {e}")
        
    return None

def check_browser_windows():
    if not url_blacklist: return
    browser_keywords = ["chrome", "edge", "firefox", "safari", "浏览器"]
    checked_urls = set()

    try:
        for window in gw.getAllWindows():
            win_title = window.title.strip().lower()
            if not win_title or not any(kw in win_title for kw in browser_keywords): continue
            
            url = get_browser_url(window)
            if not url or url in checked_urls: continue
            
            checked_urls.add(url)
            if is_url_blocked(url):
                print(f"🚫 拦截URL: {url}（窗口：{window.title}）")
                window.close()
                open_block_page(url)
                report_blocked_url(url)
                time.sleep(1) # 避免快速关闭多个窗口导致问题
    except Exception as e:
        print(f"❌ 检查浏览器窗口失败: {e}")

def start_check_browser_window():
    while True:
        check_browser_windows()
        time.sleep(CONFIG["URL_BLOCK"]["check_window_interval"])

# -------------------------- 黑名单同步 --------------------------
@sio.event
def connect():
    global is_connected
    print(f"✅ Socket.io 连接成功")
    is_connected = True
    pull_blacklist_from_server() # 连接成功后立即拉取一次

@sio.event
def connect_error(err):
    global is_connected
    is_connected = False
    print(f"❌ Socket.io 连接失败: {err}")

@sio.event
def disconnect():
    global is_connected
    is_connected = False
    print(f"❌ Socket.io 断开连接")

@sio.on('blacklist-update')
def on_blacklist_update(data):
    global url_blacklist
    print(f"ℹ️ 收到黑名单更新: {data}")
    pull_blacklist_from_server() # 简单处理，直接重新拉取整个列表

def pull_blacklist_from_server():
    try:
        response = requests.get(f"{CONFIG['SERVER']['api_url']}/api/url-blacklist/current", timeout=5)
        if response.status_code == 200:
            new_blacklist = response.json().get("blacklist", [])
            global url_blacklist
            if sorted(url_blacklist) != sorted(new_blacklist):
                url_blacklist = new_blacklist
                print(f"✅ 拉取并更新URL黑名单（共{len(url_blacklist)}条规则）")
    except Exception as e:
        print(f"❌ 拉取黑名单失败: {e}")

# -------------------------- 主函数 --------------------------
if __name__ == "__main__":
    if platform.system() != "Windows":
        print("⚠️ 警告：URL拦截功能在非Windows系统上可能无法正常工作。")
    init()

