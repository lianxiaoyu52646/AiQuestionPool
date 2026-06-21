@echo off
chcp 65001 >nul 2>&1
title 智能题库系统

echo ============================================
echo    智能题库系统 - 一键启动
echo ============================================
echo.

cd /d "%~dp0"

REM --- 检查 Python ---
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+ 并添加到 PATH
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM --- 创建虚拟环境（首次运行）---
if not exist "venv\Scripts\python.exe" (
    echo [1/3] 首次运行，正在创建虚拟环境...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo       虚拟环境创建完成
) else (
    echo [1/3] 虚拟环境已存在
)

REM --- 安装依赖（首次运行或依赖缺失时）---
echo [2/3] 检查依赖...
venv\Scripts\python.exe -c "import fastapi, uvicorn, sqlalchemy, fitz, fsrs" >nul 2>&1
if %errorlevel% neq 0 (
    echo       正在安装依赖（首次需要联网，约1-2分钟）...
    venv\Scripts\python.exe -m pip install --upgrade pip -q
    venv\Scripts\python.exe -m pip install -r requirements.txt -q
    if %errorlevel% neq 0 (
        echo [错误] 依赖安装失败，请检查网络连接
        pause
        exit /b 1
    )
    echo       依赖安装完成
) else (
    echo       依赖已就绪
)

REM --- 启动服务 ---
echo [3/3] 启动服务...
echo.
echo ============================================
echo   浏览器访问: http://localhost:8000
echo   API 文档:   http://localhost:8000/docs
echo   按 Ctrl+C 停止服务
echo ============================================
echo.

cd backend
..\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

pause
