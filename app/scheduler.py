# -*- coding: utf-8 -*-
"""
定时任务：跟进检查 + 每日报告 + setup_scheduler()
"""
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from app.config import DEFAULT_EMPLOYEE_USERID
from app.wechat_api import send_wecom_message
from app.wechat_kf_api import kf_send_msg, resolve_kf_open_kfid
from app.patient_service import update_customer_remark_and_desc
from app.database import (
    get_pending_follow_ups, update_follow_up, mark_no_response,
    get_no_response_today, get_customer_remark, get_contact_external_userid
)


def check_and_follow_up():
    """检查未回复的患者并跟进（每小时执行一次）"""
    print("[SCHEDULER] 执行定时跟进检查...")
    now = datetime.now()

    rows = get_pending_follow_ups()
    open_kfid = resolve_kf_open_kfid()
    if not open_kfid:
        print("[SCHEDULER] 无可用KF账号，跳过跟进")
        return

    no_response_list = []

    for row in rows:
        external_userid, employee_userid, first_ask_time, second_ask_time, \
            follow_up_count, patient_name, hospital = row

        first_ask_dt = _parse_datetime(first_ask_time)
        second_ask_dt = _parse_datetime(second_ask_time)

        if follow_up_count == 0 and first_ask_dt:
            # 距首次询问>=24小时，进行第二次跟进
            if (now - first_ask_dt).total_seconds() >= 86400:
                print(f"[SCHEDULER] 24h跟进: {external_userid}")
                result = kf_send_msg(external_userid, open_kfid,
                                     "您好，请问您方便提供手机尾号后4位吗？我们将为您匹配专属营养方案。")
                if result.get("errcode") == 0:
                    update_follow_up(external_userid, 1, second_ask_time=True)
                else:
                    print(f"[SCHEDULER] 24h跟进发送失败: {result}")

        elif follow_up_count == 1 and second_ask_dt:
            # 距第二次询问>=24小时(即距首次48小时)，标记为未回复
            if (now - second_ask_dt).total_seconds() >= 86400:
                print(f"[SCHEDULER] 48h未回复: {external_userid}")
                mark_no_response(external_userid)

                # 修改备注：加"-未回复"
                emp_userid = employee_userid or DEFAULT_EMPLOYEE_USERID
                if patient_name and hospital:
                    remark = f"{hospital}+{patient_name}-未回复"
                else:
                    cust_row = get_customer_remark(external_userid)
                    if cust_row and cust_row[0]:
                        remark = f"{cust_row[0]}-未回复"
                    elif cust_row and cust_row[1]:
                        remark = f"{cust_row[1]}-未回复"
                    else:
                        remark = f"{external_userid}-未回复"

                update_customer_remark_and_desc(emp_userid, get_contact_external_userid(external_userid), remark, "患者未回复手机尾号")
                no_response_list.append(remark)

    # 如果有未回复的患者，立即通知员工
    if no_response_list:
        report = "以下患者2次跟进未回复：\n"
        for i, name in enumerate(no_response_list, 1):
            report += f"{i}. {name}\n"
        send_wecom_message(DEFAULT_EMPLOYEE_USERID, report)
        print(f"[SCHEDULER] 已发送未回复名单: {len(no_response_list)}人")


def daily_report():
    """每天12:00整理当天2次跟进未果的患者名单"""
    print("[SCHEDULER] 执行每日12:00报告...")
    now = datetime.now()

    rows = get_no_response_today()

    if not rows:
        print("[SCHEDULER] 今日无新增未回复患者")
        return

    report = f"【{now.strftime('%Y年%m月%d日')} 未回复患者名单】\n\n"
    for i, row in enumerate(rows, 1):
        external_userid, patient_name, hospital, remark = row
        display_name = remark if remark else (f"{hospital}+{patient_name}" if hospital and patient_name else external_userid)
        report += f"{i}. {display_name}\n"

    report += "\n请营养师人工跟进以上患者。"
    send_wecom_message(DEFAULT_EMPLOYEE_USERID, report)
    print(f"[SCHEDULER] 每日报告已发送: {len(rows)}人")


def setup_scheduler():
    """配置定时任务"""
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_and_follow_up, 'interval', hours=1, id='follow_up_check')
    scheduler.add_job(daily_report, 'cron', hour=12, minute=0, id='daily_report')
    scheduler.start()
    print("[SCHEDULER] 定时任务已启动：每小时跟进检查 + 每天12:00报告")


def _parse_datetime(dt_str):
    """安全解析日期时间字符串"""
    if not dt_str:
        return None
    try:
        return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None
