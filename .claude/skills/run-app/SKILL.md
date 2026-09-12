---
name: run-app
description: 启动「电商知识库问答系统（LangChain RAG）」（后端 FastAPI + 前端 React）。当你被要求“打开 / 运行 / 启动应用”，或需要“验证某个改动在应用里的实际效果”时使用。
---

# 启动电商知识库问答系统

本项目是**浏览器访问的网页应用**，分前后端两个服务，两个都起来系统才能用：

- **后端**：Python + FastAPI，跑在 http://127.0.0.1:8000
- **前端**：React + Vite，跑在 http://localhost:5173（用户用浏览器打开这个地址）

## 启动方式

**最简单（推荐给用户）：** 双击项目根目录的 `start.bat`，它会依次：

1. 用虚拟环境里的 Python 启动后端（端口 8000）
2. 启动前端开发服务（端口 5173）
3. 等 4 秒后自动打开浏览器 http://localhost:5173

启动前确认两件事：

- 虚拟环境已装好：`venv\Scripts\python.exe` 存在；不存在就先跑 `setup.bat`。
- 前端依赖已装好：`frontend\node_modules` 存在；不存在就 `cd frontend && npm install`。

## 由 Claude 代为启动（命令行）

需要让服务保持运行时，**用后台方式**（Bash 工具 `run_in_background: true`），不要前台阻塞：

后端：

```bash
cd d:/LangChainRAG项目/backend
"../venv/Scripts/python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

前端：

```bash
cd d:/LangChainRAG项目/frontend
npm run dev
```

## 怎么判断启动成功

- 后端终端出现 `Uvicorn running on http://127.0.0.1:8000`
- 前端终端出现 `Local: http://localhost:5173/`
- 浏览器打开 http://localhost:5173 能看到登录页 = 全部成功

## 关闭应用

- 由 `start.bat` 启动的：用户关掉那两个服务窗口即可。
- 由 Claude 后台启动的：用 TaskStop 停掉对应后台任务。

## 注意事项 / 坑

- 后端需要 `backend/.env` 里的 `DASHSCOPE_API_KEY`（百炼密钥），缺了问答会失败。
- 端口被占（8000 / 5173）会导致启动失败——先关掉旧窗口，或看「重启服务」技能。
- 知识库数据在 `backend/data/`（向量库 + SQLite + 上传文件），不要随手删。