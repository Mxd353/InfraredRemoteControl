"""红外接收器：通过红外接收头捕获遥控器信号，用于学习码库。

接收头（如 VS1838B）输出：收到 38kHz 载波时拉低，无信号时拉高。
通过 lgpio 的边沿告警回调（带纳秒时间戳）测量每个 mark/space
的时长，重建脉冲序列。

此模块用于"学习"：用原装空调遥控器对着接收头发射，记录下时序，
存进码库后即可由 IRTransmitter 重放。

与发送端一样，本模块直接操作 /dev/gpiochip*，无需守护进程，
且会自动探测 GPIO 所属的 gpiochip（树莓派 5 为 gpiochip4）。
"""

from __future__ import annotations

import time
from typing import List, Optional, Tuple

from .raw import PulseSequence
from .tx import _find_gpiochip

try:
    import lgpio

    _HAS_LGPIO = True
except ImportError:  # pragma: no cover
    _HAS_LGPIO = False


class IRReceiver:
    """基于 lgpio 边沿告警回调的接收器。

    Args:
        gpio_pin:  连接红外接收头 OUT 的 GPIO（BCM 编号，默认 24）。
        chip:      gpiochip 编号。None 时自动探测（推荐）。
        timeout_s: 无信号超时，判定一个完整帧结束。
    """

    def __init__(
        self,
        gpio_pin: int = 24,
        chip: Optional[int] = None,
        timeout_s: float = 0.05,
    ) -> None:
        if not _HAS_LGPIO:
            raise RuntimeError(
                "未安装 lgpio。请在树莓派上安装: "
                "sudo apt install python3-lgpio  或  pip install lgpio"
            )
        self.gpio_pin = gpio_pin
        self.timeout_s = timeout_s
        self.chip_num = chip if chip is not None else _find_gpiochip(gpio_pin)

        self.h = lgpio.gpiochip_open(self.chip_num)
        if self.h < 0:
            raise RuntimeError(f"无法打开 /dev/gpiochip{self.chip_num}")
        # 声明为输入并启用双边沿告警，上拉避免悬空抖动
        lgpio.gpio_claim_alert(
            self.h, gpio_pin, lgpio.BOTH_EDGES, lFlags=lgpio.SET_PULL_UP
        )
        self._edges: List[Tuple[int, int]] = []  # (level, timestamp_ns)
        self._cb = None

    def _on_edge(self, chip: int, gpio: int, level: int, timestamp: int) -> None:
        """边沿回调：记录电平与单调时钟纳秒时间戳。

        注意：不用 lgpio 提供的 timestamp（其时钟源因内核而异，
        可能是 since-boot 或 epoch），统一改用 time.monotonic_ns()，
        与超时判断保持一致。
        """
        self._edges.append((level, time.monotonic_ns()))

    def capture(self, max_edges: int = 2000) -> Optional[PulseSequence]:
        """捕捉一次发射的完整脉冲序列。

        返回 None 表示超时未收到信号（例如按键时长过短）。
        """
        self._edges = []
        self._cb = lgpio.callback(
            self.h, self.gpio_pin, lgpio.BOTH_EDGES, self._on_edge
        )

        # 等待首个边沿（信号开始），最多等 2 秒
        deadline = time.monotonic() + 2.0
        while not self._edges and time.monotonic() < deadline:
            time.sleep(0.005)
        if not self._edges:
            self._cancel()
            return None

        # 等待最后边沿后超时（判定帧结束）
        while True:
            if not self._edges:
                time.sleep(0.005)
                continue
            last_ns = self._edges[-1][1]
            if time.monotonic_ns() - last_ns > self.timeout_s * 1_000_000_000:
                break
            if len(self._edges) >= max_edges:
                break
            time.sleep(0.002)

        seq = self._build()
        self._cancel()
        return seq

    def _build(self) -> Optional[PulseSequence]:
        """将边沿时间戳列表转换为 PulseSequence。"""
        if len(self._edges) < 2:
            return None
        us_list = []
        prev_ns = self._edges[0][1]
        for _, ts_ns in self._edges[1:]:
            us_list.append(round((ts_ns - prev_ns) / 1_000))
            prev_ns = ts_ns
        # 序列以 mark 开始；若以 space 结尾（帧间间隙），丢弃末段
        if len(us_list) % 2 == 0:
            us_list = us_list[:-1]
        if len(us_list) < 3:
            return None
        return PulseSequence(us_list)

    def _cancel(self) -> None:
        if self._cb is not None:
            self._cb.cancel()
            self._cb = None

    def cleanup(self) -> None:
        """取消回调、释放 GPIO 并关闭 gpiochip。"""
        self._cancel()
        if not hasattr(self, "h"):
            return
        try:
            lgpio.gpio_free(self.h, self.gpio_pin)
        except Exception:
            pass
        try:
            lgpio.gpiochip_close(self.h)
        except Exception:
            pass
