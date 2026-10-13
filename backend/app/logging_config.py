"""日志初始化：统一全项目的日志格式与级别。

项目此前没有任何日志，出错时只能靠静默 `except` 吞掉，排查问题非常困难。
统一在应用启动时调用 `setup_logging()`，各处再用 `logging.getLogger(__name__)`
拿 logger 即可，无需关心格式与输出目标。
"""

import logging
import sys

_LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    """配置根日志器（幂等：重复调用不会重复挂 handler）。

    Args:
        level: 根日志器的级别，默认 INFO。
    """
    root = logging.getLogger()
    if root.handlers:  # 已被配置过（例如测试或 uvicorn 已初始化），不重复添加
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    root.addHandler(handler)
    root.setLevel(level)
