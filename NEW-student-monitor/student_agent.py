import os
import time
import json
import socket
import re
import base64
import platform
import requests
import psutil
try:
    import win32gui
    import win32process
except Exception:
    win32gui = None
    win32process = None
import uuid
from datetime import datetime
from io import BytesIO
from PIL import Image
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 用于去重的缓存，存储最近上报的记录
# 格式: {(domain, title): (last_report_time, count)}
recent_reports = {}
# 去重时间窗口(秒)，相同内容在这个时间内不会重复上报
DEDUPLICATION_WINDOW = int(os.environ.get('DEDUPLICATION_WINDOW', '30'))

# 配置（可通过环境变量覆盖）
SERVER_BASE = os.environ.get('MONITOR_SERVER') or os.environ.get('SERVER_URL') or 'http://localhost:3003'
SERVER_URL = SERVER_BASE.rstrip('/') + '/api/report'
SCREENSHOT_ENABLED = os.environ.get('SCREENSHOT_ENABLED', '1') not in ['0', 'false', 'False']
REPORT_INTERVAL = float(os.environ.get('REPORT_INTERVAL', '5'))  # 上报间隔（秒）
# 最大截图大小（字节），超过会进一步压缩或省略
MAX_SCREENSHOT_BYTES = int(os.environ.get('MAX_SCREENSHOT_BYTES', str(200 * 1024)))
# 初始截图最大边长（像素）
INITIAL_MAX_SCREENSHOT = int(os.environ.get('INITIAL_MAX_SCREENSHOT', '1024'))
# JPEG初始质量
INITIAL_JPEG_QUALITY = int(os.environ.get('INITIAL_JPEG_QUALITY', '70'))

# requests session with retry
session = requests.Session()
retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[502, 503, 504], allowed_methods=['POST','GET'])
adapter = HTTPAdapter(max_retries=retries)
session.mount('http://', adapter)
session.mount('https://', adapter)

# 获取本机IP地址
def get_local_ip():
    try:
        # 方法1: 通过UDP连接获取真实IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # 连接到一个公共DNS服务器来获取本地IP
            s.connect(('8.8.8.8', 80))
            local_ip = s.getsockname()[0]
            s.close()
            # 验证是否是有效IP（非回环地址）
            if local_ip and local_ip != '127.0.0.1':
                return local_ip
        except:
            pass
        
        # 方法2: 获取所有网络接口的IP地址
        try:
            # 获取所有网络接口信息
            interfaces = psutil.net_if_addrs()
            # 遍历所有接口
            for interface_name, addresses in interfaces.items():
                for address in addresses:
                    # 只取IPv4地址且非回环地址
                    if address.family == socket.AF_INET and address.address != '127.0.0.1':
                        return address.address
        except:
            pass
        
        # 方法3: 通过hostname解析获取IP
        try:
            hostname = socket.gethostname()
            ip_addresses = socket.gethostbyname_ex(hostname)[2]
            for ip in ip_addresses:
                if ip != '127.0.0.1':
                    return ip
        except:
            pass
        
        # 所有方法都失败时返回回环地址
        return "127.0.0.1"
    except:
        return "127.0.0.1"

# 学生ID获取函数
def get_student_id():
    # 尝试从文件读取学生ID
    id_file = "student_id.txt"
    if os.path.exists(id_file):
        try:
            with open(id_file, 'r', encoding='utf-8') as f:
                student_id = f.read().strip()
                # 检查是否已经是纯计算机名格式
                if student_id and not (student_id.startswith('stu_') and '_' in student_id[4:]):
                    return student_id
        except:
            pass
    
    # 直接使用计算机名作为学生ID，不添加前缀和时间戳
    try:
        # 获取计算机名
        computer_name = platform.node()
        # 清理计算机名，移除可能的特殊字符
        computer_name = re.sub(r'[^a-zA-Z0-9_-]', '_', computer_name)
        # 保存到文件
        with open(id_file, 'w', encoding='utf-8') as f:
            f.write(computer_name)
        return computer_name
    except:
        # 兜底方案：使用简化的计算机名
        try:
            return platform.node().replace(' ', '_')
        except:
            return "unknown_pc"

