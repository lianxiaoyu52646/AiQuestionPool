# 📚 智能题库系统 (Smart Question Bank)

> 基于 FSRS 间隔重复算法的执业药师智能题库学习系统，支持真题模考、智能刷题、PDF 题目提取。

## ✨ 功能特性

### 📝 题库学习
- **FSRS 智能复习算法**：根据遗忘曲线自动调度复习时间，高效记忆
- **多维度筛选**：按章节、标签、难度筛选题目
- **学习进度统计**：掌握度、复习次数、正确率一目了然
- **标签管理**：错题、重点、已掌握等自定义标签

### 📝 真题模考
- **21 套历年真题**：覆盖 2020-2026 年中药学执业药师考试
  - 中药学专业知识（一）
  - 中药学专业知识（二）
  - 中药学综合知识与技能
- **全真模拟**：计时考试、自动评分、答案解析
- **模考记录**：历史成绩追踪，薄弱点分析

### 📄 PDF 题目提取（可选）
- 上传 PDF 试卷，AI 自动提取结构化题目
- 支持题型识别（单选、多选、配伍题等）
- 自动匹配答案与解析

### 📊 统计分析
- 学习数据可视化
- 复习热力图
- 薄弱章节分析

## 🚀 快速开始

### 方式一：EXE 直接运行（推荐，无需安装任何环境）

1. 下载 `smart-qbank.exe`（56MB）
2. 双击运行
3. 浏览器自动打开 `http://localhost:8000`

> 首次运行会自动释放数据库和前端文件，之后秒启动。

### 方式二：源码运行（需 Python 3.10+）

1. 下载项目代码
```bash
git clone https://github.com/lianxiaoyu52646/AiQuestionPool.git
cd AiQuestionPool
```

2. 双击 `start.bat`（Windows）
   - 首次运行自动创建虚拟环境并安装依赖（需联网，约1-2分钟）
   - 之后秒启动

或手动启动：
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

3. 浏览器访问 `http://localhost:8000`

## 📦 打包为 EXE

```bash
# 安装 PyInstaller
pip install pyinstaller

# 在 backend 目录下执行
cd backend
pyinstaller smart_qbank.spec --noconfirm

# 生成文件：dist/smart-qbank.exe
```

## 🏗️ 技术架构

| 组件 | 技术 | 说明 |
|------|------|------|
| 后端框架 | FastAPI | 高性能异步 Python Web 框架 |
| 数据库 | SQLite + SQLAlchemy | 零配置文件型数据库 |
| 前端框架 | Vue 3 + Vite | 渐进式 JavaScript 框架 |
| UI 样式 | Tailwind CSS | 原子化 CSS 框架 |
| 间隔重复 | FSRS 算法 | 基于 Free Spaced Repetition Scheduler |
| AI 解析 | GLM API（可选） | 用于 PDF 题目智能提取 |
| PDF 解析 | PyMuPDF | 高性能 PDF 文本提取 |
| 打包分发 | PyInstaller | 打包为单文件 EXE |

## 📁 项目结构

```
AiQuestionPool/
├── start.bat                    # 一键启动脚本
├── requirements.txt             # Python 依赖
├── .env.example                 # 环境变量模板（可选）
├── README.md                    # 项目说明（本文件）
├── README-DEPLOY.md             # 详细部署文档
│
├── backend/                     # 后端
│   ├── run.py                   # 启动入口
│   ├── run_exe.py               # EXE 打包入口
│   ├── smart_qbank.spec         # PyInstaller 配置
│   ├── crawl_233_multiagent.py  # 题库爬虫
│   └── app/
│       ├── main.py              # FastAPI 应用入口
│       ├── config.py            # 配置管理
│       ├── database.py          # 数据库连接
│       ├── models.py            # 数据模型（题目、分类、标签等）
│       ├── exam_models.py       # 模考数据模型
│       ├── schemas.py           # Pydantic 数据模式
│       ├── routers/             # API 路由
│       │   ├── pdf.py           # PDF 上传与解析
│       │   ├── questions.py     # 题目管理
│       │   ├── study.py         # 学习与复习
│       │   ├── tags.py          # 标签管理
│       │   └── exam.py          # 真题模考
│       ├── services/            # 业务服务
│       │   ├── pdf_service.py   # PDF 处理
│       │   ├── kimi_service.py  # AI API 服务
│       │   ├── fsrs_service.py  # FSRS 间隔重复
│       │   ├── agent_service.py # 多 Agent 并行解析
│       │   ├── answer_parser.py # 答案解析
│       │   └── memory_service.py # Agent 记忆管理
│       └── static/
│           ├── dist/            # 前端构建产物
│           ├── qa_database.db   # 题库数据库
│           └── uploads/         # 上传文件目录
│
└── frontend/                    # 前端
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    └── src/
        ├── App.vue              # 根组件
        ├── router.js            # 路由配置
        ├── api/index.js         # API 请求封装
        ├── stores/studyStore.js # Pinia 状态管理
        └── views/
            ├── Home.vue         # 首页
            ├── Questions.vue    # 题库浏览
            ├── Exam.vue         # 真题模考
            ├── Stats.vue        # 统计分析
            ├── Upload.vue       # PDF 上传
            └── PDFView.vue      # PDF 查看
```

## ⚙️ 可选配置：AI 解析功能

题库浏览、真题模考、FSRS 刷题学习 **不需要** AI API，开箱即用。

如需使用 **PDF 上传 + AI 自动提取题目** 功能：

1. 复制 `.env.example` 为 `.env`
2. 填入 AI API 配置：
```env
UPSTREAM_API_KEY=你的API密钥
UPSTREAM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
MODEL_NAME=glm-4
```

## 📊 题库数据

| 科目 | 年份范围 | 题目数量 |
|------|----------|----------|
| 中药学专业知识（一） | 2020-2026 | ~230题 |
| 中药学专业知识（二） | 2020-2025 | ~230题 |
| 中药学综合知识与技能 | 2020-2025 | ~230题 |
| **合计** | | **694题** |

> 含 21 套历年真题 + 模拟试卷

## 🔧 开发指南

### 前端开发
```bash
cd frontend
npm install
npm run dev    # 开发服务器 (http://localhost:5173)
npm run build  # 构建到 backend/app/static/dist/
```

### 后端开发
```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

### API 文档
启动后访问 `http://localhost:8000/docs` 查看 Swagger 文档

## ❓ 常见问题

**Q: 双击 exe 后没反应？**
A: 首次启动需要几秒钟解压文件，请等待终端显示 "Uvicorn running" 后再访问

**Q: 提示端口被占用？**
A: 关闭其他占用 8000 端口的程序，或修改启动参数中的端口号

**Q: 数据会丢失吗？**
A: 不会。数据库在 exe 同级目录的 `app/static/qa_database.db`，关闭程序后数据保留

**Q: 如何更新题库？**
A: 通过 PDF 上传功能导入新试卷（需配置 AI API），或直接替换数据库文件

## 📄 License

MIT License

## 🤝 贡献

欢迎提交 Issue 或 Pull Request
