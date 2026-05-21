# -*- coding: utf-8 -*-
"""
数据库：init_db() + 所有 DB 操作函数
v5新增：group_b, group_b_live_qr 表及相关操作
"""
import json
import sqlite3


def init_db():
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            employee_userid TEXT,
            customer_name TEXT,
            external_userid TEXT,
            remark TEXT DEFAULT '',
            PRIMARY KEY (employee_userid, external_userid)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reception_progress (
            external_userid TEXT PRIMARY KEY,
            employee_userid TEXT,
            add_time TEXT,
            phone_tail TEXT,
            hospital TEXT,
            patient_name TEXT,
            patient_matched INTEGER DEFAULT 0,
            welcome_sent INTEGER DEFAULT 0,
            phone_received INTEGER DEFAULT 0,
            status TEXT DEFAULT 'in_progress',
            first_ask_time TEXT,
            second_ask_time TEXT,
            follow_up_count INTEGER DEFAULT 0,
            contact_external_userid TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kf_sync_cursor (
            open_kfid TEXT PRIMARY KEY,
            cursor TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kf_chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_userid TEXT,
            open_kfid TEXT,
            role TEXT,
            content TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kf_conversations (
            external_userid TEXT,
            open_kfid TEXT,
            last_customer_msg_time REAL DEFAULT 0,
            reply_count INTEGER DEFAULT 0,
            service_state INTEGER DEFAULT 0,
            phone_tail TEXT DEFAULT '',
            patient_name TEXT DEFAULT '',
            PRIMARY KEY (external_userid, open_kfid)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            phone_tail TEXT NOT NULL,
            hospital TEXT NOT NULL,
            plan_type TEXT NOT NULL,
            plan_content TEXT DEFAULT '',
            group_link TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patient_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_userid TEXT,
            phone_tail TEXT,
            doc_type TEXT DEFAULT 'paper_plan',
            media_id TEXT,
            file_path TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS corp_tags (
            tag_id TEXT PRIMARY KEY,
            tag_name TEXT NOT NULL,
            group_id TEXT DEFAULT '',
            group_name TEXT DEFAULT '',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scene_mapping (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_external_userid TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ===== v5 新增表 =====

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_b (
            chat_id TEXT PRIMARY KEY,
            hospital TEXT NOT NULL,
            chat_name TEXT DEFAULT '',
            member_count INTEGER DEFAULT 1,
            max_members INTEGER DEFAULT 200,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_b_live_qr (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital TEXT NOT NULL,
            config_id TEXT DEFAULT '',
            qr_code_url TEXT DEFAULT '',
            chat_ids TEXT DEFAULT '[]',
            auto_create_group INTEGER DEFAULT 1,
            room_base_name TEXT DEFAULT '',
            room_base_id INTEGER DEFAULT 1,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hospitals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital TEXT NOT NULL UNIQUE,
            room_base_name TEXT DEFAULT '',
            room_base_id INTEGER DEFAULT 1,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 插入测试数据（仅在表为空时）
    cursor.execute("SELECT COUNT(*) FROM patients")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO patients (patient_name, phone_tail, hospital, plan_type, plan_content, group_link)
            VALUES ('张三', '8860', '北京协和医院', 'electronic',
                    '低盐低脂饮食方案：每日钠摄入<2g，限制脂肪供能比<25%，增加膳食纤维摄入至25-30g/日，推荐食物：全谷物、新鲜蔬菜、低脂奶制品。',
                    'https://work.weixin.qq.com/group1')
        ''')
        cursor.execute('''
            INSERT INTO patients (patient_name, phone_tail, hospital, plan_type, plan_content, group_link)
            VALUES ('李四', '5786', '上海瑞金医院', 'paper', '',
                    'https://work.weixin.qq.com/group2')
        ''')
        print("[DB] 已插入测试患者数据：张三(8860/电子方案)、李四(5786/纸质方案)")

    # 插入医院测试数据
    cursor.execute("SELECT COUNT(*) FROM hospitals")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO hospitals (hospital, room_base_name, room_base_id) VALUES ('北京协和医院', '北京协和医院患者交流', 1)")
        cursor.execute("INSERT INTO hospitals (hospital, room_base_name, room_base_id) VALUES ('上海瑞金医院', '上海瑞金医院患者交流', 1)")
        print("[DB] 已插入测试医院数据：北京协和医院、上海瑞金医院")

    # 兼容旧表字段
    _safe_alter(cursor, "ALTER TABLE reception_progress ADD COLUMN patient_name TEXT")
    _safe_alter(cursor, "ALTER TABLE reception_progress ADD COLUMN first_ask_time TEXT")
    _safe_alter(cursor, "ALTER TABLE reception_progress ADD COLUMN second_ask_time TEXT")
    _safe_alter(cursor, "ALTER TABLE reception_progress ADD COLUMN follow_up_count INTEGER DEFAULT 0")
    _safe_alter(cursor, "ALTER TABLE reception_progress ADD COLUMN plan_type TEXT DEFAULT ''")
    _safe_alter(cursor, "ALTER TABLE reception_progress ADD COLUMN group_link TEXT DEFAULT ''")
    _safe_alter(cursor, "ALTER TABLE reception_progress ADD COLUMN contact_external_userid TEXT DEFAULT ''")
    _safe_alter(cursor, "ALTER TABLE group_b_live_qr ADD COLUMN room_base_name TEXT DEFAULT ''")
    _safe_alter(cursor, "ALTER TABLE group_b_live_qr ADD COLUMN room_base_id INTEGER DEFAULT 1")
    _safe_alter(cursor, "ALTER TABLE kf_conversations ADD COLUMN phone_tail TEXT DEFAULT ''")
    _safe_alter(cursor, "ALTER TABLE kf_conversations ADD COLUMN patient_name TEXT DEFAULT ''")

    conn.commit()
    conn.close()


def _safe_alter(cursor, sql):
    """执行 ALTER TABLE，忽略列已存在的错误"""
    try:
        cursor.execute(sql)
    except Exception:
        pass


# ================= KF 游标操作 =================

def save_kf_cursor(open_kfid, cursor_val):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO kf_sync_cursor (open_kfid, cursor, updated_at)
        VALUES (?, ?, datetime('now'))
    ''', (open_kfid, cursor_val))
    conn.commit()
    conn.close()


def get_kf_cursor(open_kfid):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute("SELECT cursor FROM kf_sync_cursor WHERE open_kfid=?", (open_kfid,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else ""


# ================= KF 会话状态操作 =================

def update_kf_conversation(external_userid, open_kfid, is_customer_msg=True):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    if is_customer_msg:
        import time
        now = time.time()
        cursor.execute('''
            INSERT OR REPLACE INTO kf_conversations (external_userid, open_kfid, last_customer_msg_time, reply_count, service_state)
            VALUES (?, ?, ?, 0, 1)
        ''', (external_userid, open_kfid, now))
    else:
        cursor.execute('''
            INSERT OR IGNORE INTO kf_conversations (external_userid, open_kfid, last_customer_msg_time, reply_count, service_state)
            VALUES (?, ?, 0, 0, 0)
        ''', (external_userid, open_kfid))
    conn.commit()
    conn.close()


def get_kf_conversation(external_userid, open_kfid):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT last_customer_msg_time, reply_count, phone_tail, patient_name FROM kf_conversations WHERE external_userid=? AND open_kfid=?",
        (external_userid, open_kfid)
    )
    row = cursor.fetchone()
    conn.close()
    return row


def increment_kf_reply_count(external_userid, open_kfid):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE kf_conversations SET reply_count = reply_count + 1 WHERE external_userid=? AND open_kfid=?",
        (external_userid, open_kfid)
    )
    conn.commit()
    conn.close()


def update_kf_service_state(external_userid, open_kfid, state):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE kf_conversations SET service_state=? WHERE external_userid=? AND open_kfid=?",
        (state, external_userid, open_kfid)
    )
    conn.commit()
    conn.close()


def update_kf_phone_tail(external_userid, open_kfid, phone_tail):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE kf_conversations SET phone_tail=? WHERE external_userid=? AND open_kfid=?",
        (phone_tail, external_userid, open_kfid)
    )
    conn.commit()
    conn.close()


def update_kf_patient_name(external_userid, open_kfid, patient_name):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE kf_conversations SET patient_name=? WHERE external_userid=? AND open_kfid=?",
        (patient_name, external_userid, open_kfid)
    )
    conn.commit()
    conn.close()


# ================= 接待进度操作 =================

def create_reception_progress(external_userid, employee_userid):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO reception_progress
        (external_userid, employee_userid, add_time, welcome_sent, status, first_ask_time, follow_up_count)
        VALUES (?, ?, datetime('now'), 1, 'in_progress', datetime('now'), 0)
    ''', (external_userid, employee_userid))
    conn.commit()
    conn.close()


def update_phone_received(external_userid, phone_tail):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE reception_progress
        SET phone_tail = ?, phone_received = 1, updated_at = datetime('now')
        WHERE external_userid = ?
    ''', (phone_tail, external_userid))
    conn.commit()
    conn.close()


def update_reception_patient_info(external_userid, patient_info):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE reception_progress
        SET patient_matched = 1, patient_name = ?, hospital = ?, phone_tail = ?,
            plan_type = ?, group_link = ?, updated_at = datetime('now')
        WHERE external_userid = ?
    ''', (patient_info['patient_name'], patient_info['hospital'], patient_info['phone_tail'],
          patient_info.get('plan_type', ''), patient_info.get('group_link', ''), external_userid))
    conn.commit()
    conn.close()


def insert_reception_on_kf_enter(external_userid, contact_ext_id=""):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO reception_progress
        (external_userid, status, add_time, welcome_sent, first_ask_time, follow_up_count, contact_external_userid)
        VALUES (?, 'in_progress', datetime('now'), 1, datetime('now'), 0, ?)
    ''', (external_userid, contact_ext_id))
    cursor.execute('''
        UPDATE reception_progress SET first_ask_time = COALESCE(first_ask_time, datetime('now'))
        WHERE external_userid = ? AND first_ask_time IS NULL
    ''', (external_userid,))
    if contact_ext_id:
        cursor.execute('''
            UPDATE reception_progress SET contact_external_userid = ?
            WHERE external_userid = ? AND (contact_external_userid IS NULL OR contact_external_userid = '')
        ''', (contact_ext_id, external_userid))
    conn.commit()
    conn.close()


def insert_reception_on_phone_tail(external_userid, phone_tail, patient_info=None):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    if patient_info:
        cursor.execute('''
            INSERT OR REPLACE INTO reception_progress
            (external_userid, phone_tail, phone_received, status, add_time, welcome_sent,
             patient_matched, patient_name, hospital, plan_type, group_link, first_ask_time, follow_up_count)
            VALUES (?, ?, 1, 'in_progress', datetime('now'), 1,
                    1, ?, ?, ?, ?, datetime('now'), 0)
        ''', (external_userid, phone_tail,
              patient_info['patient_name'], patient_info['hospital'],
              patient_info.get('plan_type', ''), patient_info.get('group_link', '')))
    else:
        cursor.execute('''
            INSERT OR REPLACE INTO reception_progress
            (external_userid, phone_tail, phone_received, status, add_time, welcome_sent,
             patient_matched, first_ask_time, follow_up_count)
            VALUES (?, ?, 1, 'in_progress', datetime('now'), 1,
                    0, datetime('now'), 0)
        ''', (external_userid, phone_tail))
    conn.commit()
    conn.close()


# ================= Scene 映射操作 =================

def save_scene_mapping(contact_external_userid):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO scene_mapping (contact_external_userid) VALUES (?)
    ''', (contact_external_userid,))
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_scene_mapping(scene_id):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute("SELECT contact_external_userid FROM scene_mapping WHERE id = ?", (scene_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else ""


# ================= 患者信息操作 =================

def match_patient(phone_tail, patient_name=""):
    """根据手机尾号和姓名匹配患者。姓名为空时仅按尾号匹配"""
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    if patient_name:
        cursor.execute('''
            SELECT patient_name, phone_tail, hospital, plan_type, plan_content, group_link
            FROM patients WHERE phone_tail = ? AND patient_name = ?
            ORDER BY created_at DESC LIMIT 1
        ''', (phone_tail, patient_name))
    else:
        cursor.execute('''
            SELECT patient_name, phone_tail, hospital, plan_type, plan_content, group_link
            FROM patients WHERE phone_tail = ?
            ORDER BY created_at DESC LIMIT 1
        ''', (phone_tail,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "patient_name": row[0], "phone_tail": row[1], "hospital": row[2],
            "plan_type": row[3], "plan_content": row[4], "group_link": row[5]
        }
    return None


def save_patient_document(external_userid, phone_tail, doc_type, media_id, file_path):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO patient_documents (external_userid, phone_tail, doc_type, media_id, file_path)
        VALUES (?, ?, ?, ?, ?)
    ''', (external_userid, phone_tail, doc_type, media_id, file_path))
    conn.commit()
    conn.close()