# 获取活动浏览器信息
def get_active_browser_info():
    """
    获取当前活动的浏览器窗口的URL和标题
    """
    try:
        # 获取活动窗口
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        
        # 检查是否是浏览器窗口
        browser_classes = ['Chrome_WidgetWin_1', 'MozillaWindowClass', 'IEFrame', 'ApplicationFrameWindow']
        window_class = win32gui.GetClassName(hwnd)
        
        # 提取URL的正则表达式模式 - 增强版本
        url_patterns = [
            r'(https?://[^\s]+)',  # 直接匹配URL
            r'地址: (https?://[^\s]+)',  # 地址栏格式
            r'URL: (https?://[^\s]+)',  # URL: 格式
            r'(www\.[^\s]+\.[^\s]+)',  # www.开头的网址
            r'([^\s]+\.(com|cn|net|org|edu|gov|mil|int|info|biz|name|museum|coop|aero|pro|tel|mobi|asia|jobs|travel)[^\s]*)',  # 常见顶级域名
        ]
        
        # 尝试从标题中提取URL
        url = None
        for pattern in url_patterns:
            match = re.search(pattern, title)
            if match:
                url = match.group(1)
                if not url.startswith(('http://', 'https://')):
                    # 如果是域名形式但没有协议，添加https
                    if re.match(r'^www\.', url) or re.search(r'\.[a-zA-Z]{2,}(\.[a-zA-Z]{2,})?', url):
                        url = 'https://' + url
                break
        
        # 如果标题中没有找到URL，但窗口是浏览器，尝试从进程和窗口类名推断
        if url is None and window_class in browser_classes:
            try:
                _, process_id = win32process.GetWindowThreadProcessId(hwnd)
                process = psutil.Process(process_id)
                process_name = process.name().lower()
                
                # 对于浏览器窗口，即使无法获取URL，也尝试从标题中提取域名信息
                # 增强的域名提取模式
                enhanced_domain_patterns = [
                    r'([^\s]+\.(com|cn|net|org|edu|gov|mil|int|info|biz|name|museum|coop|aero|pro|tel|mobi|asia|jobs|travel)(/|$))',
                    r'(www\.[^\s]+\.[^\s]+)',
                    r'(youtube|baidu|google|bing|sohu|sina|qq|taobao|jd|tmall|1688)\.com',
                ]
                
                for pattern in enhanced_domain_patterns:
                    match = re.search(pattern, title.lower())
                    if match:
                        domain = match.group(1)
                        url = 'https://' + domain
                        break
            except:
                pass
        
        # 如果标题不为空但URL还是没有，尝试使用窗口标题作为特殊标识
        if url is None and title.strip():
            # 为有标题但无法提取URL的窗口创建一个基于标题的标识
            # 这样可以避免返回about:blank导致域名显示unknown
            sanitized_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title[:30])
            url = f"app:{sanitized_title}"
        else:
            # 如果还是没有找到URL，返回默认值
            if url is None:
                url = "about:blank"
        
        return url, title[:100]  # 限制标题长度
    except Exception as e:
        print(f"获取浏览器信息失败: {str(e)}")
        return "unknown_app", ""

# 截图功能
def take_screenshot():
    """
    对活动窗口进行截图
    """
    try:
        if not SCREENSHOT_ENABLED:
            return None

        if not win32gui:
            # 平台不支持 win32gui（例如非 Windows 环境）
            return None

        from PIL import ImageGrab

        # 获取活动窗口
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None

        # 获取窗口位置和大小
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width = right - left
        height = bottom - top

        # 如果窗口太小或不可见，返回None
        if width < 10 or height < 10:
            return None

        # 截图
        screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))

        # 初始缩放以控制尺寸
        max_side = INITIAL_MAX_SCREENSHOT
        if max(screenshot.size) > max_side:
            ratio = max_side / max(screenshot.size)
            new_size = (int(screenshot.size[0] * ratio), int(screenshot.size[1] * ratio))
            screenshot = screenshot.resize(new_size, Image.LANCZOS)

        # 逐步压缩直到小于阈值或达到最小质量
        quality = INITIAL_JPEG_QUALITY
        buf = BytesIO()
        screenshot.save(buf, format='JPEG', quality=quality)
        image_data = buf.getvalue()

        while len(image_data) > MAX_SCREENSHOT_BYTES and quality > 30:
            quality = max(30, int(quality * 0.8))
            buf = BytesIO()
            screenshot.save(buf, format='JPEG', quality=quality)
            image_data = buf.getvalue()

        # 如果仍然过大，尝试再缩小分辨率一次
        if len(image_data) > MAX_SCREENSHOT_BYTES:
            ratio = 0.7
            new_size = (max(1, int(screenshot.size[0] * ratio)), max(1, int(screenshot.size[1] * ratio)))
            screenshot = screenshot.resize(new_size, Image.LANCZOS)
            quality = max(30, int(quality * 0.8))
            buf = BytesIO()
            screenshot.save(buf, format='JPEG', quality=quality)
            image_data = buf.getvalue()

        if len(image_data) > MAX_SCREENSHOT_BYTES:
            # 无法压缩到允许范围，跳过截图
            return None

        # 转换为base64
        return base64.b64encode(image_data).decode('utf-8')
    except ImportError:
        print("缺少截图相关库，截图功能已禁用")
        return None
    except Exception as e:
        print(f"截图失败: {str(e)}")
        return None

