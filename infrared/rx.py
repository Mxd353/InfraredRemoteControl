"""红外接收器：通过红外接收头捕获遥控器信号，用于学习码库。

接收头（如 VS1838B）输出：收到 38kHz 载波时拉低，无信号时拉高。
通过监测 GPIO 边沿变化测量每个 mark/space 的时长，重建脉冲序列。

此模块用于"学习"：用原装空调遥控器对着接收头发射，记录下时序，
存进码库后即可由 IRTransmitter 重放。
"""

from __future__ import annotations

import time
from typing import Optional

try:
    import RPi.GPIO as GPIO  # type: ignore

    _HAS_GPIO = True
except ImportError:  # pragma: no cover
    _HAS_GPIO = False

from .raw import PulseSequence


class IRReceiver:
    """基于 RPi.GPIO 边沿中断的接收器。

    Args:
        gpio_pin:  连接红外接收头 OUT 的 GPIO（BCM 编号）。
        timeout_s: 无信号超时，判定一个完整帧结束。
    """

    def __init__(self, gpio_pin: int = 24, timeout_s: float = 0.05) -> None:
        if not _HAS_GPIO:
            raise RuntimeError("未安装 RPi.GPIO: sudo apt install python3-rpi.gpio")
        self.gpio_pin = gpio_pin
        self.timeout_s = timeout_s
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.gpio_pin, GPIO.IN)

    def capture(self, max_edges: int = 2000) -> Optional[PulseSequence]:
        """捕捉一次发射的完整脉冲序列。

        返回 None 表示超时未收到信号（例如按键时长过短）。
        """
        # 等待首个边沿（信号开始）
        start = time.monotonic()
        while True:
            if GPIO.input(self.gpio_pin) == 0:  # 载波状态 = 低
                break
            if time.monotonic() - start > 2.0:
                return None

        timestamps = [time.monotonic()]
        last_state = 0  # 0 = 低(载波)
        last_edge = time.monotonic()
        while len(timestamps) < max_edges:
            # 使用 poll 在宽松超时内等待边沿
            while True:
                state = GPIO.input(self.gpio_pin)
                now = time.monotonic()
                if state != last_state:
                    timestamps.append(now)
                    last_state = state
                    last_edge = now
                    break
                if now - last_edge > self.timeout_s:
                    # 超时，判定结束
                    return self._build(timestamps)
                time.sleep(1e-4)  # 100us 轮询
        return self._build(timestamps)

    @staticmethod
    def _build(timestamps) -> Optional[PulseSequence]:
        if len(timestamps) < 2:
            return None
        us_list = []
        for i in range(len(timestamps) - 1):
            d = (timestamps[i + 1] - timestamps[i]) * 1_000_000
            us_list.append(round(d))
        # 末尾补一个结束 mark 使长度为奇数（会话总是以 mark 结尾）
        us_list.append(100)  # 占位
        return PulseSequence(us_list)

    def cleanup(self) -> None:
        GPIO.cleanup()
