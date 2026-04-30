# -*- coding: utf-8 -*-
"""
患者业务：匹配、打标签、改备注描述、图片下载存档、图片OCR识别
"""
import os
import base64
import requests
from datetime import datetime
from app.config import UPLOAD_DIR, MLLM_API_KEY, MLLM_BASE_URL, MLLM_MODEL_NAME
from app.wechat_api import get_wecom_access_token
from app.wechat_kf_api import kf_send_msg
from app.database import (
    match_patient, update_reception_patient_info, save_patient_document,
    get_employee_userid_for_external, get_reception_progress_by_external,
    get_cached_tag_id, save_tag_cache, save_all_tags_from_remote, get_customer_remark,
    resolve_contact_external_userid, get_contact_external_userid
)


def get_or_create_tag(tag_name, group_name="患者标签"):
    """获取或创建企微标签，返回tag_id"""
    # 先查本地缓存
    cached = get_cached_tag_id(tag_name)
    if cached:
        return cached

    # 查企微远端
    token = get_wecom_access_token()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/get_corp_tag_list?access_token={token}"
    resp = requests.post(url, json={"tag_id": [], "group_id": []}).json()

    if resp.get("errcode") == 0:
        tag_groups = resp.get("tag_group", [])
        # 同步所有标签到本地缓存
        save_all_tags_from_remote(tag_groups)

        # 查找目标标签
        for group in tag_groups:
            for tag in group.get("tag", []):
                if tag.get("name") == tag_name:
                    return tag.get("id", "")

    # 不存在则创建
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/add_corp_tag?access_token={token}"
    resp = requests.post(url, json={
        "group_name": group_name,
        "tag": [{"name": tag_name}]
    }).json()

    if resp.get("errcode") == 0:
        tag_group = resp.get("tag_group", {})
        tags = tag_group.get("tag", [])
        if tags:
            tag_id = tags[0].get("id", "")
            grp_id = tag_group.get("group_id", "")
            save_tag_cache(tag_id, tag_name, grp_id, group_name)
            print(f"[TAG] 创建标签: {tag_name} -> {tag_id}")
            return tag_id

    print(f"[TAG] 创建标签失败: {tag_name}, resp={resp}")
    return ""


def tag_customer(employee_userid, external_userid, tag_names):
    """给客户打标签"""
    tag_ids = []
    for name in tag_names:
        tid = get_or_create_tag(name)
        if tid:
            tag_ids.append(tid)

    if not tag_ids:
        print(f"[TAG] 无有效标签ID，跳过打标签")
        return

    token = get_wecom_access_token()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/mark_tag?access_token={token}"
    resp = requests.post(url, json={
        "userid": employee_userid,
        "external_userid": external_userid,
        "add_tag": tag_ids
    }).json()
    print(f"[TAG] 打标签结果: {tag_names} -> {resp}")
    return resp


def update_customer_remark_and_desc(employee_userid, external_userid, remark, description):
    """修改客户备注名和描述"""
    token = get_wecom_access_token()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/remark?access_token={token}"
    payload = {
        "userid": employee_userid,
        "external_userid": external_userid,
        "remark": remark,
        "description": description
    }
    resp = requests.post(url, json=payload).json()
    print(f"[REMARK] 修改备注/描述: remark={remark}, resp={resp}")
    return resp


def recognize_image(file_path):
    """使用多模态LLM识别图片中的文字内容"""
    try:
        with open(file_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        ext = os.path.splitext(file_path)[1].lower()
        mime_type = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"

        payload = {
            "model": MLLM_MODEL_NAME,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "请识别这张营养方案图片中的所有文字内容，按原文格式完整输出，不要遗漏任何信息。"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_data}"
                            }
                        }
                    ]
                }
            ]
        }

        resp = requests.post(
            MLLM_BASE_URL,
            headers={"Authorization": f"Bearer {MLLM_API_KEY}"},
            json=payload,
            timeout=60
        )
        result = resp.json()
        text = result["choices"][0]["message"].get("content", "")
        print(f"[MLLM] 图片识别完成，内容长度: {len(text)}")
        return text

    except Exception as e:
        print(f"[MLLM] 图片识别失败: {e}")
        return ""

