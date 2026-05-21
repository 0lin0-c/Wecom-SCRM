# -*- coding: utf-8 -*-
"""
FastAPI 路由：所有 /wechat/callback 端点 + H5 API 端点
v5新增：客户群事件处理（进群自动发现、成员变更同步）
千院千群新增：/api/hospitals, /api/config, /api/group/register, /api/jsapi/signature
"""
import os
import time
import hashlib
import threading
import requests
from fastapi import Query, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
import xmltodict
from wechatpy.exceptions import InvalidSignatureException
from app import app
from app.config import app_crypto, contact_crypto
from app.ai_chat import chat_with_ai_and_execute
from app.event_handlers import handle_add_external_contact, handle_external_contact_msg
from app.kf_handler import process_kf_notification


# ================= 挂载静态文件 =================

static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)


# ================= JSAPI Ticket 缓存 =================

_enterprise_ticket_cache = {"ticket": None, "expires_at": 0}
_agent_ticket_cache = {"ticket": None, "expires_at": 0}
_ticket_lock = threading.Lock()


def _get_enterprise_jsapi_ticket(access_token):
    """获取企业 jsapi_ticket（带缓存，有效期7200秒）"""
    with _ticket_lock:
        now = time.time()
        if _enterprise_ticket_cache["ticket"] and now < _enterprise_ticket_cache["expires_at"]:
            return _enterprise_ticket_cache["ticket"]

        url = f"https://qyapi.weixin.qq.com/cgi-bin/get_jsapi_ticket?access_token={access_token}"
        try:
            resp = requests.get(url, timeout=10).json()
            ticket = resp.get("ticket")
            if ticket:
                _enterprise_ticket_cache["ticket"] = ticket
                _enterprise_ticket_cache["expires_at"] = now + 7000
                return ticket
            else:
                print(f"[JSAPI] get enterprise jsapi_ticket failed: {resp}")
                return None
        except Exception as e:
            print(f"[JSAPI] get enterprise jsapi_ticket error: {e}")
            return None


def _get_agent_jsapi_ticket(access_token):
    """获取应用 jsapi_ticket（带缓存，有效期7200秒）"""
    with _ticket_lock:
        now = time.time()
        if _agent_ticket_cache["ticket"] and now < _agent_ticket_cache["expires_at"]:
            return _agent_ticket_cache["ticket"]

        url = f"https://qyapi.weixin.qq.com/cgi-bin/ticket/get?access_token={access_token}&type=agent_config"
        try:
            resp = requests.get(url, timeout=10).json()
            ticket = resp.get("ticket")
            if ticket:
                _agent_ticket_cache["ticket"] = ticket
                _agent_ticket_cache["expires_at"] = now + 7000
                return ticket
            else:
                print(f"[JSAPI] get agent jsapi_ticket failed: {resp}")
                return None
        except Exception as e:
            print(f"[JSAPI] get agent jsapi_ticket error: {e}")
            return None


# ================= 企微回调端点 =================

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
        event = msg_dict.get('Event')
        sender_id = msg_dict.get('FromUserName')

        if msg_type == 'text':
            content = msg_dict.get('Content')
            print(f"[APP MSG] {sender_id}: {content}")
            background_tasks.add_task(chat_with_ai_and_execute, sender_id, content)

        elif msg_type == 'event':
            if event == 'kf_msg_or_event':
                callback_token = msg_dict.get('Token', '')
                open_kfid = msg_dict.get('OpenKfId', '')
                print(f"[KF CALLBACK] open_kfid={open_kfid}, token={'有' if callback_token else '无'}")
                if open_kfid:
                    try:
                        process_kf_notification(callback_token, open_kfid)
                    except Exception as e:
                        print(f"[KF] process_kf_notification error: {e}")

            elif event == 'change_external_contact':
                change_type = msg_dict.get('ChangeType', '')
                if change_type == 'add_external_contact':
                    background_tasks.add_task(handle_add_external_contact, msg_dict)
                elif change_type == 'del_external_contact':
                    print(f"[EVENT] del contact: {msg_dict}")

            elif event == 'change_external_chat':
                # v5新增：客户群事件（进群、退群、新建群）
                _handle_group_event(msg_dict, background_tasks)

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


# ================= v5新增：客户群事件处理 =================

