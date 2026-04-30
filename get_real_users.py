# -*- coding: utf-8 -*-
"""
获取企业内真实的员工列表
"""

import requests
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

WECOM_CORP_ID = "ww5bb595253ba23914"
WECOM_SECRET = "AX9OtwSzDLelqtNqAzK_xq0brvye5EeVMtrjkkzZOiE"
WECOM_AGENT_ID = 1000002

def main():
    # 1. 获取 token
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={WECOM_CORP_ID}&corpsecret={WECOM_SECRET}"
    token = requests.get(url).json().get("access_token")
    print(f"Token: {token[:30]}...")

    # 2. 获取部门列表
    print("\n[部门列表]")
    url = f"https://qyapi.weixin.qq.com/cgi-bin/department/list?access_token={token}"
    resp = requests.get(url).json()
    print(json.dumps(resp, indent=2, ensure_ascii=False))

    if resp.get("errcode", 0) != 0:
        print("获取部门失败")
        return

    depts = resp.get("department", [])
    
    # 3. 遍历部门获取员工
    print("\n[员工列表]")
    all_users = []
    for dept in depts:
        dept_id = dept.get("id")
        dept_name = dept.get("name")
        url = f"https://qyapi.weixin.qq.com/cgi-bin/user/simplelist?access_token={token}&department_id={dept_id}"
        r = requests.get(url).json()
        if r.get("errcode", 0) == 0:
            users = r.get("userlist", [])
            for u in users:
                if u.get("userid") not in [x.get("userid") for x in all_users]:
                    all_users.append(u)
                    print(f"  dept={dept_name}  userid={u.get('userid')}  name={u.get('name')}")

    print(f"\n共 {len(all_users)} 名员工")
    
    # 4. 用第一个员工测试发消息
    if all_users:
        test_user = all_users[0]
        print(f"\n[测试] 给 {test_user.get('name')} ({test_user.get('userid')}) 发送应用消息")
        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
        resp = requests.post(url, json={
            "touser": test_user.get("userid"),
            "msgtype": "text",
            "agentid": WECOM_AGENT_ID,
            "text": {"content": "🔧 测试消息 - 如果你收到这条消息，说明API正常！"}
        }).json()
        print(json.dumps(resp, indent=2, ensure_ascii=False))

        # 5. 获取该员工的客户列表
        print(f"\n[客户列表] 员工 {test_user.get('userid')}")
        url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/batch/get_by_user?access_token={token}"
        resp = requests.post(url, json={"userid_list": [test_user.get("userid")], "limit": 100}).json()
        print(json.dumps(resp, indent=2, ensure_ascii=False)[:1000])

if __name__ == "__main__":
    main()