def download_media(media_id):
    """下载企微临时素材（图片），返回本地文件路径"""
    token = get_wecom_access_token()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/media/get?access_token={token}&media_id={media_id}"

    resp = requests.get(url, stream=True)
    content_type = resp.headers.get("Content-Type", "")

    if "image" in content_type or "application/octet-stream" in content_type:
        ext = ".jpg"
        if "png" in content_type:
            ext = ".png"
        filename = f"{media_id}{ext}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        with open(file_path, "wb") as f:
            for chunk in resp.iter_content(1024):
                f.write(chunk)
        print(f"[MEDIA] 图片已下载: {file_path}")
        return file_path
    else:
        print(f"[MEDIA] 下载失败: {resp.text[:200]}")
        return ""


def handle_patient_matched(external_userid, patient_info, open_kfid):
    """患者匹配成功后的完整处理流程：回复+打标签+改备注+写描述"""
    hospital = patient_info['hospital']
    patient_name = patient_info['patient_name']
    plan_type = patient_info['plan_type']
    group_link = patient_info['group_link']
    plan_content = patient_info['plan_content']

    # 1. 构建回复消息
    reply = f"已为您匹配信息！您的专属交流群：{group_link}"
    if plan_type == 'paper':
        reply += "\n\n另外，请您将纸质营养方案拍照发送给我，我们将为您存档。如暂不方便，也可以稍后再发。"
    else:
        reply += "\n\n您的电子营养方案已存档，营养师会为您跟进。"

    # 先发送回复
    kf_send_msg(external_userid, open_kfid, reply)

    # 2. 更新接待进度
    update_reception_patient_info(external_userid, patient_info)

    # 3. KF external_userid 映射为客户联系的 external_userid（优先用 scene 存入的 wob ID）
    contact_ext_id = get_contact_external_userid(external_userid)

    # 4. 获取员工userid
    employee_userid = get_employee_userid_for_external(external_userid)

    # 5. 打标签：月份 + 医院
    now = datetime.now()
    month_tag = f"{now.year}年{now.month}月"
    tag_customer(employee_userid, contact_ext_id, [month_tag, hospital])

    # 6. 改备注：医院全称+建档姓名
    new_remark = f"{hospital}+{patient_name}"
    # 7. 写描述
    if plan_type == 'electronic' and plan_content:
        description = f"方案类型：电子方案\n方案内容：{plan_content}"
    elif plan_type == 'paper':
        description = "方案类型：纸质方案（待上传）"
    else:
        description = ""
    update_customer_remark_and_desc(employee_userid, contact_ext_id, new_remark, description)

    print(f"[PATIENT] 匹配完成: {patient_name}({hospital}), 备注={new_remark}")


def handle_paper_plan_image(external_userid, media_id, open_kfid):
    """处理纸质方案图片上传：下载→识别→存档→更新描述"""
    row = get_reception_progress_by_external(external_userid)

    if row and row[2] == 'paper':
        # 下载图片
        file_path = download_media(media_id)
        if file_path:
            phone_tail = row[3] or ""
            save_patient_document(external_userid, phone_tail, 'paper_plan', media_id, file_path)

            # 先告诉患者已收到
            kf_send_msg(external_userid, open_kfid, "已收到您的纸质方案照片，正在识别内容...")

            # 用多模态LLM识别图片内容
            plan_text = recognize_image(file_path)

            # KF external_userid 映射为客户联系的 external_userid
            contact_ext_id = get_contact_external_userid(external_userid)
            employee_userid = get_employee_userid_for_external(external_userid)
            patient_name = row[0]
            hospital = row[1]
            remark = f"{hospital}+{patient_name}"

            if plan_text:
                description = f"方案类型：纸质方案\n方案内容：{plan_text}\n图片路径：{file_path}"
            else:
                description = f"方案类型：纸质方案（图片识别失败，需人工查看）\n图片路径：{file_path}"

            update_customer_remark_and_desc(employee_userid, contact_ext_id, remark, description)

            kf_send_msg(external_userid, open_kfid,
                        "您的纸质方案已识别并存档！如有其他问题请随时联系。" if plan_text
                        else "您的方案照片已存档，营养师会为您跟进。如有其他问题请随时联系。")
        else:
            kf_send_msg(external_userid, open_kfid, "图片接收出现问题，请重新发送。")
        return True
    return False
