#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# student_monitor_agent.py - 学生端上网行为监控代理程序
# 功能：收集学生浏览器信息，提取域名，上报至监控服务器

import time
import json
import requests
import os
import socket
import re
import threading
from urllib.parse import urlparse

# ====== 配置项 ======
SERVER_URL = "http://localhost:3000/api/report"  # 后端服务器地址
REPORT_INTERVAL = 10  # 基础上报间隔（秒）
DUPLICATE_INTERVAL = 30  # 同一域名重复上报的间隔（秒）
UPDATE_BLACKLIST_INTERVAL = 300  # 黑名单更新间隔（秒）

# ====== 获取学生信息 ======
def get_student_id():
    """获取学生ID（使用主机名）"""
    try:
        hostname = socket.gethostname().lower()
        return hostname if hostname and hostname != 'localhost' else f"pc_{int(time.time()) % 10000}"
    except:
        return f"unknown_{int(time.time()) % 10000}"

STUDENT_ID = get_student_id()

# ====== 获取学生IP ======
def get_student_ip():
    """获取学生端本地IP地址"""
    try:
        # 获取局域网IP
        for addr_info in socket.getaddrinfo(socket.gethostname(), None):
            ip = addr_info[4][0]
            if ip.startswith(('10.', '192.168.', '172.')) and '.' in ip:
                return ip
        # 回退方案：获取任意有效IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        print(f"获取IP失败: {e}")
        return "未知IP"

# ====== 从URL提取域名 ======
def get_domain_from_url(url):
    """将完整URL转换为域名（如https://www.baidu.com/index → baidu.com）"""
    if url in ["about:blank", "—"]:
        return "空白页"
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            # 尝试直接从URL中提取
            match = re.search(r'https?://([^/]+)', url)
            if match:
                hostname = match.group(1)
            else:
                return url[:100]  # 返回原始URL前100个字符
        
        # 去掉www前缀
        if hostname.startswith('www.'):
            hostname = hostname[4:]
        return hostname.lower()
    except Exception as e:
        print(f"解析域名失败: {e}")
        return url[:100]  # 出错时返回原始URL前100个字符

# ====== 浏览器监控 ======
try:
    import win32gui
    import win32process
    import psutil

    def get_active_browser_info():
        """获取当前活动浏览器窗口信息（URL和标题）"""
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None, "无激活窗口"

        window_title = win32gui.GetWindowText(hwnd)
        if not window_title:
            return None, "无窗口标题"

        try:
            # 获取进程信息
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            exe_path = proc.exe()
            exe_name = os.path.basename(exe_path).lower()

            # 检查是否为浏览器
            browser_patterns = ['chrome.exe', 'msedge.exe', 'firefox.exe', 'iexplore.exe', 'opera.exe']
            is_browser = any(pattern in exe_name for pattern in browser_patterns)
            
            if not is_browser:
                return None, f"非浏览器进程: {exe_name}"

            # 尝试从标题提取URL（Chromium格式）
            match = re.search(r' - (https?://[^\s]+)$', window_title)
            if match:
                url = match.group(1)
                title = window_title[:match.start()].strip()
                return url, title or "无标题"

            # 对于不包含URL的标题，返回标题作为页面标题
            return "about:blank", window_title[:200]  # 限制标题长度

        except Exception as e:
            print(f"获取浏览器信息失败: {e}")
            return None, f"进程错误: {str(e)[:50]}"

except ImportError:
    print("⚠️ 未安装pywin32和psutil模块，使用模拟数据")
    
    def get_active_browser_info():
        """模拟浏览器信息（用于开发测试）"""
        import random
        sites = [
            ("https://www.baidu.com/s?wd=初中数学", "百度搜索 - 初中数学"),
            ("https://www.zxxk.com/", "学科网 - 教学资源下载平台"),
            ("https://www.jyeoo.com/", "菁优网 - 智能题库"),
            ("https://v.qq.com/", "腾讯视频 - 中国领先的在线视频平台"),
            ("https://www.bilibili.com/", "哔哩哔哩 (゜-゜)つロ 干杯~-bilibili")
        ]
        return random.choice(sites)

# ====== 黑名单本地缓存 ======
blacklist_cache = set()
last_blacklist_update = 0

def update_blacklist():
    """定期从服务器获取黑名单并更新本地缓存"""
    global blacklist_cache, last_blacklist_update
    while True:
        try:
            current_time = time.time()
            if current_time - last_blacklist_update > UPDATE_BLACKLIST_INTERVAL:
                response = requests.get(f"{SERVER_URL.replace('/report', '/blacklist/check')}", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    blacklist_cache = set(data.get('domains', []))
                    last_blacklist_update = current_time
                    print(f"✅ 黑名单更新成功，共 {len(blacklist_cache)} 个域名")
        except Exception as e:
            print(f"❌ 更新黑名单失败: {e}")
        time.sleep(min(UPDATE_BLACKLIST_INTERVAL, 60))  # 最多每分钟尝试一次

# ====== 检查是否在黑名单 ======
def is_blacklisted(domain):
    """检查域名是否在黑名单中"""
    if not domain or domain == "空白页":
        return False
    
    for blacklisted_domain in blacklist_cache:
        if blacklisted_domain in domain or domain.endswith(blacklisted_domain):
            return True
    return False

# ====== 主上报函数 ======
def report_once():
    """上报一次浏览记录"""
    # 获取浏览器信息
    raw_url, title = get_active_browser_info()
    
    # 如果不是浏览器或获取失败，跳过
    if not raw_url:
        return
    
    # 提取域名
    domain = get_domain_from_url(raw_url)
    
    # 如果域名过短，可能不是有效网址，跳过
    if len(domain) < 3:
        return
    
    # 获取学生IP
    student_ip = get_student_ip()
    
    # 检查黑名单状态
    blacklisted = is_blacklisted(domain)
    
    # 构造上报数据
    payload = {
        "student_id": STUDENT_ID,
        "student_ip": student_ip,
        "url": domain,  # 存储域名
        "title": title[:256]  # 限制标题长度
    }
    
    # 发送数据到服务器
    try:
        response = requests.post(SERVER_URL, json=payload, timeout=10)
        if response.status_code == 200:
            status = "🔴黑名单" if blacklisted else "🟢正常"
            print(f"[{time.strftime('%H:%M:%S')}] {STUDENT_ID} | {status} | {domain} | {title}")
        else:
            print(f"[{time.strftime('%H:%M:%S')}] ❌ 服务器返回错误: {response.status_code}")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] ❌ 上报失败: {e}")

# ====== 主函数 ======
def main():
    print(f"🚀 学生端监控代理启动")
    print(f"📱 学生ID: {STUDENT_ID}")
    print(f"🌐 上报地址: {SERVER_URL}")
    print(f"⏱️  上报间隔: {REPORT_INTERVAL}秒")
    print(f"🔄 黑名单更新间隔: {UPDATE_BLACKLIST_INTERVAL}秒")
    print("=" * 80)
    
    # 启动黑名单更新线程
    threading.Thread(target=update_blacklist, daemon=True).start()
    
    # 主循环
    while True:
        try:
            report_once()
        except Exception as e:
            print(f"🔴 主循环异常: {e}")
        time.sleep(REPORT_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 程序已退出")
    except Exception as e:
        print(f"💥 程序崩溃: {e}")
        input("按回车键退出...")
