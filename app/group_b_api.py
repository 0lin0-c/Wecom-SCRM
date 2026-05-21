# -*- coding: utf-8 -*-
"""
群B API：客户群管理、活码（add_join_way scene=2）、自动发现
v5更新：修正API路径、参数名、两步获取二维码、room_base_name/room_base_id
"""
import json
import sqlite3
import requests
from app.wechat_api import get_wecom_access_token
from app.database import (
    save_group_b, get_group_b_by_hospital, get_group_b_available,
    get_group_b_live_qr, save_group_b_live_qr, update_group_b_live_qr_chat_ids,
    refresh_group_b_member_count, get_hospital_by_name, save_hospital
)


# ================= 客户群查询 =================

def list_customer_group_chats(owner_userid=None, status_filter=0, offset=0, limit=100):
    """获取客户群列表

    API: externalcontact/groupchat/list
    """
    token = get_wecom_access_token()
    if not token:
        return {"errcode": -1, "errmsg": "no access token"}
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/groupchat/list?access_token={token}"
    payload = {
        "status_filter": status_filter,
        "offset": offset,
        "limit": limit
    }
    if owner_userid:
        payload["owner_filter"] = {"userid_list": [owner_userid]}
    resp = requests.post(url, json=payload).json()
    return resp


def get_customer_group_chat(chat_id, need_member_detail=1):
    """获取客户群详情

    API: externalcontact/groupchat/get
    """
    token = get_wecom_access_token()
    if not token:
        return {"errcode": -1, "errmsg": "no access token"}
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/groupchat/get?access_token={token}"
    payload = {
        "chat_id": chat_id,
        "need_member_detail": need_member_detail
    }
    resp = requests.post(url, json=payload).json()
    return resp


# ================= 群B活码（add_join_way scene=2）=================

def create_group_b_join_way(hospital, chat_ids, auto_create_room=True, room_base_name="", room_base_id=1):
    """创建"加入客户群"二维码（scene=2 模式）

    API: externalcontact/groupchat/add_join_way
    - scene: 2 - 通过二维码加入群聊
    - auto_create_room: 当群满时是否自动创建新群
    - room_base_name: 自动建群的群名前缀
    - room_base_id: 自动建群的起始序号

    两步获取二维码：add_join_way 只返回 config_id，需再调 get_join_way 获取 qr_code

    返回 {"config_id": ..., "qr_code": ...} 或 None
    """
    token = get_wecom_access_token()
    if not token:
        return None

    # Step 1: 调用 add_join_way 创建配置（仅返回 config_id）
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/groupchat/add_join_way?access_token={token}"
    payload = {
        "scene": 2,
        "chat_id_list": chat_ids,
        "auto_create_room": 1 if auto_create_room else 0,
        "remark": f"{hospital}-病友交流群活码"
    }
    if room_base_name:
        payload["room_base_name"] = room_base_name
    if room_base_id:
        payload["room_base_id"] = room_base_id

    resp = requests.post(url, json=payload).json()
    print(f"[JOIN-WAY] create: hospital={hospital}, chat_ids={chat_ids}, resp={resp}")

    if resp.get("errcode") != 0:
        return None

    config_id = resp.get("config_id", "")

    # Step 2: 调用 get_join_way 获取实际的 qr_code URL
    qr_code_url = ""
    get_resp = get_group_b_join_way(config_id)
    if get_resp and get_resp.get("errcode") == 0:
        join_way = get_resp.get("join_way", {})
        qr_code_url = join_way.get("qr_code", "")

    # Step 3: 保存到数据库
    save_group_b_live_qr(hospital, config_id, qr_code_url, chat_ids,
                         room_base_name=room_base_name, room_base_id=room_base_id)

    return {"config_id": config_id, "qr_code": qr_code_url}