def _handle_group_event(msg_dict, background_tasks):
    """处理客户群事件回调（通过自建应用回调推送）

    事件类型：change_external_chat
    - add_chat: 新建客户群 → 直接注册并生成活码
    - add_member: 外部联系人加入群 → 同步成员数
    - del_member: 外部联系人退出群 → 同步成员数
    """
    change_type = msg_dict.get('ChangeType', '')
    chat_id = msg_dict.get('ChatId', '')
    external_userid = msg_dict.get('ExternalUserID', '')

    print(f"[GROUP EVENT] change_type={change_type}, chat_id={chat_id}, external_userid={external_userid}")

    if change_type == 'add_chat':
        # 新建客户群，直接注册并生成活码
        def _register_new_group(chat_id=chat_id):
            from app.group_b_api import get_customer_group_chat, register_group_and_create_qr, discover_and_register_groups
            from app.database import save_group_b, get_group_b_live_qr, get_hospital_by_name, save_hospital

            # 先检查是否已注册
            import sqlite3
            conn = sqlite3.connect('wecom_cache.db')
            cursor = conn.cursor()
            cursor.execute("SELECT chat_id FROM group_b WHERE chat_id = ?", (chat_id,))
            if cursor.fetchone():
                conn.close()
                print(f"[GROUP EVENT] 群 {chat_id} 已注册，跳过")
                return
            conn.close()

            # 获取群详情
            detail = get_customer_group_chat(chat_id)
            chat_name = ""
            hospital = ""
            if detail.get("errcode") == 0:
                group_chat = detail.get("group_chat", {})
                chat_name = group_chat.get("name", "")
                # 从群名中提取医院名
                if "患者交流" in chat_name:
                    hospital = chat_name.split("患者交流")[0]
                elif chat_name:
                    # 尝试其他匹配：群名可能就是"XX医院XX群"
                    for h in get_hospital_by_name.__module__:
                        break
                    # 遍历已有医院，看群名是否包含某个医院名
                    from app.database import get_all_hospitals
                    for h_info in get_all_hospitals():
                        if h_info["hospital"] in chat_name:
                            hospital = h_info["hospital"]
                            break

            if not hospital:
                # 无法确定医院，用discover兜底
                print(f"[GROUP EVENT] 群 {chat_id} 名为'{chat_name}'，无法匹配医院，触发discover")
                discover_and_register_groups()
                return

            # 注册群并生成活码
            print(f"[GROUP EVENT] 注册新群: {chat_name} -> {chat_id}, 医院={hospital}")
            result = register_group_and_create_qr(hospital, chat_id)
            if result:
                print(f"[GROUP EVENT] 活码生成成功: {result.get('qr_code', '')[:50]}")
            else:
                print(f"[GROUP EVENT] 活码生成失败")

        background_tasks.add_task(_register_new_group)

    elif change_type in ('add_member', 'del_member'):
        # 成员变更，同步群B成员数
        from app.database import refresh_group_b_member_count
        import sqlite3
        conn = sqlite3.connect('wecom_cache.db')
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id FROM group_b WHERE chat_id = ? AND status = 'active'", (chat_id,))
        if cursor.fetchone():
            conn.close()
            background_tasks.add_task(refresh_group_b_member_count, chat_id)
        else:
            conn.close()
            # 未知群，可能是新建的，触发自动发现
            from app.group_b_api import discover_and_register_groups
            background_tasks.add_task(discover_and_register_groups)


# ================= 千院千群：H5 API 端点 =================

@app.get("/api/hospitals")
async def list_hospitals():
    """列出所有医院（H5下拉框用）"""
    from app.database import get_all_hospitals
    hospitals = get_all_hospitals()
    return {"hospitals": hospitals}


@app.get("/api/config")
async def get_frontend_config():
    """获取前端配置（工具人external_userid、当前员工userId等）"""
    from app.config import TOOL_PERSON_EXTERNAL_USERID, DEFAULT_EMPLOYEE_USERID, SECOND_EMPLOYEE_USERID
    return {
        "tool_person_external_userid": TOOL_PERSON_EXTERNAL_USERID,
        "employee_userid": DEFAULT_EMPLOYEE_USERID,
        "second_employee_userid": SECOND_EMPLOYEE_USERID
    }


@app.get("/api/group/check_qr")
async def check_group_qr(hospital: str = Query(...)):
    """检查某医院的群活码是否已生成（H5轮询用）"""
    from app.database import get_group_b_live_qr
    live_qr = get_group_b_live_qr(hospital)
    if live_qr and live_qr['qr_code_url']:
        return {"qr_code": live_qr['qr_code_url'], "config_id": live_qr['config_id']}
    return {"qr_code": ""}


