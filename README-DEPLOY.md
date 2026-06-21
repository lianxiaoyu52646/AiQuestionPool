# 智能题库系统 - 部署使用说明

## 🚀 快速开始（给使用者）

### 环境要求
- **Windows** 系统
- **Python 3.10+**（安装时勾选 "Add Python to PATH"）
  - 下载地址：https://www.python.org/downloads/

### 启动步骤
1. 解压项目 zip 到任意目录
2. 双击运行 `start.bat`
3. 首次运行会自动创建虚拟环境并安装依赖（需要联网，约1-2分钟）
4. 安装完成后自动启动服务
5. 浏览器打开 **http://localhost:8000** 即可使用

### 日常使用
- 以后每次使用只需双击 `start.bat`，秒启动
- 按 `Ctrl+C` 停止服务

---

## 📦 打包分发方法

### 需要包含的文件/目录
```
项目根目录/
├── start.bat              ← 一键启动脚本
├── requirements.txt       ← Python 依赖
├── .env.example           ← 环境变量模板（可选）
├── backend/
│   ├── app/               ← 后端代码 + 已构建的前端 + 数据库
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── exam_models.py
│   │   ├── routers/
│   │   ├── services/
│   │   └── static/
│   │       ├── dist/      ← 前端构建产物（已包含）
│   │       ├── qa_database.db  ← 题库数据库（已包含）
│   │       └── uploads/
│   └── run.py
└── frontend/              ← 前端源码（可选，使用者不需要）
```

### 不需要包含的
- `venv/` — 虚拟环境，start.bat 会自动创建
- `node_modules/` — 前端依赖，已构建到 dist 中
- `__pycache__/` — Python 缓存
- `backend/downloads/` — 下载的临时文件
- `backend/*.json` — 爬虫备份数据（可选保留）

### 打包命令
```powershell
# 在项目根目录执行
# 排除不需要的大目录
Compress-Archive -Path start.bat,requirements.txt,.env.example,backend,frontend -DestinationPath smart-qbank.zip -Force
```

---

## ⚙️ 可选配置：AI 解析功能

题库浏览、真题模考、FSRS 刷题学习 **不需要** AI API，开箱即用。

如需使用 **PDF 上传 + AI 自动提取题目** 功能：

1. 复制 `.env.example` 为 `.env`
2. 填入 AI API 配置：
```
UPSTREAM_API_KEY=你的API密钥
UPSTREAM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
MODEL_NAME=glm-4
```

---

## 🔧 技术架构

| 组件 | 技术 | 说明 |
|------|------|------|
| 后端 | FastAPI + SQLAlchemy | Python Web 框架 |
| 数据库 | SQLite | 零配置，文件型数据库 |
| 前端 | Vue 3 + Tailwind CSS | 已构建为静态文件 |
| 间隔重复 | FSRS 算法 | 智能复习调度 |
| AI 解析 | GLM API（可选） | PDF 题目提取 |

---

## ❓ 常见问题

**Q: 启动时提示"未找到 Python"**
A: 需要先安装 Python 3.10+，安装时务必勾选 "Add Python to PATH"

**Q: 首次启动很慢**
A: 首次需要下载依赖包，之后启动秒开

**Q: 浏览器打不开**
A: 确认终端显示"Application startup complete"后再访问 http://localhost:8000

**Q: 端口被占用**
A: 编辑 `start.bat`，将 `--port 8000` 改为其他端口如 `--port 9000`
