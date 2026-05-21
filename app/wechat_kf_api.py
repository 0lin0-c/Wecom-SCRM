# -*- coding: utf-8 -*-
"""
微信客服(KF) API：sync_msg、send_msg、service_state、cursor
"""
import time
import uuid
import requests
from app.config import KF_OPEN_KFID
from app.wechat_api import get_wecom_access_token
from app.database import (
    get_kf_conversation, increment_kf_reply_count,
    save_kf_cursor, get_kf_cursor
)


def get_kf_access_token():
    return get_wecom_access_token()


def kf_get_account_list():
    token = get_kf_access_token()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/kf/account/list?access_token={token}"
    resp = requests.post(url, json={"offset": 0, "limit": 100}).json()
    return resp


def kf_get_account_link(open_kfid, scene=""):
    token = get_kf_access_token()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/kf/add_contact_way?access_token={token}"
    payload = {"open_kfid": open_kfid, "scene": scene}
    resp = requests.post(url, json=payload).json()
    return resp


def kf_sync_msg(open_kfid, callback_token, cursor=""):
    token = get_kf_access_token()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/kf/sync_msg?access_token={token}"
    payload = {"open_kfid": open_kfid, "token": callback_token, "limit": 1000}
    if cursor:
        payload["cursor"] = cursor
    resp = requests.post(url, json=payload).json()
    return resp


def kf_send_msg(touser, open_kfid, content):
    """发送消息给客户（48小时内可回复，每次用户消息后可回复5条）"""
    row = get_kf_conversation(touser, open_kfid)

    if row:
        last_msg_time = row[0]
        now = time.time()
        if now - last_msg_time > 172800:
            print(f"[KF] 超过48小时，无法回复客户 {touser}")
            return {"errcode": -1, "errmsg": "exceeded 48h limit"}

    token = get_kf_access_token()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/kf/send_msg?access_token={token}"

    msgid = f"msg_{uuid.uuid4().hex[:24]}"
    payload = {
        "touser": touser,
        "open_kfid": open_kfid,
        "msgid": msgid,
        "msgtype": "text",
        "text": {"content": content}
    }

    resp = requests.post(url, json=payload).json()

    if resp.get("errcode") == 0:
        increment_kf_reply_count(touser, open_kfid)

    return resp


def kf_send_msg_on_event(code, content):
    """发送欢迎语等事件响应消息（code仅可使用一次）"""
    token = get_kf_access_token()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/kf/send_msg_on_event?access_token={token}"
    payload = {"code": code, "msgtype": "text", "text": {"content": content}}
    resp = requests.post(url, json=payload).json()
    return resp


def kf_get_service_state(open_kfid, external_userid):
    token = get_kf_access_token()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/kf/service_state/get?access_token={token}"
    payload = {"open_kfid": open_kfid, "external_userid": external_userid}
    resp = requests.post(url, json=payload).json()
    return resp


def kf_trans_service_state(open_kfid, external_userid, service_state, servicer_userid=""):
    """变更会话状态
    service_state: 1-由智能助手接待, 2-待接入池排队, 3-由人工接待, 4-已结束
    """
    token = get_kf_access_token()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/kf/service_state/trans?access_token={token}"
    payload = {
        "open_kfid": open_kfid,
        "external_userid": external_userid,
        "service_state": service_state
    }
    if servicer_userid:
        payload["servicer_userid"] = servicer_userid
    resp = requests.post(url, json=payload).json()
    return resp


def resolve_kf_open_kfid():
    """确定使用哪个客服账号ID"""
    if KF_OPEN_KFID:
        return KF_OPEN_KFID
    resp = kf_get_account_list()
    accounts = resp.get("account_list", [])
    if accounts:
        open_kfid = accounts[0].get("open_kfid", "")
        print(f"[KF] 自动选择客服账号: {open_kfid}")
        return open_kfid
    print("[KF] 未找到任何客服账号，请先在企微后台创建")
    return ""
