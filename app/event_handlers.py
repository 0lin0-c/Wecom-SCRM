# -*- coding: utf-8 -*-
"""
事件处理：handle_add_external_contact、handle_external_contact_msg
v5更新：加企微时自动发专属客服链接（替代原来的欢迎语+收手机尾号）
"""
from app.config import KF_OPEN_KFID
from app.wechat_api import send_welcome_message, sync_employee_customers
from app.wechat_kf_api import kf_get_account_link
from app.database import (
    create_reception_progress, update_phone_received,
    save_scene_mapping
)


def handle_add_external_contact(msg_dict):
    employee_userid = msg_dict.get('UserID')
    external_userid = msg_dict.get('ExternalUserID')
    welcome_code = msg_dict.get('WelcomeCode')
    state = msg_dict.get('State', '')

    print(f"[EVENT] add contact: employee={employee_userid}, external={external_userid}, state={state}")

    # 加好友时同步客户列表，确保新客户写入 customers 表
    sync_employee_customers(employee_userid)

    if welcome_code:
        # 生成专属客服链接：将 external_userid 存入 scene_mapping，用返回的 ID 作为 scene
        scene_id = save_scene_mapping(external_userid)
        scene = f"{employee_userid}_{scene_id}"

        kf_link = ""
        if KF_OPEN_KFID:
            link_resp = kf_get_account_link(KF_OPEN_KFID, scene=scene)
            if link_resp.get("errcode") == 0:
                kf_link = link_resp.get("url", "")
                print(f"[EVENT] 生成专属客服链接: scene={scene}, url={kf_link}")
            else:
                print(f"[EVENT] 生成客服链接失败: {link_resp}")

        if kf_link:
            welcome_msg = (
                f"您好！我是您的专属营养顾问助手。\n\n"
                f"请点击下方链接，进入客服会话，我们将为您提供一对一服务：\n"
                f"{kf_link}"
            )
        else:
            # 降级：没有客服链接时用原来的欢迎语
            welcome_msg = (
                "您好！我是您的专属营养顾问助手\n\n"
                "为了更好地为您提供服务，请回复您的【手机尾号后4位】，我将为您匹配专属营养方案。"
            )

        result = send_welcome_message(welcome_code, welcome_msg)
        if result.get("errcode") == 0:
            print(f"[SUCCESS] welcome message sent with KF link")
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