@app.post("/api/group/register")
async def register_group(request: Request):
    """注册新创建的群并生成活码

    H5页面通过 openEnterpriseChat 建群成功后调用
    Request body: {"chat_id": "wrOgQhDgAAxxxxx", "hospital": "北京协和医院"}
    """
    body = await request.json()
    chat_id = body.get("chat_id", "")
    hospital = body.get("hospital", "")

    if not chat_id or not hospital:
        return {"errcode": -1, "errmsg": "chat_id and hospital are required"}

    from app.group_b_api import register_group_and_create_qr
    result = register_group_and_create_qr(hospital, chat_id)

    if result:
        return {"errcode": 0, "errmsg": "ok", "qr_code": result.get("qr_code", ""), "config_id": result.get("config_id", "")}
    else:
        return {"errcode": -1, "errmsg": "Failed to create live QR"}


@app.post("/api/log")
async def client_log(request: Request):
    """接收前端日志上报"""
    body = await request.json()
    print(f"[H5 LOG] {body.get('time','')} {body.get('msg','')}")
    return {"errcode": 0}


@app.get("/api/group/list")
async def list_groups(hospital: str = Query(...)):
    """获取某医院所有群+活码信息"""
    from app.database import get_group_b_by_hospital, get_group_b_live_qr
    rows = get_group_b_by_hospital(hospital)
    groups = [{"chat_id": r[0], "hospital": r[1], "chat_name": r[2], "member_count": r[3]} for r in rows]
    live_qr = get_group_b_live_qr(hospital)
    live_qr_data = None
    if live_qr:
        live_qr_data = {
            "qr_code_url": live_qr.get("qr_code_url", ""),
            "config_id": live_qr.get("config_id", ""),
            "chat_ids": live_qr.get("chat_ids", [])
        }
    return {"hospital": hospital, "groups": groups, "live_qr": live_qr_data}


@app.post("/api/hospital/manage")
async def manage_hospital(request: Request):
    """新增/删除医院"""
    body = await request.json()
    action = body.get("action", "")
    hospital = body.get("hospital", "").strip()

    if not action or not hospital:
        return {"errcode": -1, "errmsg": "action and hospital are required"}

    if action == "add":
        from app.database import save_hospital
        save_hospital(hospital)
        return {"errcode": 0, "errmsg": "ok"}
    elif action == "delete":
        from app.database import delete_hospital
        delete_hospital(hospital)
        return {"errcode": 0, "errmsg": "ok"}
    else:
        return {"errcode": -1, "errmsg": "action must be 'add' or 'delete'"}


@app.get("/api/jsapi/signature")
async def get_jsapi_signature(url: str = Query(...)):
    """生成 JS-SDK 签名（H5页面鉴权用）

    返回 config 和 agentConfig 两套签名，供 ww.register() 使用
    """
    import string
    import random
    from app.config import WECOM_CORP_ID, WECOM_AGENT_ID
    from app.wechat_api import get_wecom_access_token

    token = get_wecom_access_token()
    if not token:
        return {"errcode": -1, "errmsg": "no access token"}

    # 生成随机字符串和时间戳
    nonce_str = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    timestamp = str(int(time.time()))

    # --- 企业 jsapi_ticket（用于 config 签名）---
    enterprise_ticket = _get_enterprise_jsapi_ticket(token)
    if not enterprise_ticket:
        return {"errcode": -1, "errmsg": "failed to get enterprise jsapi_ticket"}

    # 生成 config 签名
    config_string = f"jsapi_ticket={enterprise_ticket}&noncestr={nonce_str}&timestamp={timestamp}&url={url}"
    config_signature = hashlib.sha1(config_string.encode('utf-8')).hexdigest()

    # --- 应用 jsapi_ticket（用于 agentConfig 签名）---
    agent_ticket = _get_agent_jsapi_ticket(token)
    if not agent_ticket:
        return {"errcode": -1, "errmsg": "failed to get agent jsapi_ticket"}

    # 生成 agentConfig 签名
    agent_string = f"jsapi_ticket={agent_ticket}&noncestr={nonce_str}&timestamp={timestamp}&url={url}"
    agent_signature = hashlib.sha1(agent_string.encode('utf-8')).hexdigest()

    return {
        "errcode": 0,
        "corpId": WECOM_CORP_ID,
        "agentId": WECOM_AGENT_ID,
        "timestamp": timestamp,
        "nonceStr": nonce_str,
        "configSignature": config_signature,
        "agentConfigSignature": agent_signature
    }


# ================= 挂载静态文件（必须放在所有路由之后）=================

app.mount("/static", StaticFiles(directory=static_dir), name="static")
