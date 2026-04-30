# -*- coding: utf-8 -*-
"""
企业微信自动接待系统 v3
支持：扫码添加好友 -> 自动发欢迎语 -> 询问手机尾号
"""

import json
import requests
import sqlite3
import xmltodict
from fastapi import FastAPI, Query, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse
from wechatpy.enterprise.crypto import WeChatCrypto
from wechatpy.exceptions import InvalidSignatureException

app = FastAPI()

# ================= 1. 基础配置区 =================
WECOM_CORP_ID = "ww893ef078a0935650"
WECOM_SECRET = "NwTTbs4A7iaFa36SuyznKvDPNdsUb1jQsII-DUn_HX0"
WECOM_AGENT_ID = 1000035

# 自建应用的回调配置
APP_TOKEN = "0wG5odkRURpJZAn3tQJC4Qbb"
APP_AES_KEY = "4ABQ5joZC5cFt2qntCsqU1RCh33cMDReUubxgVU3F3L"

# 客户联系的回调配置
CONTACT_TOKEN = "0wG5odkRURpJZAn3tQJC4Qbb"
CONTACT_AES_KEY = "4ABQ5joZC5cFt2qntCsqU1RCh33cMDReUubxgVU3F3L"

# AI 配置
OPENAI_API_KEY = "sk-sp-iP9d7tGzkcMhgjkDVhhZ7XIhhZuTfZEGORVw0TlltsALWQq7"
OPENAI_BASE_URL = "https://api.lkeap.cloud.tencent.com/coding/v3/chat/completions"
MODEL_NAME = "glm-5"

# 欢迎语模板
WELCOME_MESSAGE = """您好！我是您的专属营养顾问助手

为了更好地为您提供服务，请回复您的【手机尾号后4位】，我将为您匹配专属营养方案。"""

# 创建加密器
app_crypto = WeChatCrypto(APP_TOKEN, APP_AES_KEY, WECOM_CORP_ID)
contact_crypto = WeChatCrypto(CONTACT_TOKEN, CONTACT_AES_KEY, WECOM_CORP_ID)

# ================= 2. 数据库 =================

def init_db():
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            employee_userid TEXT,
            customer_name TEXT,
            external_userid TEXT,
            PRIMARY KEY (employee_userid, external_userid)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reception_progress (
            external_userid TEXT PRIMARY KEY,
            employee_userid TEXT,
            add_time TEXT,
            phone_tail TEXT,
            hospital TEXT,
            patient_matched INTEGER DEFAULT 0,
            welcome_sent INTEGER DEFAULT 0,
            phone_received INTEGER DEFAULT 0,
            status TEXT DEFAULT 'in_progress',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ================= 3. 企业微信 API =================

def get_wecom_access_token():
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={WECOM_CORP_ID}&corpsecret={WECOM_SECRET}"
    return requests.get(url).json().get("access_token")

def send_welcome_message(welcome_code, message):
    token = get_wecom_access_token()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/send_welcome_msg?access_token={token}"
    
    payload = {
        "welcome_code": welcome_code,
        "text": {"content": message}
    }
    
    resp = requests.post(url, json=payload).json()
    print(f"[welcome msg] result: {resp}")
    return resp

def send_wecom_message(to_user, content):
    token = get_wecom_access_token()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
    requests.post(url, json={
        "touser": to_user, 
        "msgtype": "text", 
        "agentid": WECOM_AGENT_ID,
        "text": {"content": content}
    })

def sync_employee_customers(employee_userid):
    token = get_wecom_access_token()
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
                db_cursor.execute("REPLACE INTO customers (employee_userid, customer_name, external_userid) VALUES (?, ?, ?)", 
                                  (employee_userid, name, eid))
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
    cursor.execute("SELECT external_userid FROM customers WHERE employee_userid=? AND customer_name=?", (employee_userid, customer_name))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return f"contact [{customer_name}] not found, please sync data first."
        
    target_external_userid = row[0]
    
    token = get_wecom_access_token()
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

def create_reception_progress(external_userid, employee_userid):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO reception_progress 
        (external_userid, employee_userid, add_time, welcome_sent, status) 
        VALUES (?, ?, datetime('now'), 1, 'in_progress')
    ''', (external_userid, employee_userid))
    conn.commit()
    conn.close()

def update_phone_received(external_userid, phone_tail):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE reception_progress 
        SET phone_tail = ?, phone_received = 1, updated_at = datetime('now')
        WHERE external_userid = ?
    ''', (phone_tail, external_userid))
    conn.commit()
    conn.close()

# ================= 4. 事件处理 =================

def handle_add_external_contact(msg_dict):
    employee_userid = msg_dict.get('UserID')
    external_userid = msg_dict.get('ExternalUserID')
    welcome_code = msg_dict.get('WelcomeCode')
    state = msg_dict.get('State', '')
    
    print(f"[EVENT] add contact: employee={employee_userid}, external={external_userid}, state={state}")
    
    if welcome_code:
        result = send_welcome_message(welcome_code, WELCOME_MESSAGE)
        
        if result.get("errcode") == 0:
            print(f"[SUCCESS] welcome message sent")
            create_reception_progress(external_userid, employee_userid)
        else:
            print(f"[FAILED] welcome message: {result}")
    else:
        print(f"[WARN] no WelcomeCode, cannot send welcome message")

