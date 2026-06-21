# -*- coding: utf-8 -*-
"""PyInstaller 入口脚本 — 打包为单文件 exe

运行后：
1. 自动在当前目录创建 static/dist、static/uploads、qa_database.db
2. 启动 uvicorn 服务 (0.0.0.0:8000)
3. 自动打开浏览器
"""
import os
import sys
import webbrowser
import threading
import time

# --- 1. 计算运行时目录 ---
# PyInstaller --onefile 模式下，sys._MEIPASS 是临时解压目录（只读）
# exe 所在目录 = os.path.dirname(sys.executable)
if getattr(sys, 'frozen', False):
    # 打包后的 exe 运行
    APP_DIR = os.path.dirname(sys.executable)
    MEIPASS = sys._MEIPASS  # PyInstaller 临时解压目录
    # 把 APP_DIR 加入 sys.path，让 app 包可被导入
    sys.path.insert(0, APP_DIR)
else:
    # 开发模式直接运行
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    MEIPASS = None

# backend 目录 = APP_DIR（exe 和 backend 代码同级）
# 但 app 包在 backend/ 下，所以需要把 backend 加入 path
BACKEND_DIR = APP_DIR
sys.path.insert(0, BACKEND_DIR)

# --- 2. 设置工作目录 ---
os.chdir(BACKEND_DIR)

# --- 3. 创建必要的运行时目录 ---
static_dir = os.path.join(BACKEND_DIR, "app", "static")
os.makedirs(static_dir, exist_ok=True)
os.makedirs(os.path.join(static_dir, "uploads"), exist_ok=True)
os.makedirs(os.path.join(static_dir, "dist"), exist_ok=True)
os.makedirs(os.path.join(static_dir, "dist", "assets"), exist_ok=True)

# --- 4. 从 exe 内部释放数据文件到 exe 同级目录（首次运行）---
import shutil

if MEIPASS:
    # 4a. 释放题库数据库（如果 exe 同级目录没有，就从 exe 内部复制）
    bundled_db = os.path.join(MEIPASS, "app", "static", "qa_database.db")
    target_db = os.path.join(static_dir, "qa_database.db")
    if os.path.isfile(bundled_db) and not os.path.isfile(target_db):
        shutil.copy2(bundled_db, target_db)
        print(f"[初始化] 已释放题库数据库: {target_db}")

    # 4b. 释放前端构建产物（dist/ 目录）
    bundled_dist = os.path.join(MEIPASS, "app", "static", "dist")
    target_dist = os.path.join(static_dir, "dist")
    if os.path.isdir(bundled_dist):
        for item in os.listdir(bundled_dist):
            src = os.path.join(bundled_dist, item)
            dst = os.path.join(target_dist, item)
            if os.path.isfile(src) and not os.path.isfile(dst):
                shutil.copy2(src, dst)
            elif os.path.isdir(src) and not os.path.isdir(dst):
                shutil.copytree(src, dst)
        print(f"[初始化] 已释放前端文件: {target_dist}")

# --- 5. 启动浏览器（延迟2秒）---
def open_browser():
    time.sleep(2)
    webbrowser.open("http://localhost:8000")

threading.Thread(target=open_browser, daemon=True).start()

# --- 6. 启动 uvicorn ---
import uvicorn

if __name__ == "__main__":
    print("=" * 50)
    print("  智能题库系统启动中...")
    print("  浏览器访问: http://localhost:8000")
    print("  按 Ctrl+C 停止服务")
    print("=" * 50)

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1,
    )