def get_patient_context_for_prompt(external_userid):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT patient_name, hospital, plan_type
        FROM reception_progress WHERE external_userid = ? AND patient_matched = 1
    ''', (external_userid,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"patient_name": row[0], "hospital": row[1], "plan_type": row[2]}
    return None


def get_contact_external_userid(kf_external_userid):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute("SELECT contact_external_userid FROM reception_progress WHERE external_userid = ?", (kf_external_userid,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return row[0]
    return resolve_contact_external_userid(kf_external_userid)


def get_employee_userid_for_external(external_userid):
    from app.config import DEFAULT_EMPLOYEE_USERID
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute("SELECT employee_userid FROM reception_progress WHERE external_userid = ?", (external_userid,))
    row = cursor.fetchone()
    if row and row[0]:
        conn.close()
        return row[0]
    cursor.execute("SELECT employee_userid FROM customers WHERE external_userid = ?", (external_userid,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    return DEFAULT_EMPLOYEE_USERID


def resolve_contact_external_userid(kf_external_userid):
    """将 KF 的 external_userid (wmb开头) 映射为客户联系的 external_userid (wob开头)"""
    import requests
    from app.wechat_api import get_wecom_access_token
    from app.config import DEFAULT_EMPLOYEE_USERID

    if kf_external_userid.startswith('wob'):
        return kf_external_userid

    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()

    cursor.execute("SELECT phone_tail, patient_name FROM reception_progress WHERE external_userid = ?", (kf_external_userid,))
    row = cursor.fetchone()
    phone_tail = row[0] if row else None
    patient_name = row[1] if row else None

    if phone_tail:
        cursor.execute("SELECT patient_name FROM patients WHERE phone_tail = ? ORDER BY created_at DESC LIMIT 1", (phone_tail,))
        pt_row = cursor.fetchone()
        if pt_row:
            patient_name = pt_row[0]
            cursor.execute("UPDATE reception_progress SET patient_name = ? WHERE external_userid = ?", (patient_name, kf_external_userid))
            conn.commit()

    if patient_name:
        cursor.execute("SELECT external_userid, employee_userid FROM customers WHERE customer_name = ? OR remark = ?",
                       (patient_name, patient_name))
        cust_row = cursor.fetchone()
        if cust_row:
            conn.close()
            print(f"[MAPPING] KF {kf_external_userid} -> 客户联系 {cust_row[0]} (by name: {patient_name})")
            return cust_row[0]

    if patient_name:
        cursor.execute("SELECT external_userid, employee_userid FROM customers WHERE customer_name LIKE ? OR remark LIKE ?",
                       (f"%{patient_name}%", f"%{patient_name}%"))
        cust_row = cursor.fetchone()
        if cust_row:
            conn.close()
            print(f"[MAPPING] KF {kf_external_userid} -> 客户联系 {cust_row[0]} (by fuzzy: {patient_name})")
            return cust_row[0]

    conn.close()

    token = get_wecom_access_token()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/batch/get_by_user?access_token={token}"
    resp = requests.post(url, json={"userid_list": [DEFAULT_EMPLOYEE_USERID], "limit": 100}).json()
    if resp.get("errcode") == 0:
        for item in resp.get("external_contact_list", []):
            contact = item.get("external_contact", {})
            name = contact.get("name", "")
            eid = contact.get("external_userid", "")
            if patient_name and name == patient_name:
                conn = sqlite3.connect('wecom_cache.db')
                cursor = conn.cursor()
                cursor.execute("REPLACE INTO customers (employee_userid, customer_name, external_userid, remark) VALUES (?, ?, ?, ?)",
                               (DEFAULT_EMPLOYEE_USERID, name, eid, ""))
                conn.commit()
                conn.close()
                print(f"[MAPPING] KF {kf_external_userid} -> 客户联系 {eid} (by sync: {name})")
                return eid

    print(f"[MAPPING] 未能映射 KF external_userid: {kf_external_userid}")
    return kf_external_userid


def get_customer_by_name_or_remark(employee_userid, customer_name):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute("SELECT external_userid, customer_name, remark FROM customers WHERE employee_userid=? AND (customer_name=? OR remark=?)",
                   (employee_userid, customer_name, customer_name))
    row = cursor.fetchone()
    if not row:
        cursor.execute("SELECT external_userid, customer_name, remark FROM customers WHERE employee_userid=? AND (customer_name LIKE ? OR remark LIKE ?)",
                       (employee_userid, f"%{customer_name}%", f"%{customer_name}%"))
        row = cursor.fetchone()
    conn.close()
    return row


def get_reception_progress_by_external(external_userid):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT patient_name, hospital, plan_type, phone_tail
        FROM reception_progress
        WHERE external_userid = ? AND patient_matched = 1
    ''', (external_userid,))
    row = cursor.fetchone()
    conn.close()
    return row


