# -*- coding: utf-8 -*-
"""
AI 对话：chat_with_ai_and_execute()、chat_with_kf_ai()
v5修改：员工对话新增群B管理工具（创建群B、发通知、查看群列表）
千院千群新增：add_hospital 工具、更新 create_group_b 引导至H5侧边栏
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
    """获取微信客服链接"""
    scene = employee_userid

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


# ================= 员工群B管理工具 =================

def _tool_add_hospital(args):
    """tool: 添加医院到系统"""
    hospital = args.get("hospital", "")
    if not hospital:
        return "请指定医院名称"

    from app.database import save_hospital, get_hospital_by_name
    existing = get_hospital_by_name(hospital)
    if existing:
        return f"{hospital} 已存在，无需重复添加。群名前缀：{existing.get('room_base_name', '')}"

    room_base_name = f"{hospital}患者交流"
    save_hospital(hospital, room_base_name=room_base_name, room_base_id=1)
    return f"已添加医院「{hospital}」，群名前缀：{room_base_name}。员工可在侧边栏「一键建群」工具中看到该医院。"


def _tool_create_group_b(employee_userid, args):
    """tool: 为医院创建群B"""
    hospital = args.get("hospital", "")
    if not hospital:
        return "请指定医院名称"

    from app.group_b_api import discover_and_register_groups, ensure_group_b_live_qr
    from app.database import get_group_b_by_hospital, save_hospital
    from app.config import H5_BASE_URL

    # 确保医院在 hospitals 表中
    save_hospital(hospital)

    # 先尝试发现已有的群
    discover_and_register_groups()

    existing = get_group_b_by_hospital(hospital)
    if existing:
        group_names = [row[2] for row in existing]
        qr_url = ensure_group_b_live_qr(hospital)
        qr_info = f"\n\n入群活码：{qr_url}" if qr_url else "\n\n活码生成中，请稍后再试。"
        return f"{hospital} 已有群B：{', '.join(group_names)}。{qr_info}"

    # 没有群，引导员工使用H5侧边栏
    return f"""{hospital} 暂无患者交流群，请通过以下方式创建：

1. 在企微聊天侧边栏打开「一键建群」工具
2. 选择 {hospital}，点击一键建群

