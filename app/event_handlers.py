# -*- coding: utf-8 -*-
"""
事件处理：handle_add_external_contact、handle_external_contact_msg
"""
from app.config import WELCOME_MESSAGE
from app.wechat_api import send_welcome_message, sync_employee_customers
from app.database import create_reception_progress, update_phone_received


def handle_add_external_contact(msg_dict):
    employee_userid = msg_dict.get('UserID')
    external_userid = msg_dict.get('ExternalUserID')
    welcome_code = msg_dict.get('WelcomeCode')
    state = msg_dict.get('State', '')

    print(f"[EVENT] add contact: employee={employee_userid}, external={external_userid}, state={state}")

    # 加好友时同步客户列表，确保新客户写入 customers 表
    sync_employee_customers(employee_userid)

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