def get_pending_follow_ups():
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT external_userid, employee_userid, first_ask_time, second_ask_time,
               follow_up_count, patient_name, hospital
        FROM reception_progress
        WHERE status = 'in_progress' AND phone_received = 0 AND first_ask_time IS NOT NULL
    ''')
    rows = cursor.fetchall()
    conn.close()
    return rows


def update_follow_up(external_userid, follow_up_count, second_ask_time=None):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    if second_ask_time:
        cursor.execute('''
            UPDATE reception_progress
            SET follow_up_count = ?, second_ask_time = datetime('now'), updated_at = datetime('now')
            WHERE external_userid = ?
        ''', (follow_up_count, external_userid))
    else:
        cursor.execute('''
            UPDATE reception_progress
            SET follow_up_count = ?, updated_at = datetime('now')
            WHERE external_userid = ?
        ''', (follow_up_count, external_userid))
    conn.commit()
    conn.close()


def mark_no_response(external_userid):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE reception_progress
        SET follow_up_count = 2, status = 'no_response', updated_at = datetime('now')
        WHERE external_userid = ?
    ''', (external_userid,))
    conn.commit()
    conn.close()


def get_no_response_today():
    from datetime import datetime
    today_start = datetime.now().strftime("%Y-%m-%d") + " 00:00:00"
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT external_userid, patient_name, hospital, remark
        FROM reception_progress
        WHERE status = 'no_response' AND updated_at >= ?
    ''', (today_start,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_customer_remark(external_userid):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute("SELECT remark, customer_name FROM customers WHERE external_userid = ?", (external_userid,))
    row = cursor.fetchone()
    conn.close()
    return row


# ================= 企微标签缓存 =================

def get_cached_tag_id(tag_name):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute("SELECT tag_id FROM corp_tags WHERE tag_name = ?", (tag_name,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def save_tag_cache(tag_id, tag_name, group_id, group_name):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO corp_tags (tag_id, tag_name, group_id, group_name, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'))
    ''', (tag_id, tag_name, group_id, group_name))
    conn.commit()
    conn.close()


