# -*- coding: utf-8 -*-
"""
修改客户备注为 chl
"""

import requests
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

WECOM_CORP_ID = "ww893ef078a0935650"
WECOM_SECRET = "NwTTbs4A7iaFa36SuyznKvDPNdsUb1jQsII-DUn_HX0"

def modify_remark():
    # 1. 获取 access_token
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={WECOM_CORP_ID}&corpsecret={WECOM_SECRET}"
    resp = requests.get(url).json()
    token = resp.get("access_token")
    
    # 2. 修改备注
    employee_userid = "CaoHuiLin"
    external_userid = "wop7GUBwAAq7SMuaHt3tacVuwbt1YzhQ"
    new_remark = "chl"
    
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/remark?access_token={token}"
    resp = requests.post(url, json={
        "userid": employee_userid,
        "external_userid": external_userid,
        "remark": new_remark
    }).json()
    
    print(f"Response: {json.dumps(resp, indent=2, ensure_ascii=False)}")
    
    if resp.get("errcode") == 0:
        print(f"[SUCCESS] Remark changed to: {new_remark}")
    else:
        print(f"[FAIL] {resp.get('errmsg')}")

if __name__ == "__main__":
    modify_remark()
