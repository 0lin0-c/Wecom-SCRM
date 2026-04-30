# CODEBUDDY.md

This file provides guidance to CodeBuddy Code when working with code in this repository.

## Project Overview

WeChat Work (企业微信) auto-reception system — a FastAPI server that handles WeChat Work callbacks, sends automated welcome messages to new contacts, collects phone tail numbers, and uses an LLM (GLM-5 via Tencent Cloud) with tool calling to handle employee requests like modifying customer remarks.

## Running the Application

```bash
# Start the server (latest version)
python main_v3.py
# Binds to 0.0.0.0:8500

# Run a test script (no test framework — all are standalone scripts)
python test_api.py
python test_full_flow.py
python test_contact_way.py
```

There is no build step, no dependency management file (no requirements.txt), and no formal test framework. Dependencies (`fastapi`, `uvicorn`, `wechatpy`, `requests`, `xmltodict`) must be installed via pip manually.

## Version Convention

The project uses filename-based versioning rather than git: `main_v1.py` → `main_v2.py` → `main_v3.py`. The active/latest version is `main_v3.py`. Previous versions are kept for reference.

## Architecture

```
WeChat Work Platform
        │
  (HTTP callbacks)
        ▼
┌─────────────────────────────────────────────┐
│           FastAPI (Uvicorn :8500)            │
│                                              │
│  GET/POST /wechat/callback        (app msgs) │
│  GET/POST /wechat/contact/callback (contacts)│
└──────┬──────────────────────┬───────────────┘
       │                      │
       ▼                      ▼
chat_with_ai_and_execute()  handle_add_external_contact()
       │                      ├── send_welcome_message()
       ▼                      ├── create_reception_progress()
  LLM API (GLM-5)            └── handle_external_contact_msg()
  with tool calling                   └── update_phone_received()
       │
       ▼
 modify_customer_remark()
       │
       ▼
┌──────────────────────────────┐
│   SQLite (wecom_cache.db)    │
│  - customers                 │
│  - reception_progress        │
└──────────────────────────────┘
```

### Key Data Flows

- **App message callback** (`/wechat/callback`): Employee sends text via self-built app. If content is "sync data", triggers `sync_employee_customers()`. Otherwise, the LLM interprets the message and may call `modify_customer_remark()` as a tool.
- **Contact event callback** (`/wechat/contact/callback`): When an external contact is added (scans QR), a welcome message is sent and reception progress is created. When the contact replies with a 4-digit number, it's recorded as their phone tail.
- Two separate `WeChatCrypto` instances (`app_crypto` and `contact_crypto`) handle decryption for the two callback endpoints.

### Configuration

All config is hardcoded at the top of `main_v3.py` (CorpID, Secret, AgentID, Token, AES Key, LLM API key/URL). There is no `.env` file or environment variable usage. The `create_qr.py` and `test_new_*` files reference a secondary enterprise (CorpID `ww5bb595253ba23914`).

## Standalone Scripts

| Script | Purpose |
|--------|---------|
| `create_qr.py` | Create "Contact Me" QR code (template for new enterprises) |
| `modify_remark.py` | Directly modify a specific customer's remark |
| `test_*.py` | Ad-hoc API connectivity and flow tests (not pytest) |