创建完成后系统会自动生成入群活码，群满200人自动创建新群。"""


def _tool_list_groups(args):
    """tool: 列出群"""
    group_type = args.get("group_type", "")
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    result_lines = []

    if not group_type or group_type == "group_b":
        cursor.execute("SELECT chat_id, hospital, chat_name, member_count, status FROM group_b ORDER BY created_at DESC LIMIT 20")
        rows = cursor.fetchall()
        if rows:
            result_lines.append("【群B - 医院大群】")
            for row in rows:
                result_lines.append(f"  {row[2]} (chat_id: {row[0]}, 医院: {row[1]}, 人数: {row[3]}/200, 状态: {row[4]})")

    conn.close()
    return "\n".join(result_lines) if result_lines else "暂无群数据"


def _tool_send_group_b_announcement(employee_userid, args):
    """tool: 在群B发送公共通知"""
    hospital = args.get("hospital", "")
    content = args.get("content", "")

    from app.database import get_group_b_by_hospital
    group_b_rows = get_group_b_by_hospital(hospital)
    if not group_b_rows:
        return f"未找到 {hospital} 的群B，请先创建"

    # 客户群需要通过群机器人webhook或appchat发送
    # 这里先通过企微应用消息通知员工手动发
    send_wecom_message(employee_userid,
                       f"请在 {hospital} 患者交流群中发送以下通知：\n\n【通知】{content}")
    return f"已提醒在 {hospital} 交流群中发送通知"


def _tool_get_group_b_qr(employee_userid, args):
    """tool: 获取某医院的群B活码"""
    hospital = args.get("hospital", "")
    if not hospital:
        return "请指定医院名称"

    from app.group_b_api import ensure_group_b_live_qr
    qr_url = ensure_group_b_live_qr(hospital)
    if qr_url:
        return f"{hospital} 病友交流群活码：{qr_url}\n\n患者扫描此二维码即可加入群聊。"
    else:
        return f"{hospital} 暂无群B，请先通过侧边栏「一键建群」创建客户群。"


def chat_with_ai_and_execute(employee_userid, user_message):
    """面向员工的LLM对话（自建应用场景），支持tool calling

    v5新增工具：create_group_b, list_groups, send_group_b_announcement, get_group_b_qr
    千院千群新增工具：add_hospital
    """
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
                "description": "获取微信客服链接，当员工需要客服链接、客服二维码、让患者联系客服、患者入口等场景时调用",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_name": {"type": "string", "description": "可选，指定客户姓名以生成专属链接"}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "add_hospital",
                "description": "添加医院到系统，当员工需要新增医院、添加新医院、配置新医院时调用",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "hospital": {"type": "string", "description": "医院名称"}
                    },
                    "required": ["hospital"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_group_b",
                "description": "为指定医院创建或查找患者交流大群（群B），当员工要求创建医院群、病友群、交流群时调用",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "hospital": {"type": "string", "description": "医院名称"}
                    },
                    "required": ["hospital"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_groups",
                "description": "查看当前群列表",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "group_type": {"type": "string", "description": "群类型：group_b(医院大群)，不填则全部"}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "send_group_b_announcement",
                "description": "在医院患者交流群（群B）中发送公共通知",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "hospital": {"type": "string", "description": "医院名称"},
                        "content": {"type": "string", "description": "通知内容"}
                    },
                    "required": ["hospital", "content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_group_b_qr",
                "description": "获取某医院的患者交流群活码二维码链接，当员工需要群二维码、入群链接时调用",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "hospital": {"type": "string", "description": "医院名称"}
                    },
                    "required": ["hospital"]
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
            args = json.loads(tool_call["function"]["arguments"])

            if fn_name == "modify_customer_remark":
                result_str = modify_customer_remark(employee_userid, args["customer_name"], args["new_remark"])
                send_wecom_message(employee_userid, f"result: {result_str}")
            elif fn_name == "get_kf_link":
                customer_name = args.get("customer_name")
                result_str = _get_kf_link(employee_userid, customer_name)
                send_wecom_message(employee_userid, result_str)
            elif fn_name == "add_hospital":
                result_str = _tool_add_hospital(args)
                send_wecom_message(employee_userid, result_str)
            elif fn_name == "create_group_b":
                result_str = _tool_create_group_b(employee_userid, args)
                send_wecom_message(employee_userid, result_str)
            elif fn_name == "list_groups":
                result_str = _tool_list_groups(args)
                send_wecom_message(employee_userid, result_str)
            elif fn_name == "send_group_b_announcement":
                result_str = _tool_send_group_b_announcement(employee_userid, args)
                send_wecom_message(employee_userid, result_str)
            elif fn_name == "get_group_b_qr":
                result_str = _tool_get_group_b_qr(employee_userid, args)
                send_wecom_message(employee_userid, result_str)
    else:
        final_reply = message_obj.get("content", "I don't understand.")
        send_wecom_message(employee_userid, final_reply)


def chat_with_kf_ai(external_userid, user_message, open_kfid):
    """面向客户的LLM对话（微信客服场景），带历史记录和患者上下文"""
    try:
        save_chat_history(external_userid, open_kfid, 'user', user_message)

        rows = get_chat_history(external_userid, open_kfid, limit=20)

        system_prompt = KF_SYSTEM_PROMPT_BASE
        patient_ctx = get_patient_context_for_prompt(external_userid)
        if patient_ctx:
            system_prompt += f"""

【当前客户已匹配信息】
- 患者姓名：{patient_ctx['patient_name']}
- 医院：{patient_ctx['hospital']}
- 方案类型：{'电子方案（营养师可直接查看）' if patient_ctx['plan_type'] == 'electronic' else '纸质方案（已请求上传照片）'}

注意：该客户已提供手机尾号并匹配成功，不要再询问手机尾号。如客户有其他问题请正常回答。"""

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

        save_chat_history(external_userid, open_kfid, 'assistant', reply)

        result = kf_send_msg(external_userid, open_kfid, reply)
        print(f"[KF AI] reply to {external_userid}: {reply[:50]}... result={result.get('errcode')}")

    except Exception as e:
        print(f"[KF AI] error: {e}")
