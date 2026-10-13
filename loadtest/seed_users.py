"""（可选）批量预注册 100 个压测账号 loaduser001~100。

默认的压测脚本（locustfile.py）用单个共享账号，不需要跑这个脚本。
若想模拟「100 个不同用户同时在线」：
    1) 先跑本脚本注册账号：  ..\\venv\\Scripts\\python.exe seed_users.py 100
    2) 再用 LOADTEST_DISTINCT_USERS=1 启动 Locust（每个虚拟用户自动用不同账号）。

用法：python seed_users.py [数量，默认 100]
"""
import sys

import requests

HOST = "http://127.0.0.1:8000"
PASSWORD = "LoadTest123"  # 与 locustfile.py 里的 _SEED_PASSWORD 保持一致


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    ok = fail = 0
    for i in range(1, n + 1):
        username = f"loaduser{i:03d}"
        try:
            r = requests.post(
                f"{HOST}/api/auth/register",
                json={"username": username, "password": PASSWORD},
                timeout=10,
            )
        except requests.RequestException as exc:
            fail += 1
            print(f"网络异常 {username}：{exc}")
            continue
        if r.status_code == 201:
            ok += 1
        elif r.status_code == 400 and "占用" in (r.json().get("detail") or ""):
            ok += 1  # 已经注册过也算就绪，可重复执行本脚本
        else:
            fail += 1
            print(f"注册失败 {username}：HTTP {r.status_code} {r.text}")
    print(f"完成：{ok} 个账号就绪，失败 {fail} 个")


if __name__ == "__main__":
    main()