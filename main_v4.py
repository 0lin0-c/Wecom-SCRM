# -*- coding: utf-8 -*-
"""
企业微信自动接待系统 v4 - 入口文件
启动方式：python main_v4.py
"""
from app import app
from app.scheduler import setup_scheduler
import uvicorn

if __name__ == "__main__":
    # 启动定时任务
    setup_scheduler()

    print("=" * 50)
    print("WeChat Work Auto Reception v4 (患者接待版)")
    print("=" * 50)
    print(f"App callback:     http://111.229.157.67:8500/wechat/callback")
    print(f"Contact callback: http://111.229.157.67:8500/wechat/contact/callback")
    print("=" * 50)
    from app.config import KF_OPEN_KFID
    if KF_OPEN_KFID:
        print(f"[KF] 微信客服模块已启用 (open_kfid={KF_OPEN_KFID})")
    else:
        print("[KF] 微信客服模块未配置 (KF_OPEN_KFID 为空)")
    print(f"[SCHEDULER] 每小时跟进检查 + 每天12:00报告")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8500)
