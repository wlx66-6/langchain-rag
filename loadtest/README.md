# loadtest：压测脚本使用说明

这套脚本用 **Locust** 模拟「大量用户同时访问问答系统」，测出系统的**承载能力**。

**Locust 是什么（大白话）**：它是一个 Python 写的压测工具。你在本机开一个「指挥中心」，它按你设定的人数派出一堆「**虚拟用户**」，这些虚拟用户就像真实的访问者一样，不停地登录、提问、翻看会话。成百上千个虚拟用户一起上，就能测出系统在「同时被很多人用」时的表现——这正是毕设要证明的「企业级承载能力」。

## 目录里都有啥

| 文件 | 作用 |
|---|---|
| `locustfile.py` | 压测场景脚本（每个虚拟用户会做什么） |
| `requirements.txt` | 依赖清单（就一个 `locust`） |
| `seed_users.py` | （可选）批量注册 100 个不同账号 |
| `report_*.html` / `results_*.csv` | 跑完后自动生成的报告和数据（可直接写进论文） |

## 准备：装依赖 + 起后端

1. **装 locust**（装进项目自带环境，只装一次）：
   ```
   venv\Scripts\python.exe -m pip install -r loadtest\requirements.txt
   ```
2. **起后端**：按 `start.bat` 正常启动即可（默认在 `http://127.0.0.1:8000`）。

## 两轮压测（关键：同一份脚本，靠后端启动方式区分）

### 轮 A｜真实端到端（少量真大模型，拿「真实响应时间」）

后端**正常**启动（**不**设 `MOCK_LLM`），用 5~10 个用户小规模跑，得到含大模型在内的真实响应时间：

```
cd loadtest
..\venv\Scripts\python.exe -m locust -f locustfile.py --host http://127.0.0.1:8000 --users 8 --spawn-rate 2 --run-time 2m --headless --csv=results_real --html=report_real.html
```

### 轮 B｜100 人骨架（假大模型，专测系统自身承受力）

后端用**假大模型模式**启动（见下一节），用 100 个用户压系统的「骨架」（数据库 + 检索），不花钱、不被百炼限流干扰：

```
cd loadtest
..\venv\Scripts\python.exe -m locust -f locustfile.py --host http://127.0.0.1:8000 --users 100 --spawn-rate 10 --run-time 3m --headless --csv=results_mock --html=report_mock.html
```

**命令里几个参数是啥意思（大白话）**：
- `--users 100`：同时有 100 个虚拟用户在线；
- `--spawn-rate 10`：每秒新增 10 个用户，慢慢冲上去（而不是 100 个一窝蜂上来，那样不真实）；
- `--run-time 3m`：跑 3 分钟；
- `--headless`：不弹网页界面，直接在命令行跑完出结果；
- `--csv=xxx` / `--html=xxx.html`：把结果和数据落到文件里。

## 怎么开「假大模型」模式（轮 B 用）

后端启动前设置环境变量 `MOCK_LLM=1`，问答接口就会改用假模型、跳过远程重排，只跑本地骨架：

- **Windows CMD**：`set MOCK_LLM=1` 之后再启动后端；
- **Git Bash / Linux**：`MOCK_LLM=1 uvicorn ...`（或先 `export MOCK_LLM=1`）。

想恢复正常：去掉这个环境变量重启后端即可（开关默认关闭，不影响日常使用）。

## 可选：100 个不同账号

默认脚本里所有虚拟用户都**共用演示账号 `itheima/123456`**（压系统骨架完全够用）。若论文要「100 个不同用户同时在线」的证据：

1. 先注册 100 个账号：
   ```
   cd loadtest
   ..\venv\Scripts\python.exe seed_users.py 100
   ```
2. 再用 `LOADTEST_DISTINCT_USERS=1` 启动 Locust（每个虚拟用户自动用 `loaduser001~100` 登录）：
   ```
   ..\venv\Scripts\python.exe -m locust -f locustfile.py --host http://127.0.0.1:8000 --users 100 --spawn-rate 10 --run-time 3m --headless --csv=results_mock --html=report_mock.html
   ```
   （命令前面加一句 `set LOADTEST_DISTINCT_USERS=1`，Git Bash 用 `LOADTEST_DISTINCT_USERS=1`。）

## 看懂结果

Locust 跑完会打印一串关键数字，可以直接写进论文：

- **Requests / RPS**：每秒处理了多少个请求（吞吐量，越大越好）；
- **失败数 / 失败率**：多少请求出错了（越接近 0 越好）；
- **平均 / 最小 / 最大响应时间**：一次请求从发出到完成用多久；
- **P50 / P95 / P99**：有 50% / 95% / 99% 的请求都在这个时间内完成。**P99 最能反映「最慢的那批用户等多久」**，是论文里很有说服力的一项。

## 注意（诚实声明）

- 压测是**本机自测**（Locust 客户端和你被测的后端在同一台电脑上），报告里要如实说明这一点；若要更干净的数字，可另找一台电脑跑 Locust 指向这台后端。
- 压测会在数据库里产生**大量会话/消息记录**，测完可备份或清理。