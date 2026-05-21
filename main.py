# -*- coding: utf-8 -*-
"""
企业微信自动接待系统 v5 - 入口文件
启动方式：python main.py

与 v4 的区别：
- 保留微信客服(KF)进行一对一接待（手机尾号、方案存档等）
- 新增群B（医院患者交流大群）功能：
  - 患者建档完成后，自动发送群B活码（add_join_way scene=2）
  - 群满200人时自动创建新群并更新活码
  - 员工可通过AI工具管理群B
  - 自动发现已有客户群并注册
"""
from app import app
from app.scheduler import setup_scheduler
import uvicorn
import os

if __name__ == "__main__":
    # 启动定时任务
    setup_scheduler()

    # 启动时自动发现已有客户群
    try:
        from app.group_b_api import discover_and_register_groups
        discover_and_register_groups()
    except Exception as e:
        print(f"[STARTUP] 群自动发现失败（可能access_token未配置）: {e}")

    host_ip = os.getenv("SERVER_IP", "111.229.157.67")

    print("=" * 60)
    print("WeChat Work Auto Reception v5 (KF + 群B活码版)")
    print("=" * 60)
    print(f"App callback:     http://{host_ip}:8500/wechat/callback")
    print(f"Contact callback: http://{host_ip}:8500/wechat/contact/callback")
    print("=" * 60)
    from app.config import KF_OPEN_KFID, TOOL_PERSON_EXTERNAL_USERID, H5_BASE_URL
    if KF_OPEN_KFID:
        print(f"[KF] 微信客服模块已启用 (open_kfid={KF_OPEN_KFID})")
    else:
        print("[KF] 微信客服模块未配置 (KF_OPEN_KFID 为空)")
    print(f"[SCHEDULER] 每小时跟进检查 + 每天12:00报告")
    print("=" * 60)
    print(f"[v5新增] 群B活码：患者建档后自动发送医院群活码")
    print(f"[v5新增] 群满200人自动创建新群并更新活码 (add_join_way scene=2)")
    print(f"[v5新增] 员工AI工具：创建群B、查看群列表、发通知、获取活码")
    print(f"[v5新增] 自动发现已有客户群并注册")
    print("=" * 60)
    if TOOL_PERSON_EXTERNAL_USERID:
        print(f"[千院千群] 一键建群H5侧边栏已启用")
        print(f"[千院千群] H5页面: {H5_BASE_URL}/static/group_creator.html")
    else:
        print(f"[千院千群] TOOL_PERSON_EXTERNAL_USERID 未配置，一键建群不可用")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8500)
