from fastapi import FastAPI, Query
from fastapi.responses import PlainTextResponse
from wechatpy.enterprise.crypto import WeChatCrypto
from wechatpy.exceptions import InvalidSignatureException

app = FastAPI()

# 替换为你刚才在企微后台生成的三个参数
TOKEN = '8gc2MSGpYpPhneNcjFaz'
AES_KEY = 'XuaKFNct2eiZrxw8j85IoK4EwuuENayWc549ZRtKDwp'
CORP_ID = 'ww893ef078a0935650' # 在企微后台“我的企业”最底部查看

# 初始化企微加解密工具
crypto = WeChatCrypto(TOKEN, AES_KEY, CORP_ID)

@app.get("/wechat/callback")
async def verify_url(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...)
):
    try:
        # 解密企微发来的 echostr
        decrypted_echostr = crypto.check_signature(
            msg_signature,
            timestamp,
            nonce,
            echostr
        )
        # 必须以纯文本(PlainText)的形式返回解密后的明文
        return PlainTextResponse(content=decrypted_echostr)
    except InvalidSignatureException:
        return PlainTextResponse(content="签名验证失败", status_code=403)

if __name__ == "__main__":
    # 在 8500 端口启动服务
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8500)