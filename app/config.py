# -*- coding: utf-8 -*-
"""
配置区：从 .env 读取所有配置 + 常量
"""
import os
from wechatpy.enterprise.crypto import WeChatCrypto

# ================= 企业微信基础配置 =================
WECOM_CORP_ID = os.getenv("WECOM_CORP_ID", "")
WECOM_SECRET = os.getenv("WECOM_SECRET", "")
WECOM_AGENT_ID = int(os.getenv("WECOM_AGENT_ID", "0"))

# ================= 自建应用回调配置 =================
APP_TOKEN = os.getenv("APP_TOKEN", "")
APP_AES_KEY = os.getenv("APP_AES_KEY", "")

# ================= 客户联系回调配置 =================
CONTACT_TOKEN = os.getenv("CONTACT_TOKEN", "")
CONTACT_AES_KEY = os.getenv("CONTACT_AES_KEY", "")

# ================= AI 配置 =================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
MODEL_NAME = os.getenv("MODEL_NAME", "glm-5")

# ================= 多模态AI配置（图片识别）=================
MLLM_API_KEY = os.getenv("MLLM_API_KEY", "")
MLLM_BASE_URL = os.getenv("MLLM_BASE_URL", "")
MLLM_MODEL_NAME = os.getenv("MLLM_MODEL_NAME", "GLM-4.5V")

# ================= 微信客服(KF)配置 =================
KF_OPEN_KFID = os.getenv("KF_OPEN_KFID", "")

# ================= 员工配置 =================
DEFAULT_EMPLOYEE_USERID = os.getenv("DEFAULT_EMPLOYEE_USERID", "CaoHuiLin")
SECOND_EMPLOYEE_USERID = os.getenv("SECOND_EMPLOYEE_USERID", "Mo")

# ================= 千院千群配置 =================
TOOL_PERSON_EXTERNAL_USERID = os.getenv("TOOL_PERSON_EXTERNAL_USERID", "")
H5_BASE_URL = os.getenv("H5_BASE_URL", "")

# ================= 加密器 =================
app_crypto = WeChatCrypto(APP_TOKEN, APP_AES_KEY, WECOM_CORP_ID)
contact_crypto = WeChatCrypto(CONTACT_TOKEN, CONTACT_AES_KEY, WECOM_CORP_ID)

# ================= 文件上传目录 =================
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ================= 欢迎语模板 =================
WELCOME_MESSAGE = """您好！我是您的专属营养顾问助手

请点击下方链接，进入客服会话，我们将为您提供一对一服务。"""

KF_WELCOME_MESSAGE = """您好！我是您的专属营养顾问助手

为了更好地为您提供服务，请先回复您的【手机尾号后4位】，然后再回复您的【姓名】，我们将为您匹配专属营养方案。"""

# ================= AI 系统提示词 =================
KF_SYSTEM_PROMPT_BASE = """你是一位专业、友好的企业微信客服助手，专注于营养健康领域。你的工作流程：

1. 客户首次进入时，你需要询问他们的手机尾号后4位来匹配服务方案
2. 如果客户回复了4位数字（手机尾号），确认收到
3. 之后根据客户的问题，提供专业的营养健康建议
4. 回复简洁明了，避免过长

注意：
- 如果客户发了4位纯数字，那就是手机尾号，请确认收到
- 如果客户问其他问题，正常回答即可
- 如果无法回答，礼貌告知会转接人工客服
请用中文回复。"""
