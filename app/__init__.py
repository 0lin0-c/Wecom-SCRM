# -*- coding: utf-8 -*-
"""
企业微信自动接待系统 v5 - 应用入口
"""
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI

app = FastAPI()

# 导入路由以注册端点
from app import routes  # noqa: E402, F401
