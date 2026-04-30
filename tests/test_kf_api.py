# -*- coding: utf-8 -*-
"""
测试微信客服 API 连通性
运行前需在企微后台开通微信客服并配置API权限
"""

import requests
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

WECOM_CORP_ID = "ww5bb595253ba23914"
# 用自建应用的Secret即可调用微信客服API（需在后台授权绑定）
WECOM_SECRET = "AX9OtwSzDLelqtNqAzK_xq0brvye5EeVMtrjkkzZOiE"

def get_kf_token():
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={WECOM_CORP_ID}&corpsecret={WECOM_SECRET}"
    resp = requests.get(url).json()
    return resp.get("access_token")

def test_kf_api():
    # 1. 获取access_token
    print("=" * 50)
    print("[Step 1] Get KF access_token")
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={WECOM_CORP_ID}&corpsecret={WECOM_SECRET}"
    resp = requests.get(url).json()
    print(f"Response: {json.dumps(resp, indent=2)}")

    if resp.get("errcode", 0) != 0:
        print("[FAIL] Cannot get token")
        return

    token = resp.get("access_token")
    print(f"[OK] Token: {token[:20]}...")

    # 2. 获取客服账号列表
    print("\n" + "=" * 50)
    print("[Step 2] Get KF account list")
    url = f"https://qyapi.weixin.qq.com/cgi-bin/kf/account/list?access_token={token}"
    resp = requests.post(url, json={"offset": 0, "limit": 100}).json()
    print(f"Response: {json.dumps(resp, indent=2, ensure_ascii=False)[:1000]}")

    if resp.get("errcode") == 0:
        accounts = resp.get("account_list", [])
        if accounts:
            print(f"\n[OK] Found {len(accounts)} KF account(s):")
            for acc in accounts:
                print(f"  - open_kfid: {acc.get('open_kfid')}")
                print(f"    name: {acc.get('name')}")
                print(f"    avatar: {acc.get('avatar', '')[:50]}...")
        else:
            print("[INFO] No KF accounts found. Please create one in WeChat Work admin console.")
    else:
        print(f"[FAIL] {resp.get('errmsg')}")
        if resp.get("errcode") == 60011:
            print("[HINT] 没有权限，请确认已在企微后台配置'可调用接口的应用'")

    # 3. 测试sync_msg（如果没有客服账号则跳过）
    if resp.get("errcode") == 0 and accounts:
        open_kfid = accounts[0].get("open_kfid")
        print(f"\n" + "=" * 50)
        print(f"[Step 3] Test sync_msg for {open_kfid}")
        url = f"https://qyapi.weixin.qq.com/cgi-bin/kf/sync_msg?access_token={token}"
        resp = requests.post(url, json={
            "open_kfid": open_kfid,
            "limit": 10
        }).json()
        print(f"Response: {json.dumps(resp, indent=2, ensure_ascii=False)[:800]}")

        if resp.get("errcode") == 0:
            msg_list = resp.get("msg_list", [])
            print(f"\n[OK] sync_msg works! Found {len(msg_list)} messages")
            if msg_list:
                for msg in msg_list[:3]:
                    print(f"  - msgtype={msg.get('msgtype')}, origin={msg.get('origin')}, time={msg.get('send_time')}")
        else:
            print(f"[FAIL] {resp.get('errmsg')}")
    else:
        print("\n[SKIP] Step 3: No KF account available for testing")

    # 4. 获取客服链接
    if resp.get("errcode") == 0 if accounts else False:
        open_kfid = accounts[0].get("open_kfid")
        print(f"\n" + "=" * 50)
        print(f"[Step 4] Get KF account link")
        url = f"https://qyapi.weixin.qq.com/cgi-bin/kf/add_contact_way?access_token={token}"
        resp = requests.post(url, json={"open_kfid": open_kfid, "scene": "test"}).json()
        print(f"Response: {json.dumps(resp, indent=2, ensure_ascii=False)[:500]}")

        if resp.get("errcode") == 0:
            print(f"\n[OK] 客服链接: {resp.get('url', '')}")
        else:
            print(f"[FAIL] {resp.get('errmsg')}")

if __name__ == "__main__":
    test_kf_api()
