# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec 文件 — 智能题库系统打包配置

打包命令:
    cd d:\lian\praPro\e\backend
    ..\venv\Scripts\pyinstaller.exe smart_qbank.spec

输出:
    dist/smart-qbank.exe  (单文件)
"""

import os

block_cipher = None

# backend 目录
backend_dir = os.path.abspath('.')

a = Analysis(
    ['run_exe.py'],
    pathex=[backend_dir],
    binaries=[],
    datas=[
        # 打包前端构建产物 (dist/index.html, dist/assets/)
        ('app/static/dist', 'app/static/dist'),
        # 打包题库数据库
        ('app/static/qa_database.db', 'app/static'),
        # 打包 app 包的所有 Python 文件
        ('app/*.py', 'app'),
        ('app/routers/*.py', 'app/routers'),
        ('app/services/*.py', 'app/services'),
    ],
    hiddenimports=[
        # FastAPI / uvicorn
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'fastapi',
        'fastapi.middleware.cors',
        'fastapi.staticfiles',
        'fastapi.responses',
        # SQLAlchemy
        'sqlalchemy',
        'sqlalchemy.dialects.sqlite',
        # Pydantic
        'pydantic',
        'pydantic_settings',
        # PyMuPDF
        'fitz',
        # FSRS
        'fsrs',
        # 其他依赖
        'httpx',
        'numpy',
        'aiofiles',
        'multipart',
        # 项目内部模块
        'app',
        'app.main',
        'app.config',
        'app.database',
        'app.models',
        'app.schemas',
        'app.exam_models',
        'app.routers.pdf',
        'app.routers.questions',
        'app.routers.study',
        'app.routers.tags',
        'app.routers.exam',
        'app.services.pdf_service',
        'app.services.kimi_service',
        'app.services.fsrs_service',
        'app.services.agent_service',
        'app.services.answer_parser',
        'app.services.memory_service',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'PIL',
        'pandas',
        'scipy',
        'pytest',
        'IPython',
        'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='smart-qbank',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
