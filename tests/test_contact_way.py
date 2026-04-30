# -*- coding: utf-8 -*-
"""
测试企业微信"联系我"功能和事件回调
"""

import requests
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

WECOM_CORP_ID = "ww893ef078a0935650"
WECOM_SECRET = "NwTTbs4A7iaFa36SuyznKvDPNdsUb1jQsII-DUn_HX0"

def get_token():
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={WECOM_CORP_ID}&corpsecret={WECOM_SECRET}"
    resp = requests.get(url).json()
    return resp.get("access_token")

def test_contact_way(token):
    """测试"联系我"功能 - 查看已有的联系方式配置"""
    print("=" * 50)
    print("[Step 1] List existing contact ways")
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/list_contact_way?access_token={token}"
    resp = requests.post(url, json={
        "offset": 0,
        "limit": 100
    }).json()
    print(f"Response: {json.dumps(resp, indent=2, ensure_ascii=False)[:800]}")
    return resp

def create_contact_way(token):
    """为员工创建"联系我"二维码，这样添加好友时会有 welcome_code"""
    print("\n" + "=" * 50)
    print("[Step 2] Create contact way for employee CaoHuiLin")
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/add_contact_way?access_token={token}"
    resp = requests.post(url, json={
        "type": 2,           # 2=单人
        "scene": 2,          # 2=添加外部联系人
        "skip_verify": True, # 自动通过
        "user": ["CaoHuiLin"],
        "state": "reception_flow"
    }).json()
    print(f"Response: {json.dumps(resp, indent=2, ensure_ascii=False)[:800]}")
    return resp

def test_send_welcome_msg(token):
    """测试发送欢迎语（需要真实的 welcome_code）"""
    print("\n" + "=" * 50)
    print("[Step 3] Test send_welcome_msg API (will fail without real welcome_code)")
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/send_welcome_msg?access_token={token}"
    resp = requests.post(url, json={
        "welcome_code": "TEST_CODE",  # 假的，测试接口是否可调用
        "text": {
            "content": "您好！我是您的专属营养顾问助手。\n请问您的手机尾号后4位是多少？\n我将为您匹配营养方案。"
        }
    }).json()
    print(f"Response: {json.dumps(resp, indent=2, ensure_ascii=False)}")
    return resp

def check_external_contact_callback(token):
    """检查客户联系事件的回调配置"""
    print("\n" + "=" * 50)
    print("[Step 4] Check if we can get contact event callback info")
    # 企微没有直接查询回调配置的API，但可以测试添加外部联系人的事件
    # 这个需要在企微后台配置
    print("Note: External contact event callback needs to be configured in WeChat Work admin console.")
    print("Path: Customer Contact -> API -> Callback URL")
    print("You need to configure:")
    print("  - URL: http://YOUR_SERVER:8500/wechat/external_callback")
    print("  - Token: (set your own)")
    print("  - AES Key: (set your own)")

if __name__ == "__main__":
    token = get_token()
    if not token:
        print("[FAIL] Cannot get token")
        exit()
    print(f"[OK] Token obtained")
    
    # Step 1: 查看已有配置
    contact_ways = test_contact_way(token)
    
    # Step 2: 创建联系方式
    create_contact_way(token)
    
    # Step 3: 测试欢迎语接口
    test_send_welcome_msg(token)
    
    # Step 4: 回调说明
    check_external_contact_callback(token)
