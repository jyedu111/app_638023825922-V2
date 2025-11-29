# student_agent.py —— Windows 专用增强版（v2.1）
import time
import json
import requests
import os
import sys
import base64
import re
from io import BytesIO

# ====== 配置 ======
SERVER_URL = "http://10.1.82.202:3000/api/report"
ENABLE_SCREENSHOT = False  # 👈 设为 True 开启截屏（建议抽查开启）
REPORT_INTERVAL = 180      # 每 3 分钟上报一次（秒）

# 获取学生ID：优先用主机名，兼容机房命名如 "PC-01", "Student205"
try:
    import socket
    STUDENT_ID = socket.gethostname().lower()
    if not STUDENT_ID or STUDENT_ID == 'localhost':
        STUDENT_ID = f"win_{int(time.time()) % 1000}"
except:
    STUDENT_ID = "unknown_windows"

# ====== Windows 专用：获取当前活跃窗口（Chrome/Edge）======
try:
    import win32gui
    import win32process
    import psutil

    def get_active_browser_info():
        """返回 (url, title)，若非浏览器或无法获取则返回 (None, None)"""
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None, None

        # 获取窗口标题 & 进程名
        title = win32gui.GetWindowText(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            proc = psutil.Process(pid)
            exe_name = os.path.basename(proc.exe()).lower()
        except:
            return None, None

        # 仅监控 Chromium 浏览器（Chrome / Edge）
        if 'chrome' not in exe_name and 'msedge' not in exe_name:
            return None, None

        # 从标题提取 URL（Chromium 格式：标题 - 网址）
        # 示例：'百度一下，你就知道 - https://www.baidu.com/'
        match = re.search(r' - (https?://[^\s]+)$', title)
        if match:
            url = match.group(1)
            page_title = title[:match.start()].strip()
            return url, page_title or "无标题"
        
        # 备用：仅返回标题（如本地文件、about:blank）
        return "about:blank", title[:50]

except ImportError as e:
    print("⚠️ 未安装 pywin32/psutil，将使用模拟数据（请运行 install.bat）")
    def get_active_browser_info():
        import random
        sites = [
            "https://www.baidu.com/s?wd=初中数学",
            "https://www.zxxk.com/",
            "https://www.jyeoo.com/",
            "https://v.qq.com/",
            "about:blank"
        ]
        return random.choice(sites), "学习页面"


# ====== Windows 专用：区域截图（仅浏览器窗口）======
def take_browser_screenshot():
    if not ENABLE_SCREENSHOT:
        return None
    try:
        from PIL import ImageGrab, Image
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        rect = win32gui.GetWindowRect(hwnd)
        left, top, right, bottom = rect
        width, height = right - left, bottom - top

        # 过滤无效窗口（最小化/太小）
        if width < 200 or height < 100:
            return None

        # 截图（+偏移避免标题栏干扰）
        bbox = (left + 8, top + 30, right - 8, bottom - 8)
        img = ImageGrab.grab(bbox=bbox)
        if img.width < 100 or img.height < 50:
            return None

        # 缩放 + 压缩
        img.thumbnail((320, 180))
        buffered = BytesIO()
        img = img.convert("RGB")  # 避免 RGBA 问题
        img.save(buffered, format="JPEG", quality=50, optimize=True)
        b64 = base64.b64encode(buffered.getvalue()).decode()
        return f"image/jpeg;base64,{b64}"
    except Exception as e:
        print(f"📸 截图失败: {e}")
        return None


# ====== 主循环 ======
def report_once():
    url, title = get_active_browser_info()
    if not url:
        return  # 非浏览器窗口，跳过

    screenshot = take_browser_screenshot()

    payload = {
        "student_id": STUDENT_ID,
        "url": url[:512],      # 防超长
        "title": (title or "")[:256],
        "screenshot": screenshot
    }

    try:
        resp = requests.post(SERVER_URL, json=payload, timeout=10)
        data = resp.json()
        status = "🔴黑名单" if data.get('blacklisted') else "🟢正常"
        print(f"[{time.strftime('%H:%M:%S')}] {STUDENT_ID} | {status} | {url}")
    except Exception as e:
        print(f"❌ 上报失败: {e}")


# ====== 后台静默运行支持 ======
def run_as_background():
    """用 .vbs 启动自己实现无黑窗"""
    vbs_path = os.path.join(os.path.dirname(__file__), "agent.vbs")
    script = f'''
Set ws = CreateObject("WScript.Shell")
ws.Run "python.exe ""{os.path.abspath(__file__)}""", 0, False
'''
    with open(vbs_path, 'w', encoding='utf-8') as f:
        f.write(script)
    print(f"✅ 已生成静默启动脚本: {vbs_path}")
    print("👉 双击此 .vbs 文件即可后台运行（无黑窗）")
    os.system(f'cscript "{vbs_path}" //nologo')
    sys.exit()


if __name__ == '__main__':
    print(f"🧑 Windows 学生端 v2.1 启动")
    print(f"  ID: {STUDENT_ID} | 截屏: {'✅' if ENABLE_SCREENSHOT else '❌'}")
    print(f"  上报地址: {SERVER_URL} | 间隔: {REPORT_INTERVAL}秒")
    
    # 检测是否从 .vbs 启动（隐藏窗口）
    if 'vbs' not in sys.argv and os.path.basename(sys.executable) != 'pythonw.exe':
        if input("\n是否生成静默启动脚本？(y/n): ").strip().lower() == 'y':
            run_as_background()

    # 主循环
    while True:
        report_once()
        time.sleep(REPORT_INTERVAL)