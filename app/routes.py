# -*- coding: utf-8 -*-
"""
FastAPI 路由：所有 /wechat/callback 端点
"""
from fastapi import Query, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse
import xmltodict
from wechatpy.exceptions import InvalidSignatureException
from app import app
from app.config import app_crypto, contact_crypto
from app.ai_chat import chat_with_ai_and_execute
from app.event_handlers import handle_add_external_contact, handle_external_contact_msg
from app.kf_handler import process_kf_notification


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

        elif msg_type == 'event' and event == 'kf_msg_or_event':
            callback_token = msg_dict.get('Token', '')
            open_kfid = msg_dict.get('OpenKfId', '')
            print(f"[KF CALLBACK] open_kfid={open_kfid}, token={'有' if callback_token else '无'}")
            if open_kfid:
                try:
                    process_kf_notification(callback_token, open_kfid)
                except Exception as e:
                    print(f"[KF] process_kf_notification error: {e}")

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
