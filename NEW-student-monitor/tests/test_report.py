"""可配置的上报演示脚本

用法示例:
  python tests/test_report.py --server http://localhost:3003 --student-id demo_pc --count 2 --interval 1 --timestamp

支持参数:
  --server       后端地址（包含路径），默认为 http://localhost:3003
  --student-id   学生ID，默认为 test_pc
  --count        上报次数，默认为 1
  --interval     上报间隔（秒），默认为 1
  --timestamp    如果指定，则在上报中带上 timestamp 字段（毫秒）
"""

import argparse
import json
import time
import requests
from datetime import datetime


def make_payload(student_id, student_ip, url, title, add_timestamp=False):
    payload = {
        "student_id": student_id,
        "student_ip": student_ip,
        "url": url,
        "original_url": url,
        "title": title
    }
    if add_timestamp:
        # 使用毫秒时间戳以兼容多种客户端
        payload["timestamp"] = int(time.time() * 1000)
    return payload


def post_once(server, payload, timeout=5):
    try:
        resp = requests.post(f"{server.rstrip('/')}/api/report", json=payload, timeout=timeout)
        return resp.status_code, resp.text
    except Exception as e:
        return None, str(e)


def main():
    p = argparse.ArgumentParser(description="演示向学生监控后端上报数据")
    p.add_argument('--server', default='http://localhost:3003', help='后端地址，默认为 http://localhost:3003')
    p.add_argument('--student-id', default='test_pc', help='学生ID')
    p.add_argument('--student-ip', default='192.168.1.100', help='学生IP')
    p.add_argument('--url', default='https://www.example.com/test', help='原始URL')
    p.add_argument('--title', default='测试页面', help='页面标题')
    p.add_argument('--count', type=int, default=1, help='上报次数')
    p.add_argument('--interval', type=float, default=1.0, help='上报间隔（秒）')
    p.add_argument('--timestamp', action='store_true', help='在上报中附带 timestamp 字段（毫秒）')
    args = p.parse_args()

    print(f"将向 {args.server} 发送 {args.count} 条上报, student_id={args.student_id}")

    for i in range(args.count):
        payload = make_payload(args.student_id, args.student_ip, args.url, args.title, add_timestamp=args.timestamp)
        status, body = post_once(args.server, payload)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if status is None:
            print(f"[{now}] 第 {i+1} 次上报失败: {body}")
        else:
            print(f"[{now}] 第 {i+1} 次上报: status={status}, body={body}")
        if i < args.count - 1:
            time.sleep(args.interval)


if __name__ == '__main__':
    main()
