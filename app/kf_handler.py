# -*- coding: utf-8 -*-
"""
KF 消息处理：process_kf_notification()
"""
import sqlite3
from app.config import KF_WELCOME_MESSAGE
from app.wechat_kf_api import (
    kf_sync_msg, kf_send_msg, kf_send_msg_on_event,
    kf_get_service_state, kf_trans_service_state,
    resolve_kf_open_kfid
)
from app.database import (
    save_kf_cursor, get_kf_cursor,
    update_kf_conversation, update_kf_service_state,
    update_kf_phone_tail, update_kf_patient_name,
    match_patient, insert_reception_on_kf_enter,
    insert_reception_on_phone_tail, get_scene_mapping,
    get_reception_progress_by_external
)
from app.patient_service import handle_patient_matched, handle_paper_plan_image
from app.ai_chat import chat_with_kf_ai


def process_kf_notification(callback_token, open_kfid):
    """处理微信客服通知：拉取消息并处理"""
    print(f"[KF] 收到通知, open_kfid={open_kfid}, token={'有' if callback_token else '无'}")

    cursor = get_kf_cursor(open_kfid)
    print(f"[KF] 上次cursor: {cursor or '无'}")

    resp = kf_sync_msg(open_kfid, callback_token, cursor)
    print(f"[KF] sync_msg结果: errcode={resp.get('errcode')}, msg_count={len(resp.get('msg_list', []))}")

    if resp.get("errcode") != 0:
        print(f"[KF] sync_msg failed: {resp}")
        return

    msg_list = resp.get("msg_list", [])
    next_cursor = resp.get("next_cursor", "")
    has_more = resp.get("has_more", 0)

    if not msg_list and not has_more:
        print(f"[KF] 无新消息")
        return

    for msg in msg_list:
        origin = msg.get("origin", 0)
        msgtype = msg.get("msgtype", "")
        external_userid = msg.get("external_userid", "")
        msg_open_kfid = msg.get("open_kfid", open_kfid)

        print(f"[KF MSG] origin={origin}, msgtype={msgtype}, user={external_userid}")

        if origin == 3:
            _handle_customer_message(msg, msgtype, external_userid, msg_open_kfid)

        elif origin == 4:
            _handle_kf_event(msg, msg_open_kfid)

        elif origin == 5:
            pass

    # 保存游标
    if next_cursor:
        save_kf_cursor(open_kfid, next_cursor)

    # 如果还有更多消息，继续拉取
    if has_more:
        print(f"[KF] 还有更多消息，继续拉取...")
        process_kf_notification(callback_token, open_kfid)


def _handle_customer_message(msg, msgtype, external_userid, msg_open_kfid):
    """处理客户发送的消息 (origin==3)

    收集流程：
    1. 患者先发手机尾号(4位数字) → 保存，询问姓名
    2. 患者再发姓名 → 用尾号+姓名匹配患者库
    3. 匹配成功 → 走 handle_patient_matched
    4. 匹配失败 → 提示信息不匹配
    """
    update_kf_conversation(external_userid, msg_open_kfid, is_customer_msg=True)

    # 确保会话状态为"由智能助手接待"(1)
    state_resp = kf_get_service_state(msg_open_kfid, external_userid)
    if state_resp.get("errcode") == 0:
        current_state = state_resp.get("service_state", 0)
        if current_state == 0:
            kf_trans_service_state(msg_open_kfid, external_userid, 1)

    if msgtype == "text":
        content = msg.get("text", {}).get("content", "").strip()
        print(f"[KF] 客户消息: {content}")

        # 获取当前会话中已收集的信息
        conv = get_kf_conversation_row(external_userid, msg_open_kfid)
        existing_phone_tail = conv.get("phone_tail", "") if conv else ""
        existing_patient_name = conv.get("patient_name", "") if conv else ""

        # 检查是否已匹配过患者（已匹配则走AI）
        if _already_matched(external_userid):
            chat_with_kf_ai(external_userid, content, msg_open_kfid)
            return

        # 步骤1：收到4位纯数字 → 记录为手机尾号
        if content.isdigit() and len(content) == 4:
            if not existing_phone_tail:
                update_kf_phone_tail(external_userid, msg_open_kfid, content)
                print(f"[KF] 收到手机尾号: {content}, 询问姓名")
                kf_send_msg(external_userid, msg_open_kfid,
                            f"已收到您的手机尾号 {content}，请再告诉我您的姓名，以便核实身份。")
                return
            else:
                # 已有尾号，又发了一个4位数（可能是输错了想重输）
                update_kf_phone_tail(external_userid, msg_open_kfid, content)
                existing_phone_tail = content

        # 步骤2：已有尾号，收到姓名 → 尝试匹配
        if existing_phone_tail and not existing_patient_name:
            # 把非4位数字的消息当作姓名
            update_kf_patient_name(external_userid, msg_open_kfid, content)
            existing_patient_name = content
            print(f"[KF] 收到姓名: {content}, 尝试匹配 尾号={existing_phone_tail}+姓名={content}")

            patient_info = match_patient(existing_phone_tail, existing_patient_name)
            insert_reception_on_phone_tail(external_userid, existing_phone_tail, patient_info)

            if patient_info:
                handle_patient_matched(external_userid, patient_info, msg_open_kfid)
            else:
                # 尾号+姓名不匹配，尝试仅用尾号匹配看看
                patient_by_tail = match_patient(existing_phone_tail)
                if patient_by_tail:
                    kf_send_msg(external_userid, msg_open_kfid,
                                f"您输入的姓名与手机尾号 {existing_phone_tail} 对应的记录不一致，请确认姓名是否正确。\n"
                                f"如需重新输入，请直接发送正确的姓名。")
                else:
                    kf_send_msg(external_userid, msg_open_kfid,
                                "抱歉，未找到与您提供的信息匹配的记录，请确认手机尾号和姓名是否正确，或联系人工客服。")
            return

        # 步骤3：已有尾号+姓名，但之前匹配失败，收到新姓名 → 重新匹配
        if existing_phone_tail and existing_patient_name:
            if not content.isdigit():
                # 更新姓名并重新匹配
                update_kf_patient_name(external_userid, msg_open_kfid, content)
                print(f"[KF] 更新姓名: {content}, 重新匹配 尾号={existing_phone_tail}")
                patient_info = match_patient(existing_phone_tail, content)
                insert_reception_on_phone_tail(external_userid, existing_phone_tail, patient_info)

                if patient_info:
                    handle_patient_matched(external_userid, patient_info, msg_open_kfid)
                else:
                    kf_send_msg(external_userid, msg_open_kfid,
                                "抱歉，仍然未找到匹配的记录，请联系人工客服获取帮助。")
                return

        # 无尾号时发来的非数字消息 → 走AI回复
        chat_with_kf_ai(external_userid, content, msg_open_kfid)

    elif msgtype == "image":
        image_info = msg.get("image", {})
        media_id = image_info.get("media_id", "")
        print(f"[KF] 收到图片: media_id={media_id}")

        # 检查是否需要存档纸质方案
        handled = handle_paper_plan_image(external_userid, media_id, msg_open_kfid)
        if not handled:
            # 不需要纸质方案或未匹配，仍由AI处理
            chat_with_kf_ai(external_userid, "[发送了一张图片]", msg_open_kfid)

    else:
        kf_send_msg(external_userid, msg_open_kfid,
                    "抱歉，目前仅支持文字和图片消息，请用文字描述您的问题。")