def save_all_tags_from_remote(tag_groups):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    for group in tag_groups:
        for tag in group.get("tag", []):
            cursor.execute('''
                INSERT OR REPLACE INTO corp_tags (tag_id, tag_name, group_id, group_name, updated_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            ''', (tag.get("id", ""), tag.get("name", ""),
                  group.get("group_id", ""), group.get("group_name", "")))
    conn.commit()
    conn.close()


# ================= KF 聊天历史 =================

def save_chat_history(external_userid, open_kfid, role, content):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO kf_chat_history (external_userid, open_kfid, role, content) VALUES (?, ?, ?, ?)",
        (external_userid, open_kfid, role, content)
    )
    conn.commit()
    conn.close()


def get_chat_history(external_userid, open_kfid, limit=20):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM kf_chat_history WHERE external_userid=? AND open_kfid=? ORDER BY id DESC LIMIT ?",
        (external_userid, open_kfid, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


# ================= 群B操作（v5新增）=================

def save_group_b(chat_id, hospital, chat_name="", member_count=1):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO group_b (chat_id, hospital, chat_name, member_count, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'))
    ''', (chat_id, hospital, chat_name, member_count))
    conn.commit()
    conn.close()


def get_group_b_by_hospital(hospital):
    """查找某医院的所有群B"""
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id, hospital, chat_name, member_count FROM group_b WHERE hospital = ? AND status = 'active'",
                   (hospital,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_group_b_available(hospital):
    """获取某医院当前可用的群B（未满200人的）"""
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id, hospital, chat_name, member_count FROM group_b WHERE hospital = ? AND status = 'active' AND member_count < 200 ORDER BY member_count ASC",
                   (hospital,))
    row = cursor.fetchone()
    conn.close()
    return row


def refresh_group_b_member_count(chat_id):
    """从企微API同步群B的真实成员数"""
    from app.group_b_api import get_customer_group_chat
    resp = get_customer_group_chat(chat_id)
    if resp.get("errcode") == 0:
        member_list = resp.get("group_chat", {}).get("member_list", [])
        real_count = len(member_list)
        conn = sqlite3.connect('wecom_cache.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE group_b SET member_count = ?, updated_at = datetime('now') WHERE chat_id = ?",
                       (real_count, chat_id))
        conn.commit()
        conn.close()
        return real_count
    return None


def save_group_b_live_qr(hospital, config_id, qr_code_url, chat_ids, room_base_name="", room_base_id=1):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO group_b_live_qr (hospital, config_id, qr_code_url, chat_ids, room_base_name, room_base_id, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
    ''', (hospital, config_id, qr_code_url, json.dumps(chat_ids) if isinstance(chat_ids, list) else chat_ids,
          room_base_name, room_base_id))
    conn.commit()
    conn.close()


def get_group_b_live_qr(hospital):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, hospital, config_id, qr_code_url, chat_ids, status FROM group_b_live_qr WHERE hospital = ? AND status = 'active'",
                   (hospital,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0], "hospital": row[1], "config_id": row[2],
            "qr_code_url": row[3], "chat_ids": json.loads(row[4]) if row[4] else [],
            "status": row[5]
        }
    return None