def update_group_b_join_way(config_id, chat_ids, auto_create_room=True, room_base_name="", room_base_id=1):
    """更新"加入客户群"二维码配置（群满时追加新群）

    API: externalcontact/groupchat/update_join_way
    """
    token = get_wecom_access_token()
    if not token:
        return False
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/groupchat/update_join_way?access_token={token}"
    payload = {
        "config_id": config_id,
        "scene": 2,
        "chat_id_list": chat_ids,
        "auto_create_room": 1 if auto_create_room else 0,
    }
    if room_base_name:
        payload["room_base_name"] = room_base_name
    if room_base_id:
        payload["room_base_id"] = room_base_id

    resp = requests.post(url, json=payload).json()
    print(f"[JOIN-WAY] update: config_id={config_id}, chat_ids={chat_ids}, resp={resp}")
    if resp.get("errcode") == 0:
        update_group_b_live_qr_chat_ids(config_id, chat_ids)
        return True
    return False


def get_group_b_join_way(config_id):
    """获取"加入客户群"二维码详情

    API: externalcontact/groupchat/get_join_way
    """
    token = get_wecom_access_token()
    if not token:
        return None
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/groupchat/get_join_way?access_token={token}"
    payload = {"config_id": config_id}
    resp = requests.post(url, json=payload).json()
    return resp


# ================= 获取/确保群B活码 =================

def ensure_group_b_live_qr(hospital):
    """获取某医院的群B活码URL，如果没有则创建

    返回活码URL字符串，失败返回 None
    """
    # 获取医院的 room_base 配置
    hospital_info = get_hospital_by_name(hospital)
    room_base_name = hospital_info.get("room_base_name", f"{hospital}患者交流") if hospital_info else f"{hospital}患者交流"
    room_base_id = hospital_info.get("room_base_id", 1) if hospital_info else 1

    # 1. 查已有活码
    live_qr = get_group_b_live_qr(hospital)
    if live_qr and live_qr['qr_code_url']:
        # 检查群是否都满了
        chat_ids = live_qr['chat_ids']
        all_full = True
        for cid in chat_ids:
            real_count = refresh_group_b_member_count(cid)
            if real_count is None:
                all_full = False  # API失败，保守假设未满
                break
            if real_count < 200:
                all_full = False
                break

        if all_full and chat_ids:
            # 所有群都满了，查找是否有新群可以加入活码
            available = get_group_b_available(hospital)
            if available and available[0] not in chat_ids:
                new_chat_ids = chat_ids + [available[0]]
                update_group_b_join_way(live_qr['config_id'], new_chat_ids,
                                       room_base_name=room_base_name, room_base_id=room_base_id)
            # auto_create_room=1 时企微会自动创建新群

        return live_qr['qr_code_url']

    # 2. 没有活码，查找群B并创建
    group_b_rows = get_group_b_by_hospital(hospital)
    if not group_b_rows:
        return None  # 没有群B

    chat_ids = [row[0] for row in group_b_rows]
    result = create_group_b_join_way(hospital, chat_ids,
                                      room_base_name=room_base_name, room_base_id=room_base_id)
    if result:
        return result.get("qr_code")
    return None


# ================= 注册新群+生成活码（H5调用）=================

