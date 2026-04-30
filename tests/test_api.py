# -*- coding: utf-8 -*-
"""
测试企业微信 API 连通性和权限
"""

import requests
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

WECOM_CORP_ID = "ww893ef078a0935650"
WECOM_SECRET = "NwTTbs4A7iaFa36SuyznKvDPNdsUb1jQsII-DUn_HX0"

def test_api():
    # 1. 获取 access_token
    print("=" * 50)
    print("[Step 1] Get access_token")
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={WECOM_CORP_ID}&corpsecret={WECOM_SECRET}"
    resp = requests.get(url).json()
    print(f"Response: {json.dumps(resp, indent=2)}")
    
    if resp.get("errcode", 0) != 0:
        print("[FAIL] Cannot get token")
        return None
    
    token = resp.get("access_token")
    print(f"[OK] Token obtained (length: {len(token)})")
    
    # 2. 获取部门列表
    print("\n" + "=" * 50)
    print("[Step 2] Get department list")
    url = f"https://qyapi.weixin.qq.com/cgi-bin/department/list?access_token={token}"
    resp = requests.get(url).json()
    print(f"Response: {json.dumps(resp, indent=2, ensure_ascii=False)[:600]}")
    
    departments = resp.get("department", [])
    if departments:
        print(f"[OK] Found {len(departments)} departments")
        for d in departments[:5]:
            print(f"   - id: {d.get('id')}, name: {d.get('name')}")
        dept_id = departments[0].get("id")
    else:
        print("[WARN] No departments found, trying root dept (id=1)")
        dept_id = 1
    
    # 3. 获取部门成员
    print("\n" + "=" * 50)
    print(f"[Step 3] Get members in department {dept_id}")
    url = f"https://qyapi.weixin.qq.com/cgi-bin/user/simplelist?access_token={token}&department_id={dept_id}"
    resp = requests.get(url).json()
    print(f"Response: {json.dumps(resp, indent=2, ensure_ascii=False)[:600]}")
    
    users = resp.get("userlist", [])
    if users:
        print(f"[OK] Found {len(users)} members")
        for u in users[:5]:
            print(f"   - userid: {u.get('userid')}, name: {u.get('name')}")
    else:
        print("[FAIL] No members found, cannot continue test")
        return token
    
    # 4. 尝试获取该员工的客户列表
    print("\n" + "=" * 50)
    print("[Step 4] Get external contacts (customers)")
    
    test_userid = users[0].get("userid")
    print(f"Trying to get customers for user [{test_userid}]...")
    
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/batch/get_by_user?access_token={token}"
    resp = requests.post(url, json={"userid_list": [test_userid], "limit": 100}).json()
    print(f"Response: {json.dumps(resp, indent=2, ensure_ascii=False)[:800]}")
    
    errcode = resp.get("errcode", 0)
    if errcode != 0:
        print(f"[FAIL] Error: {resp.get('errmsg')} (errcode: {errcode})")
        if errcode == 60011:
            print("\n>>> PERMISSION DENIED: This app lacks 'Customer Contact' permission!")
            print(">>> Solution: Use the 'Customer Contact' app's Secret instead of self-built app's Secret")
    else:
        contacts = resp.get("external_contact_list", [])
        print(f"[OK] Found {len(contacts)} customers")
        if contacts:
            first_contact = contacts[0].get("external_contact", {})
            print(f"   First customer: name={first_contact.get('name')}, external_userid={first_contact.get('external_userid')}")
    
    # 5. 测试 remark 接口权限
    print("\n" + "=" * 50)
    print("[Step 5] Test remark API permission")
    
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/remark?access_token={token}"
    resp = requests.post(url, json={
        "userid": test_userid,
        "external_userid": "wmTEST123456",  # fake ID to test permission
        "remark": "test remark"
    }).json()
    print(f"Response: {json.dumps(resp, indent=2, ensure_ascii=False)}")
    
    errcode = resp.get("errcode", 0)
    if errcode == 60011:
        print("\n[CONCLUSION] This app does NOT have 'Customer Contact' permission!")
        print("Cannot modify customer remarks with current app!")
        print("\nSolution:")
        print("1. Login to https://work.weixin.qq.com/")
        print("2. Go to: App Management -> Customer Contact (System App)")
        print("3. Get the Secret of Customer Contact app")
        print("4. Update WECOM_SECRET in your code")
    elif errcode == 60012:
        print("[INFO] Invalid external_userid (expected, we used fake ID)")
        print("But this means the API permission is OK!")
    elif errcode == 0:
        print("[OK] Remark API works! (unexpected success with fake ID)")
    else:
        print(f"[INFO] Other error: {resp.get('errmsg')}")
    
    return token

if __name__ == "__main__":
    test_api()
