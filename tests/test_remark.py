"""
测试企业微信 remark 接口权限
运行前请确保已同步客户数据，且知道一个 external_userid
"""

import requests

WECOM_CORP_ID = "ww893ef078a0935650"
WECOM_SECRET = "NwTTbs4A7iaFa36SuyznKvDPNdsUb1jQsII-DUn_HX0"  # 当前自建应用的 Secret

def get_access_token():
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={WECOM_CORP_ID}&corpsecret={WECOM_SECRET}"
    resp = requests.get(url).json()
    print(f"获取 token 返回: {resp}")
    return resp.get("access_token")

def test_remark_api():
    token = get_access_token()
    if not token:
        print("❌ 无法获取 access_token，请检查 CorpID 和 Secret")
        return
    
    # 测试调用 remark 接口（用一个假的 external_userid 来测试权限）
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/remark?access_token={token}"
    
    # 这里的参数需要你替换成真实的
    # employee_userid: 员工的企微账号（如 "ZhangSan"）
    # external_userid: 外部联系人的ID（如 "wmXXXXXXXX"，需要先同步获取）
    test_payload = {
        "userid": "你的员工企微账号",  # ← 替换
        "external_userid": "wmXXXXXXXX",  # ← 替换为真实的 external_userid
        "remark": "测试备注"
    }
    
    print(f"\n请求参数: {test_payload}")
    resp = requests.post(url, json=test_payload).json()
    print(f"接口返回: {resp}")
    
    if resp.get("errcode") == 0:
        print("✅ 有权限！接口调用成功")
    elif resp.get("errcode") == 60011:
        print("❌ 权限不足！当前应用没有客户联系权限")
    elif resp.get("errcode") == 60012:
        print("❌ 无效的 external_userid 或该员工没有此客户")
    else:
        print(f"❌ 其他错误: {resp.get('errmsg')}")

if __name__ == "__main__":
    test_remark_api()
