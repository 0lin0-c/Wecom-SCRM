# -*- coding: utf-8 -*-
"""
AI 对话：chat_with_ai_and_execute()、chat_with_kf_ai()
"""
import json
import sqlite3
import requests
from app.config import (
    OPENAI_API_KEY, OPENAI_BASE_URL, MODEL_NAME,
    KF_SYSTEM_PROMPT_BASE
)
from app.wechat_api import send_wecom_message, sync_employee_customers, modify_customer_remark
from app.wechat_kf_api import kf_send_msg, kf_get_account_link
from app.config import KF_OPEN_KFID
from app.database import (
    save_chat_history, get_chat_history,
    get_patient_context_for_prompt, get_customer_by_name_or_remark,
    save_scene_mapping
)


def _get_kf_link(employee_userid, customer_name=None):
    """获取微信客服链接，scene 嵌入映射 ID 以便自动关联 wob ID
    scene 格式: "员工ID" 或 "员工ID_映射ID"（映射ID 对应 scene_mapping 表中的 wob ID）
    scene 限制 32 字符，所以不能直接放 wob ID
    """
    scene = employee_userid

    # 如果指定了客户名，查找其 external_userid 并存入映射表，scene 放短 ID
    if customer_name:
        cust = get_customer_by_name_or_remark(employee_userid, customer_name)
        if cust and cust[0] and (cust[0].startswith('wob') or cust[0].startswith('wm')):
            mapping_id = save_scene_mapping(cust[0])
            scene = f"{employee_userid}_{mapping_id}"
            print(f"[KF LINK] 为客户 {customer_name} 生成专属链接, scene={scene}, external_userid={cust[0]}")
        else:
            print(f"[KF LINK] 未找到客户 {customer_name} 的 external_userid，生成普通链接")

    result = kf_get_account_link(KF_OPEN_KFID, scene=scene)
    if result.get("errcode") == 0:
        link = result.get("url", "")
        return f"微信客服链接：\n{link}\n\n可将此链接发送给患者，患者点击后即可进入客服会话。"
    else:
        return f"获取客服链接失败：{result.get('errmsg', '未知错误')}"


def chat_with_ai_and_execute(employee_userid, user_message):
    """面向员工的LLM对话（自建应用场景），支持tool calling"""
    if user_message.strip() == "sync data":
        send_wecom_message(employee_userid, "syncing...")
        result = sync_employee_customers(employee_userid)
        send_wecom_message(employee_userid, result)
        return

    tools = [
        {
            "type": "function",
            "function": {
                "name": "modify_customer_remark",
                "description": "修改客户备注名，当员工要求改备注、修改备注时调用",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_name": {"type": "string", "description": "客户姓名或当前备注名"},
                        "new_remark": {"type": "string", "description": "新的备注名"}
                    },
                    "required": ["customer_name", "new_remark"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_kf_link",
                "description": "获取微信客服链接，当员工需要客服链接、客服二维码、让患者联系客服、患者入口等场景时调用。可指定客户姓名生成专属链接，系统会自动关联该客户",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_name": {"type": "string", "description": "可选，指定客户姓名以生成专属链接，实现自动关联"}
                    }
                }
            }
        }
    ]

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
        for tool_call in message_obj["tool_calls"]:
            fn_name = tool_call["function"]["name"]
            if fn_name == "modify_customer_remark":
                args = json.loads(tool_call["function"]["arguments"])
                result_str = modify_customer_remark(employee_userid, args["customer_name"], args["new_remark"])
                send_wecom_message(employee_userid, f"result: {result_str}")
            elif fn_name == "get_kf_link":
                args = json.loads(tool_call["function"]["arguments"])
                customer_name = args.get("customer_name")
                result_str = _get_kf_link(employee_userid, customer_name)
                send_wecom_message(employee_userid, result_str)
    else:
        final_reply = message_obj.get("content", "I don't understand.")
        send_wecom_message(employee_userid, final_reply)


def chat_with_kf_ai(external_userid, user_message, open_kfid):
    """面向客户的LLM对话（微信客服场景），带历史记录和患者上下文"""
    try:
        # 保存用户消息到历史
        save_chat_history(external_userid, open_kfid, 'user', user_message)

        # 读取最近20条历史
        rows = get_chat_history(external_userid, open_kfid, limit=20)

        # 动态构建system prompt
        system_prompt = KF_SYSTEM_PROMPT_BASE
        patient_ctx = get_patient_context_for_prompt(external_userid)
        if patient_ctx:
            system_prompt += f"""

【当前客户已匹配信息】
- 患者姓名：{patient_ctx['patient_name']}
- 医院：{patient_ctx['hospital']}
- 方案类型：{'电子方案（营养师可直接查看）' if patient_ctx['plan_type'] == 'electronic' else '纸质方案（已请求上传照片）'}

注意：该客户已提供手机尾号并匹配成功，不要再询问手机尾号。如客户有其他问题请正常回答。"""

        # 构建消息列表（按时间正序）
        messages = [{"role": "system", "content": system_prompt}]
        for role, content in reversed(rows):
            messages.append({"role": role, "content": content})

        payload = {
            "model": MODEL_NAME,
            "messages": messages
        }

        raw_resp = requests.post(OPENAI_BASE_URL, headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, json=payload)
        resp = raw_resp.json()
        reply = resp["choices"][0]["message"].get("content", "抱歉，我暂时无法回答，请稍后再试。")

        # 保存AI回复到历史
        save_chat_history(external_userid, open_kfid, 'assistant', reply)

        # 发送回复给客户
        result = kf_send_msg(external_userid, open_kfid, reply)
        print(f"[KF AI] reply to {external_userid}: {reply[:50]}... result={result.get('errcode')}")

    except Exception as e:
        print(f"[KF AI] error: {e}")