def handle_external_contact_msg(msg_dict):
    msg_type = msg_dict.get('MsgType')
    external_userid = msg_dict.get('FromUserName')
    employee_userid = msg_dict.get('ToUserName')
    
    print(f"[MSG] external contact message: {external_userid} -> {employee_userid}, type={msg_type}")
    
    if msg_type == 'text':
        content = msg_dict.get('Content', '').strip()
        
        if content.isdigit() and len(content) == 4:
            print(f"[PHONE] received: {content}")
            update_phone_received(external_userid, content)

# ================= 5. AI 对话 =================

def chat_with_ai_and_execute(employee_userid, user_message):
    if user_message.strip() == "sync data":
        send_wecom_message(employee_userid, "syncing...")
        result = sync_employee_customers(employee_userid)
        send_wecom_message(employee_userid, result)
        return

    tools = [{
        "type": "function",
        "function": {
            "name": "modify_customer_remark",
            "description": "modify customer remark",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string"},
                    "new_remark": {"type": "string"}
                },
                "required": ["customer_name", "new_remark"]
            }
        }
    }]

    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": user_message}],
        "tools": tools,
        "tool_choice": "auto"
    }
    
    raw_resp = requests.post(OPENAI_BASE_URL, headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, json=payload)
    resp = raw_resp.json()
    message_obj = resp["choices"][0]["message"]

    if message_obj.get("tool_calls"):
        tool_call = message_obj["tool_calls"][0]
        if tool_call["function"]["name"] == "modify_customer_remark":
            args = json.loads(tool_call["function"]["arguments"])
            result_str = modify_customer_remark(employee_userid, args["customer_name"], args["new_remark"])
            send_wecom_message(employee_userid, f"result: {result_str}")
    else:
        final_reply = message_obj.get("content", "I don't understand.")
        send_wecom_message(employee_userid, final_reply)

# ================= 6. FastAPI 路由 =================

@app.get("/wechat/callback")
async def app_verify_url(
    msg_signature: str = Query(...), 
    timestamp: str = Query(...), 
    nonce: str = Query(...), 
    echostr: str = Query(...)
):
    try:
        decrypted_echostr = app_crypto.check_signature(msg_signature, timestamp, nonce, echostr)
        return PlainTextResponse(content=decrypted_echostr)
    except InvalidSignatureException:
        return PlainTextResponse(content="signature check failed", status_code=403)

@app.post("/wechat/callback")
async def app_receive_msg(
    request: Request,
    background_tasks: BackgroundTasks,
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...)
):
    raw_body = await request.body()
    try:
        decrypted_xml = app_crypto.decrypt_message(raw_body, msg_signature, timestamp, nonce)
        msg_dict = xmltodict.parse(decrypted_xml)['xml']
        
        msg_type = msg_dict.get('MsgType')
        sender_id = msg_dict.get('FromUserName')
        
        if msg_type == 'text':
            content = msg_dict.get('Content')
            print(f"[APP MSG] {sender_id}: {content}")
            background_tasks.add_task(chat_with_ai_and_execute, sender_id, content)
            
        return PlainTextResponse(content="success")
        
    except Exception as e:
        print(f"decrypt error: {e}")
        return PlainTextResponse(content="success")

@app.get("/wechat/contact/callback")
async def contact_verify_url(
    msg_signature: str = Query(...), 
    timestamp: str = Query(...), 
    nonce: str = Query(...), 
    echostr: str = Query(...)
):
    try:
        decrypted_echostr = contact_crypto.check_signature(msg_signature, timestamp, nonce, echostr)
        return PlainTextResponse(content=decrypted_echostr)
    except InvalidSignatureException:
        return PlainTextResponse(content="signature check failed", status_code=403)

@app.post("/wechat/contact/callback")
async def contact_receive_event(
    request: Request,
    background_tasks: BackgroundTasks,
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...)
):
    raw_body = await request.body()
    try:
        decrypted_xml = contact_crypto.decrypt_message(raw_body, msg_signature, timestamp, nonce)
        msg_dict = xmltodict.parse(decrypted_xml)['xml']
        
        msg_type = msg_dict.get('MsgType')
        event = msg_dict.get('Event')
        change_type = msg_dict.get('ChangeType')
        
        print(f"[CONTACT EVENT] msg_type={msg_type}, event={event}, change_type={change_type}")
        
        if msg_type == 'event' and event == 'change_external_contact':
            if change_type == 'add_external_contact':
                background_tasks.add_task(handle_add_external_contact, msg_dict)
            elif change_type == 'del_external_contact':
                print(f"[EVENT] del contact: {msg_dict}")
                
        return PlainTextResponse(content="success")
        
    except Exception as e:
        print(f"decrypt error: {e}")
        return PlainTextResponse(content="success")

# ================= 7. 启动 =================

if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("WeChat Work Auto Reception v3")
    print("=" * 50)
    print(f"App callback: http://111.229.157.67:8500/wechat/callback")
    print(f"Contact callback: http://111.229.157.67:8500/wechat/contact/callback")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8500)
