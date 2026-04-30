# -*- coding: utf-8 -*-
"""
用最新凭证测试企业微信 API 全流程
1. 获取 access_token
2. 拉取员工客户列表
3. 修改客户备注
4. 发送应用消息
"""

import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

# ===== 最新凭证 =====
WECOM_CORP_ID = "ww5bb595253ba23914"
WECOM_SECRET = "AX9OtwSzDLelqtNqAzK_xq0brvye5EeVMtrjkkzZOiE"
WECOM_AGENT_ID = 1000002
TEST_USERID = "17851205786"

def test():
    # ===== Step 1: 获取 access_token =====
    print("=" * 60)
    print("[Step 1] 获取 access_token")
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={WECOM_CORP_ID}&corpsecret={WECOM_SECRET}"
    resp = requests.get(url).json()
    print(f"Response: {json.dumps(resp, indent=2, ensure_ascii=False)}")

    if resp.get("errcode", 0) != 0:
        print("[FAIL] 无法获取 token，请检查 CorpID 和 Secret")
        return

    token = resp["access_token"]
    print(f"[OK] Token 获取成功，长度: {len(token)}")

    # ===== Step 2: 拉取员工客户列表 =====
    print("\n" + "=" * 60)
    print(f"[Step 2] 拉取员工 [{TEST_USERID}] 的客户列表")
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/batch/get_by_user?access_token={token}"
    all_customers = []
    cursor = ""

    while True:
        payload = {"userid_list": [TEST_USERID], "limit": 100}
        if cursor:
            payload["cursor"] = cursor
        resp = requests.post(url, json=payload).json()
        print(f"Response: {json.dumps(resp, indent=2, ensure_ascii=False)[:800]}")

        if resp.get("errcode", 0) != 0:
            print(f"[FAIL] 拉取客户列表失败: {resp.get('errmsg')} (errcode: {resp.get('errcode')})")
            break

        contacts = resp.get("external_contact_list", [])
        all_customers.extend(contacts)
        cursor = resp.get("next_cursor")
        if not cursor:
            break

    print(f"\n[OK] 共找到 {len(all_customers)} 个客户")
    for i, item in enumerate(all_customers[:10]):
        c = item.get("external_contact", {})
        print(f"  {i+1}. {c.get('name')}  external_userid={c.get('external_userid')}")

    if not all_customers:
        print("[WARN] 无客户，跳过后续步骤")
        # 即使没有客户，也测试发消息
    else:
        # ===== Step 3: 修改第一个客户的备注 =====
        print("\n" + "=" * 60)
        first = all_customers[0].get("external_contact", {})
        ext_uid = first.get("external_userid")
        cname = first.get("name")
        print(f"[Step 3] 修改客户备注: {cname} ({ext_uid})")

        url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/remark?access_token={token}"
        resp = requests.post(url, json={
            "userid": TEST_USERID,
            "external_userid": ext_uid,
            "remark": "API测试备注-可删除"
        }).json()
        print(f"Response: {json.dumps(resp, indent=2, ensure_ascii=False)}")

        if resp.get("errcode") == 0:
            print("[OK] 备注修改成功！请在企微客户端确认")
        else:
            print(f"[FAIL] 备注修改失败: {resp.get('errmsg')}")

    # ===== Step 4: 发送应用消息给测试员工 =====
    print("\n" + "=" * 60)
    print(f"[Step 4] 发送应用消息给员工 [{TEST_USERID}]")
    url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
    resp = requests.post(url, json={
        "touser": TEST_USERID,
        "msgtype": "text",
        "agentid": WECOM_AGENT_ID,
        "text": {"content": "🔧 API连通性测试 - 如果你看到这条消息，说明应用消息推送正常！"}
    }).json()
    print(f"Response: {json.dumps(resp, indent=2, ensure_ascii=False)}")

    if resp.get("errcode") == 0:
        print("[OK] 消息发送成功！请检查企微是否收到")
    else:
        print(f"[FAIL] 消息发送失败: {resp.get('errmsg')}")

    # ===== Step 5: 测试 remark API 权限（用假ID） =====
    print("\n" + "=" * 60)
    print("[Step 5] 测试 remark API 权限（用假 external_userid）")
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/remark?access_token={token}"
    resp = requests.post(url, json={
        "userid": TEST_USERID,
        "external_userid": "wmFAKE_TEST_ID_123",
        "remark": "权限测试"
    }).json()
    print(f"Response: {json.dumps(resp, indent=2, ensure_ascii=False)}")

    errcode = resp.get("errcode", -1)
    if errcode == 60011:
        print("[FAIL] 当前应用无客户联系权限，需要使用「客户联系」系统应用的 Secret")
    elif errcode in (60012, 40022, 81061):
        print("[OK] API 权限正常（ID 不存在是预期的）")
    elif errcode == 0:
        print("[OK] 居然成功了（假ID不应该成功，但权限没问题）")
    else:
        print(f"[INFO] 其他错误: {resp.get('errmsg')} (errcode: {errcode})")

    print("\n" + "=" * 60)
    print("测试完成！")

if __name__ == "__main__":
    test()
