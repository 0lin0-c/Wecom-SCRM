# -*- coding: utf-8 -*-
"""
新企业测试 - 自建应用回调
"""

from fastapi import FastAPI, Query
from fastapi.responses import PlainTextResponse
from wechatpy.enterprise.crypto import WeChatCrypto
from wechatpy.exceptions import InvalidSignatureException

app = FastAPI()

# ========== 新企业配置 ==========
TOKEN = '0wG5odkRURpJZAn3tQJC4Qbb'
AES_KEY = '4ABQ5joZC5cFt2qntCsqU1RCh33cMDReUubxgVU3F3L'
CORP_ID = 'ww5bb595253ba23914'

crypto = WeChatCrypto(TOKEN, AES_KEY, CORP_ID)

# ========== 自建应用回调 ==========

@app.get("/wechat/callback")
async def verify_url(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...)
):
    """验证回调 URL"""
    try:
        decrypted_echostr = crypto.check_signature(msg_signature, timestamp, nonce, echostr)
        print("[OK] URL verification passed")
        return PlainTextResponse(content=decrypted_echostr)
    except InvalidSignatureException:
        print("[FAIL] Signature check failed")
        return PlainTextResponse(content="signature failed", status_code=403)

@app.post("/wechat/callback")
async def receive_msg(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...)
):
    """接收消息（暂时只打印日志）"""
    print(f"[MSG] Received POST request")
    return PlainTextResponse(content="success")

# ========== 客户联系回调 ==========

@app.get("/wechat/contact/callback")
async def contact_verify_url(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...)
):
    """验证客户联系回调 URL"""
    try:
        decrypted_echostr = crypto.check_signature(msg_signature, timestamp, nonce, echostr)
        print("[OK] Contact URL verification passed")
        return PlainTextResponse(content=decrypted_echostr)
    except InvalidSignatureException:
        print("[FAIL] Contact signature check failed")
        return PlainTextResponse(content="signature failed", status_code=403)

@app.post("/wechat/contact/callback")
async def contact_receive_event(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...)
):
    """接收客户联系事件"""
    print(f"[CONTACT EVENT] Received POST request")
    return PlainTextResponse(content="success")

# ========== 启动 ==========

if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("New Enterprise Test Server")
    print("=" * 50)
    print(f"App callback: http://111.229.157.67:8500/wechat/callback")
    print(f"Contact callback: http://111.229.157.67:8500/wechat/contact/callback")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8500)