def update_group_b_live_qr_chat_ids(config_id, chat_ids):
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE group_b_live_qr SET chat_ids = ?, updated_at = datetime('now') WHERE config_id = ?",
                   (json.dumps(chat_ids), config_id))
    conn.commit()
    conn.close()


# ================= 医院管理操作 =================

def get_all_hospitals():
    """获取所有医院列表（H5下拉用）"""
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, hospital, room_base_name, room_base_id FROM hospitals WHERE status = 'active' ORDER BY hospital")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "hospital": r[1], "room_base_name": r[2], "room_base_id": r[3]} for r in rows]


def get_hospital_by_name(hospital):
    """获取单个医院信息"""
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, hospital, room_base_name, room_base_id FROM hospitals WHERE hospital = ? AND status = 'active'", (hospital,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "hospital": row[1], "room_base_name": row[2], "room_base_id": row[3]}
    return None


def save_hospital(hospital, room_base_name="", room_base_id=1):
    """保存或更新医院信息（upsert）"""
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO hospitals (hospital, room_base_name, room_base_id, status, created_at)
        VALUES (?, ?, ?, 'active', COALESCE((SELECT created_at FROM hospitals WHERE hospital = ?), datetime('now')))
    ''', (hospital, room_base_name or f"{hospital}患者交流", room_base_id, hospital))
    conn.commit()
    conn.close()


def delete_hospital(hospital):
    """软删除医院"""
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE hospitals SET status = 'inactive' WHERE hospital = ?", (hospital,))
    conn.commit()
    conn.close()


# 初始化数据库
init_db()
