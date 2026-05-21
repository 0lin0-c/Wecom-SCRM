# -*- coding: utf-8 -*-
"""
企业微信 API：access_token（带缓存）、发送消息、同步客户、修改备注
"""
import time
import threading
import sqlite3
import requests
from app.config import WECOM_CORP_ID, WECOM_SECRET, WECOM_AGENT_ID

_access_token_cache = {"token": None, "expires_at": 0}
_access_token_lock = threading.Lock()


def get_wecom_access_token():
    """获取企微access_token，带缓存（有效期7200秒，提前200秒刷新）"""
    with _access_token_lock:
        now = time.time()
        if _access_token_cache["token"] and now < _access_token_cache["expires_at"]:
            return _access_token_cache["token"]

        url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={WECOM_CORP_ID}&corpsecret={WECOM_SECRET}"
        try:
            resp = requests.get(url, timeout=10).json()
            token = resp.get("access_token")
            if token:
                _access_token_cache["token"] = token
                _access_token_cache["expires_at"] = now + 7000
                return token
            else:
                print(f"[TOKEN] 获取access_token失败: {resp}")
                return None
        except Exception as e:
            print(f"[TOKEN] 获取access_token异常: {e}")
            return None


def send_welcome_message(welcome_code, message):
    token = get_wecom_access_token()
    if not token:
        return {"errcode": -1, "errmsg": "no access token"}
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/send_welcome_msg?access_token={token}"
    payload = {"welcome_code": welcome_code, "text": {"content": message}}
    resp = requests.post(url, json=payload).json()
    print(f"[welcome msg] result: {resp}")
    return resp


def send_wecom_message(to_user, content):
    token = get_wecom_access_token()
    if not token:
        return
    url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
    requests.post(url, json={
        "touser": to_user,
        "msgtype": "text",
        "agentid": WECOM_AGENT_ID,
        "text": {"content": content}
    })


def sync_employee_customers(employee_userid):
    token = get_wecom_access_token()
    if not token:
        return f"sync failed: no access token"
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/batch/get_by_user?access_token={token}"

    cursor_str = ""
    total_synced = 0
    conn = sqlite3.connect('wecom_cache.db')
    db_cursor = conn.cursor()

    while True:
        resp = requests.post(url, json={"userid_list": [employee_userid], "cursor": cursor_str, "limit": 100}).json()
        if resp.get("errcode") != 0:
            return f"sync failed: {resp.get('errmsg')}"

        for item in resp.get("external_contact_list", []):
            contact = item.get("external_contact", {})
            name = contact.get("name")
            eid = contact.get("external_userid")
            if name and eid:
                follow_info = item.get("follow_info", {})
                remark = follow_info.get("remark", "")
                db_cursor.execute(
                    "REPLACE INTO customers (employee_userid, customer_name, external_userid, remark) VALUES (?, ?, ?, ?)",
                    (employee_userid, name, eid, remark)
                )
                total_synced += 1

        cursor_str = resp.get("next_cursor")
        if not cursor_str:
            break

    conn.commit()
    conn.close()
    return f"sync done! total: {total_synced}"


def modify_customer_remark(employee_userid, customer_name, new_remark):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute("SELECT external_userid, customer_name FROM customers WHERE employee_userid=? AND customer_name=?",
                   (employee_userid, customer_name))
    row = cursor.fetchone()
    if not row:
        cursor.execute("SELECT external_userid, customer_name FROM customers WHERE employee_userid=? AND remark=?",
                       (employee_userid, customer_name))
        row = cursor.fetchone()
    if not row:
        cursor.execute(
            "SELECT external_userid, customer_name FROM customers WHERE employee_userid=? AND (customer_name LIKE ? OR remark LIKE ?)",
            (employee_userid, f"%{customer_name}%", f"%{customer_name}%"))
        row = cursor.fetchone()
    if not row:
        conn.close()
        return f"contact [{customer_name}] not found. Please sync data first or check the name."

    target_external_userid = row[0]
    conn.close()

    token = get_wecom_access_token()
    if not token:
        return "failed: no access token"
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/remark?access_token={token}"
    resp = requests.post(url, json={
        "userid": employee_userid,
        "external_userid": target_external_userid,
        "remark": new_remark
    }).json()

    if resp.get("errcode") == 0:
        return f"remark changed to: {new_remark}"
    else:
        return f"failed: {resp.get('errmsg')}"
