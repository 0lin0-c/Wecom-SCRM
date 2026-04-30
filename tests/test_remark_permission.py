# -*- coding: utf-8 -*-
"""
直接测试 remark 接口权限（不需要访问通讯录）
"""

import requests
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

WECOM_CORP_ID = "ww893ef078a0935650"
WECOM_SECRET = "NwTTbs4A7iaFa36SuyznKvDPNdsUb1jQsII-DUn_HX0"

def test_remark_permission():
    # 1. 获取 access_token
    print("=" * 50)
    print("[Step 1] Get access_token")
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={WECOM_CORP_ID}&corpsecret={WECOM_SECRET}"
    resp = requests.get(url).json()
    
    if resp.get("errcode", 0) != 0:
        print(f"[FAIL] Cannot get token: {resp}")
        return
    
    token = resp.get("access_token")
    print(f"[OK] Token obtained")
    
    # 2. 直接测试 remark 接口
    print("\n" + "=" * 50)
    print("[Step 2] Test remark API permission")
    print("(Using fake IDs to test if API is accessible)")
    
    # 使用假数据测试权限
    # errcode 60011 = 无权限
    # errcode 60012 = external_userid 无效（说明有权限，只是 ID 不对）
    # errcode 40003 = userid 无效（说明有权限，只是 ID 不对）
    
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/remark?access_token={token}"
    
    test_cases = [
        {"userid": "test_user", "external_userid": "wmTEST123", "remark": "test"},
        {"userid": "ZhangSan", "external_userid": "wmABC123456", "remark": "test"},
    ]
    
    for i, payload in enumerate(test_cases):
        print(f"\nTest case {i+1}: {payload}")
        resp = requests.post(url, json=payload).json()
        print(f"Response: {json.dumps(resp, indent=2, ensure_ascii=False)}")
        
        errcode = resp.get("errcode", 0)
        if errcode == 60011:
            print(">>> [60011] PERMISSION DENIED - No Customer Contact permission!")
        elif errcode == 60012:
            print(">>> [60012] Invalid external_userid - Permission OK!")
        elif errcode == 40003:
            print(">>> [40003] Invalid userid - Permission OK!")
        elif errcode == 0:
            print(">>> [0] Success!")
        else:
            print(f">>> [{errcode}] Other error: {resp.get('errmsg')}")
    
    # 3. 总结
    print("\n" + "=" * 50)
    print("SUMMARY:")
    print("If all tests return 60011, your app lacks 'Customer Contact' permission.")
    print("\nSolution:")
    print("1. Login to https://work.weixin.qq.com/")
    print("2. App Management -> Customer Contact (system app)")
    print("3. Get the Secret of 'Customer Contact' app")
    print("4. Replace WECOM_SECRET with Customer Contact app's Secret")

if __name__ == "__main__":
    test_remark_permission()
