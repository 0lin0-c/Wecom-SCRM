# -*- coding: utf-8 -*-
"""
测试新企业 API 连通性
"""

import requests
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

# 新企业配置
WECOM_CORP_ID = "ww5bb595253ba23914"
WECOM_SECRET = "AX9OtwSzDLelqtNqAzK_xq0brvye5EeVMtrjkkzZOiE"
WECOM_AGENT_ID = 1000002
EMPLOYEE_USERID = "CaoHuiLin"

def test_api():
    # 1. 获取 access_token
    print("=" * 50)
    print("[Step 1] Get access_token")
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={WECOM_CORP_ID}&corpsecret={WECOM_SECRET}"
    resp = requests.get(url).json()
    print(f"Response: {json.dumps(resp, indent=2)}")
    
    if resp.get("errcode", 0) != 0:
        print("[FAIL] Cannot get token")
        return
    
    token = resp.get("access_token")
    print(f"[OK] Token: {token[:20]}...")
    
    # 2. 测试发送消息给员工
    print("\n" + "=" * 50)
    print("[Step 2] Send test message to employee")
    url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
    resp = requests.post(url, json={
        "touser": EMPLOYEE_USERID,
        "msgtype": "text",
        "agentid": WECOM_AGENT_ID,
        "text": {"content": "Hello! This is a test message from API."}
    }).json()
    print(f"Response: {json.dumps(resp, indent=2)}")
    
    if resp.get("errcode") == 0:
        print("[OK] Message sent successfully!")
    else:
        print(f"[FAIL] {resp.get('errmsg')}")
    
    # 3. 测试客户联系权限
    print("\n" + "=" * 50)
    print("[Step 3] Test customer contact permission")
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/batch/get_by_user?access_token={token}"
    resp = requests.post(url, json={"userid_list": [EMPLOYEE_USERID], "limit": 100}).json()
    print(f"Response: {json.dumps(resp, indent=2)[:500]}")
    
    if resp.get("errcode") == 0:
        print("[OK] Customer contact API works!")
    elif resp.get("errcode") == 48002:
        print("[FAIL] No customer contact permission!")
    else:
        print(f"[INFO] {resp.get('errmsg')}")

if __name__ == "__main__":
    test_api()
