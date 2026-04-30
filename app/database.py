# -*- coding: utf-8 -*-
"""
数据库：init_db() + 所有 DB 操作函数
"""
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

    # 兼容旧表：确保 reception_progress 有新字段
    _safe_alter(cursor, "ALTER TABLE reception_progress ADD COLUMN patient_name TEXT")
    _safe_alter(cursor, "ALTER TABLE reception_progress ADD COLUMN first_ask_time TEXT")
    _safe_alter(cursor, "ALTER TABLE reception_progress ADD COLUMN second_ask_time TEXT")
    _safe_alter(cursor, "ALTER TABLE reception_progress ADD COLUMN follow_up_count INTEGER DEFAULT 0")
    _safe_alter(cursor, "ALTER TABLE reception_progress ADD COLUMN plan_type TEXT DEFAULT ''")
    _safe_alter(cursor, "ALTER TABLE reception_progress ADD COLUMN group_link TEXT DEFAULT ''")
    _safe_alter(cursor, "ALTER TABLE reception_progress ADD COLUMN contact_external_userid TEXT DEFAULT ''")

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
        "SELECT last_customer_msg_time, reply_count FROM kf_conversations WHERE external_userid=? AND open_kfid=?",
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
    """KF enter_session 时初始化接待记录，contact_ext_id 为从 scene 获取的 wob ID"""
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO reception_progress
        (external_userid, status, add_time, welcome_sent, first_ask_time, follow_up_count, contact_external_userid)
        VALUES (?, 'in_progress', datetime('now'), 1, datetime('now'), 0, ?)
    ''', (external_userid, contact_ext_id))
    # 如果记录已存在，更新 first_ask_time 和 contact_external_userid
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
    """收到手机尾号时更新或创建接待记录"""
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
    """存储客户联系 external_userid，返回自增 ID（用于嵌入 scene，解决 32 字符限制）"""
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
    """通过 scene 中的 ID 查找对应的客户联系 external_userid"""
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute("SELECT contact_external_userid FROM scene_mapping WHERE id = ?", (scene_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else ""


# ================= 患者信息操作 =================

def match_patient(phone_tail):
    """用手机尾号查询患者信息，多条取最新"""
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT patient_name, phone_tail, hospital, plan_type, plan_content, group_link
        FROM patients WHERE phone_tail = ?
        ORDER BY created_at DESC LIMIT 1
    ''', (phone_tail,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "patient_name": row[0],
            "phone_tail": row[1],
            "hospital": row[2],
            "plan_type": row[3],
            "plan_content": row[4],
            "group_link": row[5]
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
    """查询患者匹配信息，用于动态构建AI system prompt"""
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
    """获取 KF external_userid 对应的客户联系 external_userid (wob ID)
    优先用 scene 存入的 contact_external_userid，其次用映射函数
    """
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    cursor.execute("SELECT contact_external_userid FROM reception_progress WHERE external_userid = ?", (kf_external_userid,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return row[0]
    # 没有存过，用映射函数兜底
    return resolve_contact_external_userid(kf_external_userid)


def get_employee_userid_for_external(external_userid):
    """查询某个外部联系人对应的员工userid"""
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
    """将 KF 的 external_userid (wmb开头) 映射为客户联系的 external_userid (wob开头)
    
    KF 和客户联系使用不同的 external_userid 体系：
    - KF: wmb 开头，用于 kf/send_msg 等
    - 客户联系: wob 开头，用于 externalcontact/remark、mark_tag 等
    
    映射方式：
    1. 按 patients 表的手机尾号→患者姓名→customers 表匹配
    2. 按 reception_progress 的患者姓名→customers 表匹配
    3. 按 customers 表的 remark 字段模糊匹配
    4. 遍历所有员工的外部联系人列表匹配
    """
    import requests
    from app.wechat_api import get_wecom_access_token
    from app.config import DEFAULT_EMPLOYEE_USERID

    # 如果已经是 wob 开头，直接返回
    if kf_external_userid.startswith('wob'):
        return kf_external_userid

    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()

    # 方式1：从 reception_progress 查手机尾号 → patients 表查姓名 → customers 匹配
    cursor.execute("SELECT phone_tail, patient_name FROM reception_progress WHERE external_userid = ?", (kf_external_userid,))
    row = cursor.fetchone()
    phone_tail = row[0] if row else None
    patient_name = row[1] if row else None

    # 用手机尾号从 patients 表查真实的患者姓名
    if phone_tail:
        cursor.execute("SELECT patient_name FROM patients WHERE phone_tail = ? ORDER BY created_at DESC LIMIT 1", (phone_tail,))
        pt_row = cursor.fetchone()
        if pt_row:
            patient_name = pt_row[0]
            # 同步更新 reception_progress
            cursor.execute("UPDATE reception_progress SET patient_name = ? WHERE external_userid = ?", (patient_name, kf_external_userid))
            conn.commit()

    # 方式2：用患者姓名在 customers 表里匹配（customer_name 或 remark）
    if patient_name:
        cursor.execute("SELECT external_userid, employee_userid FROM customers WHERE customer_name = ? OR remark = ?",
                       (patient_name, patient_name))
        cust_row = cursor.fetchone()
        if cust_row:
            conn.close()
            print(f"[MAPPING] KF {kf_external_userid} -> 客户联系 {cust_row[0]} (by name: {patient_name})")
            return cust_row[0]

    # 方式3：用备注模糊匹配（patients 表的姓名可能和 customers 的 remark 部分匹配）
    if patient_name:
        cursor.execute("SELECT external_userid, employee_userid FROM customers WHERE customer_name LIKE ? OR remark LIKE ?",
                       (f"%{patient_name}%", f"%{patient_name}%"))
        cust_row = cursor.fetchone()
        if cust_row:
            conn.close()
            print(f"[MAPPING] KF {kf_external_userid} -> 客户联系 {cust_row[0]} (by fuzzy: {patient_name})")
            return cust_row[0]

    conn.close()

    # 方式4：遍历默认员工的外部联系人列表
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
    """按姓名或备注查找客户，返回 (external_userid, customer_name, remark)"""
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    # 精确匹配
    cursor.execute("SELECT external_userid, customer_name, remark FROM customers WHERE employee_userid=? AND (customer_name=? OR remark=?)",
                   (employee_userid, customer_name, customer_name))
    row = cursor.fetchone()
    if not row:
        # 模糊匹配
        cursor.execute("SELECT external_userid, customer_name, remark FROM customers WHERE employee_userid=? AND (customer_name LIKE ? OR remark LIKE ?)",
                       (employee_userid, f"%{customer_name}%", f"%{customer_name}%"))
        row = cursor.fetchone()
    conn.close()
    return row


def get_reception_progress_by_external(external_userid):
    """查询接待进度记录"""
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
    """查询需要跟进的记录"""
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
    """更新跟进状态"""
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
    """标记为未回复"""
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
    """查询今天标记为未回复的记录"""
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
    """查询客户的备注和姓名"""
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
    """从远端同步所有标签到本地缓存"""
    conn = sqlite3.connect('wecom_cache.db')
    cursor = conn.cursor()
    found_tag_id = None
    for group in tag_groups:
        for tag in group.get("tag", []):
            tag_id = tag.get("id", "")
            tag_n = tag.get("name", "")
            grp_id = group.get("group_id", "")
            grp_name = group.get("group_name", "")
            cursor.execute('''
                INSERT OR REPLACE INTO corp_tags (tag_id, tag_name, group_id, group_name, updated_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            ''', (tag_id, tag_n, grp_id, grp_name))
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


# 初始化数据库
init_db()
