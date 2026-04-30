# -*- coding: utf-8 -*-
"""
为新企业创建「联系我」二维码
运行前修改下面的配置
"""
import requests
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

# ========= 修改这里的配置 =========
WECOM_CORP_ID = "替换为新企业的CorpID"
WECOM_SECRET = "替换为新企业自建应用的Secret"
EMPLOYEE_USERID = "替换为测试员工的UserID"
# ===================================

def get_token():
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={WECOM_CORP_ID}&corpsecret={WECOM_SECRET}"
    resp = requests.get(url).json()
    if resp.get("errcode") != 0:
        print(f"[ERROR] {resp}")
        return None
    return resp.get("access_token")

def create_contact_way(token):
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/add_contact_way?access_token={token}"
    resp = requests.post(url, json={
        "type": 2,              # 单人
        "scene": 2,             # 添加外部联系人
        "skip_verify": True,    # 自动通过
        "user": [EMPLOYEE_USERID],
        "state": "reception_flow"
    }).json()
    print(f"[Result] {json.dumps(resp, indent=2, ensure_ascii=False)}")
    
    if resp.get("errcode") == 0:
        print(f"\n[OK] config_id: {resp.get('config_id')}")
        print(f"[OK] QR Code URL: {resp.get('qr_code')}")
    else:
        print(f"[FAIL] {resp.get('errmsg')}")
    
    return resp

if __name__ == "__main__":
    token = get_token()
    if token:
        create_contact_way(token)