def _handle_kf_event(msg, msg_open_kfid):
    """处理KF系统事件 (origin==4)"""
    event = msg.get("event", {})
    event_type = event.get("event_type", "")

    if event_type == "enter_session":
        welcome_code = event.get("welcome_code", "")
        ext_userid = event.get("external_userid", "")
        scene = event.get("scene", "")
        print(f"[KF] 用户进入会话: {ext_userid}, welcome_code={'有' if welcome_code else '无'}, scene={scene}")

        # 从 scene 提取 wob ID
        contact_ext_id = ""
        if scene and "_" in scene:
            parts = scene.rsplit("_", 1)
            try:
                mapping_id = int(parts[1])
                contact_ext_id = get_scene_mapping(mapping_id)
                print(f"[KF] 从 scene 提取映射ID={mapping_id}, contact_external_userid={contact_ext_id}")
            except ValueError:
                pass

        # 先将会话转为智能助手接待
        trans_resp = kf_trans_service_state(msg_open_kfid, ext_userid, 1)
        if trans_resp.get("errcode") != 0:
            print(f"[KF] 转智能助手失败: {trans_resp}")

        # 发送欢迎语
        if welcome_code:
            result = kf_send_msg_on_event(welcome_code, KF_WELCOME_MESSAGE)
            print(f"[KF] 欢迎语发送结果(event): {result}")

        # 初始化会话记录
        update_kf_conversation(ext_userid, msg_open_kfid, is_customer_msg=False)

        # 记录首次询问时间和 contact_external_userid
        insert_reception_on_kf_enter(ext_userid, contact_ext_id)

    elif event_type == "session_status_change":
        change_type = event.get("change_type", 0)
        print(f"[KF] 会话状态变更: change_type={change_type}")
        ext_userid = event.get("external_userid", "")
        update_kf_service_state(ext_userid, msg_open_kfid, change_type)

    elif event_type == "msg_send_fail":
        fail_msgid = event.get("fail_msgid", "")
        fail_type = event.get("fail_type", 0)
        print(f"[KF] 消息发送失败: msgid={fail_msgid}, fail_type={fail_type}")

    else:
        print(f"[KF] 未知事件: {event_type}")


def get_kf_conversation_row(external_userid, open_kfid):
    """获取会话完整信息（含phone_tail, patient_name）"""
    from app.database import get_kf_conversation
    row = get_kf_conversation(external_userid, open_kfid)
    if not row:
        return None
    # row = (last_customer_msg_time, reply_count, phone_tail, patient_name)
    return {
        "last_customer_msg_time": row[0],
        "reply_count": row[1],
        "phone_tail": row[2] if len(row) > 2 else "",
        "patient_name": row[3] if len(row) > 3 else ""
    }


def _already_matched(external_userid):
    """检查该患者是否已匹配成功（有接待进度且已匹配）"""
    from app.database import get_reception_progress_by_external
    progress = get_reception_progress_by_external(external_userid)
    if progress and progress.get("phone_tail"):
        return True
    return False
