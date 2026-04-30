import json
import requests
import sqlite3
import xmltodict
from fastapi import FastAPI, Query, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse
from wechatpy.enterprise.crypto import WeChatCrypto
from wechatpy.exceptions import InvalidSignatureException

app = FastAPI()

# ================= 1. 基础配置区 (请替换为你自己的真实数据) =================
WECOM_CORP_ID = "ww893ef078a0935650"
WECOM_SECRET = "NwTTbs4A7iaFa36SuyznKvDPNdsUb1jQsII-DUn_HX0"
WECOM_AGENT_ID = 1000035  # 你的自建应用 AgentId (纯数字)
WECOM_TOKEN = "8gc2MSGpYpPhneNcjFaz"
WECOM_AES_KEY = "XuaKFNct2eiZrxw8j85IoK4EwuuENayWc549ZRtKDwp"

OPENAI_API_KEY = "sk-sp-iP9d7tGzkcMhgjkDVhhZ7XIhhZuTfZEGORVw0TlltsALWQq7"
OPENAI_BASE_URL = "https://api.lkeap.cloud.tencent.com/coding/v3/chat/completions" # 假设OpenClaw兼容OpenAI接口格式
MODEL_NAME = "glm-5" # 已修正模型名

crypto = WeChatCrypto(WECOM_TOKEN, WECOM_AES_KEY, WECOM_CORP_ID)

# ================= 2. 数据库与本地缓存层 =================

def init_db():
    """初始化 SQLite 数据库，用于缓存客户姓名与 ID 的映射"""
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
    conn.commit()
    conn.close()

# 启动服务时初始化表结构
init_db()

# ================= 3. 企业微信 API 工具 =================

def get_wecom_access_token():
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={WECOM_CORP_ID}&corpsecret={WECOM_SECRET}"
    return requests.get(url).json().get("access_token")

def send_wecom_message(to_user: str, content: str):
    token = get_wecom_access_token()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
    requests.post(url, json={
        "touser": to_user, "msgtype": "text", "agentid": WECOM_AGENT_ID,
        "text": {"content": content}
    })

def sync_employee_customers(employee_userid: str) -> str:
    """【新增逻辑】：批量拉取该员工的客户并存入本地数据库"""
    token = get_wecom_access_token()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/batch/get_by_user?access_token={token}"
    
    cursor_str = ""
    total_synced = 0
    conn = sqlite3.connect('wecom_cache.db')
    db_cursor = conn.cursor()
    
    while True:
        resp = requests.post(url, json={"userid_list": [employee_userid], "cursor": cursor_str, "limit": 100}).json()
        if resp.get("errcode") != 0:
            return f"同步失败: {resp.get('errmsg')}"
            
        for item in resp.get("external_contact_list", []):
            contact = item.get("external_contact", {})
            name = contact.get("name")
            eid = contact.get("external_userid")
            
            if name and eid:
                # 插入或更新数据库 (使用 REPLACE 避免主键冲突)
                db_cursor.execute("REPLACE INTO customers (employee_userid, customer_name, external_userid) VALUES (?, ?, ?)", 
                                  (employee_userid, name, eid))
                total_synced += 1
                
        cursor_str = resp.get("next_cursor")
        if not cursor_str:
            break
            
    conn.commit()
    conn.close()
    return f"✅ 同步完成！共拉取并缓存了 {total_synced} 个联系人。"

def modify_customer_remark(employee_userid: str, customer_name: str, new_remark: str) -> str:
    """【改造逻辑】：查本地库拿到真实 ID，再调用企微接口"""
    print(f"-> 正在本地数据库查找 {customer_name} 的 ID...")
    
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    # 根据员工 ID 和客户名查找底层 ID
    cursor.execute("SELECT external_userid FROM customers WHERE employee_userid=? AND customer_name=?", (employee_userid, customer_name))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return f"❌ 在本地缓存中未找到联系人【{customer_name}】。请先发送命令“同步客户数据”来更新缓存。"
        
    target_external_userid = row[0]
    print(f"-> 查库成功：姓名={customer_name}, ID={target_external_userid}")
    
    # 拿着真实 ID 去请求企微修改备注
    token = get_wecom_access_token()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/remark?access_token={token}"
    resp = requests.post(url, json={
        "userid": employee_userid,
        "external_userid": target_external_userid,
        "remark": new_remark
    }).json()
    
    if resp.get("errcode") == 0:
        return f"✅ 系统已成功将【{customer_name}】的备注修改为：{new_remark}"
    else:
        return f"❌ 修改失败，企业微信报错：{resp.get('errmsg')}"

# ================= 4. OpenClaw 核心调度 =================

def chat_with_openclaw_and_execute(employee_userid: str, user_message: str):
    # 特殊指令拦截：如果用户发送了特定口令，触发数据库同步
    if user_message.strip() == "同步客户数据":
        send_wecom_message(employee_userid, "⏳ 正在拉取企微通讯录并构建本地索引，请稍候...")
        result = sync_employee_customers(employee_userid)
        send_wecom_message(employee_userid, result)
        return

    tools = [{
        "type": "function",
        "function": {
            "name": "modify_customer_remark",
            "description": "修改企业微信好友/客户的备注名。提取客户的原名以及新的备注名。",
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
            send_wecom_message(employee_userid, f"🤖 操作汇报：\n{result_str}")
    else:
        final_reply = message_obj.get("content", "我不太明白。")
        send_wecom_message(employee_userid, final_reply)

# ================= 5. FastAPI 路由 =================

@app.get("/wechat/callback")
async def verify_url(msg_signature: str = Query(...), timestamp: str = Query(...), nonce: str = Query(...), echostr: str = Query(...)):
    """处理企微的 URL 验证请求 (保持不变)"""
    try:
        decrypted_echostr = crypto.check_signature(msg_signature, timestamp, nonce, echostr)
        return PlainTextResponse(content=decrypted_echostr)
    except InvalidSignatureException:
        return PlainTextResponse(content="签名验证失败", status_code=403)

@app.post("/wechat/callback")
async def receive_msg(
    request: Request,
    background_tasks: BackgroundTasks, # 引入后台任务管理器
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...)
):
    """处理企微的真实推送消息"""
    raw_body = await request.body()
    try:
        decrypted_xml = crypto.decrypt_message(raw_body, msg_signature, timestamp, nonce)
        msg_dict = xmltodict.parse(decrypted_xml)['xml']
        
        msg_type = msg_dict.get('MsgType')
        sender_id = msg_dict.get('FromUserName') # 发消息的员工企微账号
        
        if msg_type == 'text':
            content = msg_dict.get('Content')
            print(f"[{sender_id}] 说了: {content}")
            
            # 将耗时的“大脑思考”扔到后台去慢慢跑
            background_tasks.add_task(chat_with_openclaw_and_execute, sender_id, content)
            
        # 无论后台跑多久，立刻在一瞬间给企微回复 success，防止超时重试
        return PlainTextResponse(content="success")
        
    except Exception as e:
        print(f"解密或处理报错: {e}")
        return PlainTextResponse(content="success")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8500)