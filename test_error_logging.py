#!/usr/bin/env python3
"""测试错误日志记录功能"""

import http.client
import json
import time

def send_error_requests():
    """发送多个错误请求"""
    conn = http.client.HTTPConnection("localhost", 25566)
    
    # 测试用例 1: 无效的 JSON
    print("发送无效 JSON 请求...")
    headers = {"Content-Type": "application/json"}
    conn.request("POST", "/v1/messages", "invalid json", headers)
    response = conn.getresponse()
    print(f"响应状态: {response.status}")
    response.read()
    time.sleep(1)
    
    # 测试用例 2: 有效的请求但目标服务器可能返回错误
    print("发送有效请求...")
    valid_request = {
        "model": "test-model",
        "messages": [
            {"role": "user", "content": "Hello"}
        ]
    }
    conn.request("POST", "/v1/messages", json.dumps(valid_request), headers)
    response = conn.getresponse()
    print(f"响应状态: {response.status}")
    response.read()
    time.sleep(1)
    
    # 测试用例 3: 另一个无效的 JSON
    print("发送另一个无效 JSON 请求...")
    conn.request("POST", "/v1/chat/completions", "{invalid json}", headers)
    response = conn.getresponse()
    print(f"响应状态: {response.status}")
    response.read()
    time.sleep(1)
    
    conn.close()
    print("测试完成！请查看 logs/router_error.log 文件。")

if __name__ == "__main__":
    send_error_requests()