# 从URL提取域名
def extract_domain(url):
    """
    从URL中提取域名，保留www前缀，避免返回unknown
    """
    try:
        # 处理特殊情况
        if not url or url.strip() == '':
            return "empty_url"
        
        # 处理app:前缀的特殊标识
        if url.startswith('app:'):
            # 保留app:前缀，这样可以区分应用程序和网页
            return url.replace('app:', 'app_').replace('__', '_')
        
        # 处理unknown_app的特殊情况
        if url == 'unknown_app':
            return 'unknown_app'
        
        # 处理about:blank等特殊URL
        if url.startswith('about:'):
            return 'internal_page'
        
        # 移除协议部分
        clean_url = re.sub(r'^https?://', '', url)
        # 移除路径部分
        domain = re.sub(r'/.*$', '', clean_url)
        # 移除端口号
        domain = re.sub(r':\d+$', '', domain)
        
        # 清理后的域名验证
        if not domain or domain.strip() == '' or domain in ['about:blank']:
            # 尝试从原始URL中提取任何可能的域名部分
            fallback_match = re.search(r'([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', url)
            if fallback_match:
                return fallback_match.group(1)
            # 如果真的无法提取有效域名，使用一个有意义的标识而不是unknown
            return "unparsable_url"
        
        return domain
    except Exception as e:
        print(f"域名提取失败: {str(e)}")
        # 即使出错也不返回unknown，返回一个更有用的标识
        return "domain_parse_error"

# 上报函数
def report_once(student_id):
    """
    执行一次数据上报，包含去重逻辑
    """
    try:
        # 步骤1: 获取浏览器信息
        original_url, title = get_active_browser_info()
        
        # 步骤2: 检查是否需要跳过上报
        if original_url == "about:blank" and not title.strip():
            return False
        
        # 步骤3: 提取域名
        domain = extract_domain(original_url)
        
        # 步骤4: 执行去重逻辑
        current_time = time.time()
        report_key = (domain, title)
        
        # 4.1: 清理过期的缓存记录
        expired_keys = [
            k for k, v in recent_reports.items() 
            if current_time - v[0] > DEDUPLICATION_WINDOW
        ]
        for key in expired_keys:
            del recent_reports[key]
        
        # 4.2: 检查是否在去重窗口内已上报
        if report_key in recent_reports:
            last_time, count = recent_reports[report_key]
            recent_reports[report_key] = (current_time, count + 1)
            print(f"[去重] 相同内容在{DEDUPLICATION_WINDOW}秒内已上报过 {count} 次，" 
                  f"跳过本次上报: {domain} - {title[:20]}...")
            return False
        
        # 步骤5: 准备上报数据
        # 5.1: 生成截图
        screenshot = take_screenshot() if SCREENSHOT_ENABLED else None
        
        # 5.2: 获取时间戳和IP
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        student_ip = get_local_ip()
        
        # 5.3: 构造上报数据结构
        report_data = {
            "student_id": student_id,
            "student_ip": student_ip,
            "url": domain,
            "original_url": original_url,
            "domain": domain,
            "title": title,
            "timestamp": timestamp,
            "screenshot": screenshot,
            "system": platform.system(),
            "system_version": platform.version()
        }
        
        # 步骤6: 发送数据到服务器（使用 session，带重试和超时）
        headers = {'Content-Type': 'application/json'}

        # 指数退避重试（在 session 的重试失败时再做一次逐步退避）
        tries = 0
        max_tries = 3
        backoff = 1
        while tries < max_tries:
            try:
                resp = session.post(SERVER_URL, json=report_data, headers=headers, timeout=6)
                if resp.status_code == 200:
                    print(f"[{timestamp}] 上报成功: {domain}")
                    recent_reports[report_key] = (current_time, 1)
                    return True
                else:
                    print(f"上报失败: 状态码 {resp.status_code}, body={resp.text}")
                    return False
            except requests.exceptions.RequestException as e:
                tries += 1
                print(f"网络请求失败 ({tries}/{max_tries}): {str(e)}")
                time.sleep(backoff)
                backoff *= 2
        return False
              
    except requests.exceptions.RequestException as e:
        print(f"网络请求失败: {str(e)}")
        return False
    except Exception as e:
        print(f"上报过程中出错: {str(e)}")
        return False

# 静默运行支持
def run_silently():
    """
    检查是否需要以无窗口模式运行
    """
    import sys
    if sys.stdout is None and sys.stderr is None:
        return True
    return False

# 创建VBS脚本以无黑窗运行
def create_vbs_wrapper():
    """
    创建VBS脚本，用于无黑窗口运行Python脚本
    """
    vbs_content = '''
Set objShell = CreateObject("WScript.Shell")
objShell.Run "cmd /c python student_agent.py", 0, False
'''
    
    with open("agent.vbs", "w") as f:
        f.write(vbs_content)
    
    print("已创建静默运行脚本 agent.vbs，双击即可无黑窗运行")

# 主函数
def main():
    print("学生端监控代理已启动")
    print(f"服务器地址: {SERVER_URL}")
    print(f"上报间隔: {REPORT_INTERVAL}秒")
    
    # 创建静默运行脚本
    create_vbs_wrapper()
    
    # 获取学生ID
    student_id = get_student_id()
    print(f"学生ID: {student_id}")
    
    # 主循环
    try:
        while True:
            report_once(student_id)
            time.sleep(REPORT_INTERVAL)
    except KeyboardInterrupt:
        print("\n代理已停止")
    except Exception as e:
        print(f"运行出错: {str(e)}")

if __name__ == "__main__":
    main()