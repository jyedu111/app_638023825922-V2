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
SERVER_URL = "http://10.1.82.204:3003/api/report"
ENABLE_SCREENSHOT = False  # 👈 设为 True 开启截屏（建议抽查开启）
REPORT_INTERVAL = 10       # 每10秒上报一次（秒）- 测试用

# 获取学生ID：优先用主机名，兼容机房命名如 "PC-01", "Student205"
try:
    import socket
    import platform
    
    # 尝试从文件读取学生ID
    id_file = "student_id.txt"
    if os.path.exists(id_file):
        try:
            with open(id_file, 'r', encoding='utf-8') as f:
                student_id = f.read().strip()
                # 检查是否已经是纯计算机名格式
                if student_id and not (student_id.startswith('stu_') and '_' in student_id[4:]):
                    STUDENT_ID = student_id
                    raise Exception("使用文件中的学生ID")
        except:
            pass
    
    # 直接使用计算机名作为学生ID
    STUDENT_ID = platform.node().lower()
    # 保存到文件
    with open(id_file, 'w', encoding='utf-8') as f:
        f.write(STUDENT_ID)
        
    if not STUDENT_ID or STUDENT_ID == 'localhost':
        STUDENT_ID = f"win_{int(time.time()) % 1000}"
except:
    try:
        STUDENT_ID = platform.node().replace(' ', '_').lower()
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

        # 尝试多种方式从标题中提取URL
        # 1. 标准格式：标题 - https://www.example.com
        match = re.search(r' - (https?://[^\s]+)$', title)
        if match:
            url = match.group(1)
            page_title = title[:match.start()].strip()
            return url, page_title or "无标题"
        
        # 2. URL可能在任何位置的情况
        url_match = re.search(r'https?://[^\s]+', title)
        if url_match:
            url = url_match.group(0)
            # 移除URL部分，剩余作为标题
            page_title = title.replace(url, '').strip().replace('-', '').strip()
            return url, page_title or "无标题"
        
        # 3. 检查是否包含域名格式（可能是不完整URL）
        domain_match = re.search(r'www\.[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', title)
        if domain_match:
            domain = domain_match.group(0)
            page_title = title.replace(domain, '').strip().replace('-', '').strip()
            return f"https://{domain}", page_title or "无标题"
        
        # 最终备用：尝试解析页面标题
        # 移除常见的浏览器后缀（如 "- Google Chrome"）
        clean_title = title
        browser_suffixes = [' - Google Chrome', ' - Microsoft Edge', ' - 新标签页']
        for suffix in browser_suffixes:
            if clean_title.endswith(suffix):
                clean_title = clean_title[:-len(suffix)].strip()
        
        # 如果是新标签页或空白页
        if clean_title in ['新标签页', 'New Tab', '', 'about:blank']:
            return "about:blank", clean_title or "空白页"
        
        # 其他情况：返回标题作为页面标题，但使用特殊标记表示无法获取URL
        return "about:blank", clean_title[:50]  # 保持返回格式一致

except ImportError as e:
    print("⚠️ 未安装 pywin32/psutil，将使用模拟数据（请运行 install.bat）")
    def get_active_browser_info():
        import random
        # 更真实的模拟数据，包含各种类型的学习和非学习网站
        site_data = [
            ("https://www.baidu.com/s?wd=初中数学公式", "百度搜索 - 初中数学公式"),
            ("https://www.zxxk.com/", "学科网 - 教育资源平台"),
            ("https://www.jyeoo.com/", "菁优网 - 初中题库"),
            ("https://baike.baidu.com/item/Python/407313", "Python - 百度百科"),
            ("https://www.w3school.com.cn/html/index.asp", "HTML 教程 - W3School"),
            ("https://www.101edu.cn/", "101教育PPT - 教师备课平台"),
            ("about:blank", "新标签页"),
            ("https://www.bilibili.com/video/BV12X4y1P754", "【数学】二次函数教学视频"),
            ("https://www.zhihu.com/question/485632187", "初中生如何提高编程能力？"),
            ("https://www.163.com/", "网易 - 有态度的新闻门户")
        ]
        url, title = random.choice(site_data)
        return url, title


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

    # 从完整URL中提取域名用于显示和匹配
    domain = ""
    try:
        if url and "://" in url:
            domain = url.split("://")[1].split("/")[0].replace("www.", "").lower()
        elif url and not url.startswith("about:"):
            domain = url.split("/")[0].replace("www.", "").lower()
    except:
        domain = url or ""
    
    payload = {
        "student_id": STUDENT_ID,
        "url": url[:512],      # 发送完整URL
        "domain": domain[:256],  # 同时发送提取的域名用于显示
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