"""Locust 压测脚本：模拟大量并发用户在问答系统上的真实行为。

用法（详见 loadtest/README.md）：
    cd loadtest
    ..\\venv\\Scripts\\python.exe -m locust -f locustfile.py --host http://127.0.0.1:8000 --users 100 --spawn-rate 10 --run-time 3m --headless --csv=results_mock --html=report_mock.html

每个「虚拟用户」会先登录拿令牌，然后按权重循环做三件事：
  提问（85%）、查会话列表（10%）、健康检查（5%）。
"""
import itertools
import json
import os
import random
from time import perf_counter

from locust import HttpUser, between, task

# ===== 账号配置 =====
# 默认：所有虚拟用户共用一个演示账号 itheima/123456（最简单，压系统骨架完全够用）。
# 若论文要「100 个不同账号同时用」的证据：先跑 seed_users.py 注册 loaduser001~100，
# 再设环境变量 LOADTEST_DISTINCT_USERS=1 启动，每个虚拟用户会自动用不同账号登录。
USERNAME = os.environ.get("LOADTEST_USERNAME", "itheima")
PASSWORD = os.environ.get("LOADTEST_PASSWORD", "123456")
DISTINCT_USERS = os.environ.get("LOADTEST_DISTINCT_USERS") == "1"
_SEED_PASSWORD = "LoadTest123"  # 与 seed_users.py 保持一致

_counter = itertools.count(1)  # 「100 个不同账号」模式下的自增编号

# ===== 一组贴近知识库的问题（尺码 / 洗涤养护 / 颜色） =====
QUESTIONS = [
    "这件衣服我该选什么尺码？",
    "身高175体重70公斤，穿多大码比较合适？",
    "毛衣怎么洗才不容易起球？",
    "牛仔裤第一次洗会掉色吗？",
    "这件衣服有哪几种颜色可以选？",
    "白色衣服穿久了发黄，怎么处理？",
    "这件衣服适合什么身材的人穿？",
    "羽绒服可以机洗吗？",
]


class ShopUser(HttpUser):
    # 每个虚拟用户每次操作之间随机歇 1~3 秒，模拟真人的节奏。
    # 想压得更狠，可以把(1, 3)改小，比如(0.5, 1.5)。
    wait_time = between(1, 3)

    def on_start(self):
        """登录拿访问令牌（每个虚拟用户启动时执行一次）。"""
        username, password = USERNAME, PASSWORD
        if DISTINCT_USERS:
            username = f"loaduser{next(_counter):03d}"
            password = _SEED_PASSWORD
        resp = self.client.post(
            "/api/auth/login", json={"username": username, "password": password}
        )
        if resp.status_code == 200:
            self.token = resp.json().get("access_token")
        else:
            raise RuntimeError(f"登录失败（{username}）：HTTP {resp.status_code}")

    @property
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    @task(85)
    def ask_question(self):
        """核心场景：提一个问题，读完整个流式回答才计时结束、才算成功。

        conversation_id 传 None = 每次都新建会话，走「建会话 + 存提问 + 检索 +
        生成 + 存回答」的完整链路，最能暴露数据库写锁、线程池这些真瓶颈。
        """
        body = {"conversation_id": None, "content": random.choice(QUESTIONS)}
        start = perf_counter()  # 手动计时：读完整个流后，覆盖默认的「只计到响应头」
        with self.client.post(
            "/api/chat",
            json=body,
            headers=self._headers,
            stream=True,
            catch_response=True,
            timeout=60,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}")
                return
            saw_done = False
            error_msg = None
            try:
                for raw in resp.iter_lines():
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="ignore")
                    if not line.startswith("data: "):
                        continue
                    try:
                        event = json.loads(line[len("data: "):])
                    except ValueError:
                        continue
                    if event.get("type") == "done":
                        saw_done = True
                    elif event.get("type") == "error":
                        error_msg = event.get("data")
            except Exception as exc:  # 网络中断 / 连接被重置等
                resp.failure(f"读取流式回答异常：{exc}")
                return
            # 关键：stream=True 时 requests 在「收到响应头」时就返回，Locust 默认只计到那里，
            # 会漏掉后面大模型流式生成的时间。这里把计时覆盖成「读完整个流」的真实耗时。
            resp.request_meta["response_time"] = (perf_counter() - start) * 1000
            if error_msg:
                resp.failure(f"服务端返回 error：{error_msg}")
            elif not saw_done:
                resp.failure("流式回答未收到 done 事件（可能被提前断开）")

    @task(10)
    def list_conversations(self):
        self.client.get("/api/conversations", headers=self._headers)

    @task(5)
    def health(self):
        self.client.get("/api/health")