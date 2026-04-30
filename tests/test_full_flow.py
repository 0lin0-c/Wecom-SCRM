# -*- coding: utf-8 -*-
"""
用真实员工ID测试完整流程
"""

import requests
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

WECOM_CORP_ID = "ww893ef078a0935650"
WECOM_SECRET = "NwTTbs4A7iaFa36SuyznKvDPNdsUb1jQsII-DUn_HX0"

def test_full_flow():
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
    
    # 2. 用员工ID拉取客户列表
    print("\n" + "=" * 50)
    print("[Step 2] Get customer list for employee: CaoHuiLin")
    
    employee_userid = "CaoHuiLin"
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/batch/get_by_user?access_token={token}"
    
    all_customers = []
    cursor = ""
    
    while True:
        payload = {"userid_list": [employee_userid], "limit": 100}
        if cursor:
            payload["cursor"] = cursor
        
        resp = requests.post(url, json=payload).json()
        print(f"Response: {json.dumps(resp, indent=2, ensure_ascii=False)[:600]}")
        
        if resp.get("errcode", 0) != 0:
            print(f"[FAIL] Error: {resp.get('errmsg')} (errcode: {resp.get('errcode')})")
            return
        
        contacts = resp.get("external_contact_list", [])
        all_customers.extend(contacts)
        
        cursor = resp.get("next_cursor")
        if not cursor:
            break
    
    print(f"\n[OK] Found {len(all_customers)} customers")
    
    if not all_customers:
        print("[WARN] No customers found for this employee")
        return
    
    # 显示前5个客户
    print("\nCustomer list:")
    for i, item in enumerate(all_customers[:5]):
        contact = item.get("external_contact", {})
        print(f"  {i+1}. name: {contact.get('name')}, external_userid: {contact.get('external_userid')}")
    
    # 3. 用第一个客户测试修改备注
    print("\n" + "=" * 50)
    print("[Step 3] Test modify remark")
    
    first_customer = all_customers[0].get("external_contact", {})
    external_userid = first_customer.get("external_userid")
    customer_name = first_customer.get("name")
    
    print(f"Target customer: {customer_name} ({external_userid})")
    print(f"New remark: TEST_REMARK_BY_API")
    
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/remark?access_token={token}"
    resp = requests.post(url, json={
        "userid": employee_userid,
        "external_userid": external_userid,
        "remark": "TEST_REMARK_BY_API"
    }).json()
    
    print(f"\nResponse: {json.dumps(resp, indent=2, ensure_ascii=False)}")
    
    if resp.get("errcode") == 0:
        print("\n[SUCCESS] Remark modified!")
        print("Please check in WeChat Work app if the remark changed.")
    else:
        print(f"\n[FAIL] Error: {resp.get('errmsg')}")

if __name__ == "__main__":
    test_full_flow()