def register_group_and_create_qr(hospital, chat_id):
    """注册新创建的群并生成活码

    H5页面通过 openEnterpriseChat 建群成功后调用。
    1. 从企微API获取群详情（成员数、群名）
    2. 保存到 group_b 表
    3. 如果医院已有活码，追加 chat_id 并更新
    4. 如果没有活码，创建新活码（auto_create_room=1 + room_base_*）
    5. 返回活码URL

    Returns {"qr_code": "...", "config_id": "..."} or None
    """
    # 1. 获取群详情
    detail = get_customer_group_chat(chat_id)
    chat_name = ""
    member_count = 1
    if detail.get("errcode") == 0:
        group_chat = detail.get("group_chat", {})
        chat_name = group_chat.get("name", "")
        member_count = len(group_chat.get("member_list", []))
    else:
        print(f"[REGISTER] get group detail failed: {detail}")
        chat_name = f"{hospital}患者交流群"
        member_count = 1

    # 2. 保存到 group_b
    save_group_b(chat_id, hospital, chat_name=chat_name, member_count=member_count)
    print(f"[REGISTER] 保存群B: {chat_name} -> {chat_id}, 人数={member_count}")

    # 3. 确保医院在 hospitals 表中
    hospital_info = get_hospital_by_name(hospital)
    if not hospital_info:
        room_base_name = f"{hospital}患者交流"
        room_base_id = 1
        save_hospital(hospital, room_base_name=room_base_name, room_base_id=room_base_id)
    else:
        room_base_name = hospital_info.get("room_base_name", f"{hospital}患者交流")
        room_base_id = hospital_info.get("room_base_id", 1)

    # 4. 检查是否已有活码
    live_qr = get_group_b_live_qr(hospital)
    if live_qr:
        # 已有活码，追加 chat_id
        if chat_id not in live_qr['chat_ids']:
            new_chat_ids = live_qr['chat_ids'] + [chat_id]
            success = update_group_b_join_way(
                live_qr['config_id'], new_chat_ids,
                auto_create_room=True,
                room_base_name=room_base_name,
                room_base_id=room_base_id
            )
            if success:
                # 重新获取更新后的 qr_code
                get_resp = get_group_b_join_way(live_qr['config_id'])
                if get_resp and get_resp.get("errcode") == 0:
                    qr_code = get_resp.get("join_way", {}).get("qr_code", "")
                    if qr_code:
                        conn = sqlite3.connect('wecom_cache.db')
                        cursor = conn.cursor()
                        cursor.execute("UPDATE group_b_live_qr SET qr_code_url = ?, updated_at = datetime('now') WHERE config_id = ?",
                                       (qr_code, live_qr['config_id']))
                        conn.commit()
                        conn.close()
                        return {"qr_code": qr_code, "config_id": live_qr['config_id']}

            return {"qr_code": live_qr['qr_code_url'], "config_id": live_qr['config_id']}
        else:
            # chat_id 已在列表中
            return {"qr_code": live_qr['qr_code_url'], "config_id": live_qr['config_id']}

    # 5. 没有活码，创建新的
    result = create_group_b_join_way(
        hospital, [chat_id],
        auto_create_room=True,
        room_base_name=room_base_name,
        room_base_id=room_base_id
    )
    if result:
        return result
    return None


# ================= 自动发现客户群 =================

def discover_and_register_groups():
    """扫描企微客户群，自动注册到 group_b 表

    命名规则：群名包含"患者交流" → 归入 group_b，群名中"患者交流"前的部分作为医院名
    """
    token = get_wecom_access_token()
    if not token:
        return

    offset = 0
    while True:
        resp = list_customer_group_chats(offset=offset, limit=100)
        if resp.get("errcode") != 0:
            break
        group_list = resp.get("group_chat_list", [])
        if not group_list:
            break

        for g in group_list:
            chat_id = g.get("chat_id", "")
            chat_name = g.get("chat_name", "")

            if "患者交流" in chat_name:
                hospital = chat_name.split("患者交流")[0]
                conn = sqlite3.connect('wecom_cache.db')
                cursor = conn.cursor()
                try:
                    cursor.execute("SELECT chat_id FROM group_b WHERE chat_id = ?", (chat_id,))
                    if not cursor.fetchone():
                        detail = get_customer_group_chat(chat_id)
                        member_count = len(detail.get("group_chat", {}).get("member_list", [])) if detail.get("errcode") == 0 else 1
                        save_group_b(chat_id, hospital, chat_name=chat_name, member_count=member_count)
                        print(f"[DISCOVER] 注册群B: {chat_name} -> {chat_id}, 人数={member_count}")

                        # 确保医院在 hospitals 表中
                        hospital_info = get_hospital_by_name(hospital)
                        if not hospital_info:
                            save_hospital(hospital)

                        live_qr = get_group_b_live_qr(hospital)
                        if live_qr and chat_id not in live_qr['chat_ids']:
                            new_chat_ids = live_qr['chat_ids'] + [chat_id]
                            room_base_name = hospital_info.get("room_base_name", "") if hospital_info else ""
                            room_base_id = hospital_info.get("room_base_id", 1) if hospital_info else 1
                            update_group_b_join_way(live_qr['config_id'], new_chat_ids,
                                                    room_base_name=room_base_name, room_base_id=room_base_id)
                finally:
                    conn.close()

        offset += len(group_list)
        if len(group_list) < 100:
            break
