"""红外发送器：GPIO 输出 38kHz 载波调制。

无硬件调制的 IR LED 模块需要 GPIO 自行产生 38kHz 载波。
通过 PWM 实现载波，在"标记(mark)"期间开 PWM、在"间隙(space)"
期间关 PWM。

注意：
- 默认使用 pigpio 以得到稳定、精确至极微小秒级的时序。
  pigpio 的 wave 可在内核层面精确发射，避免 Python 抖动。
  安装: sudo apt install pigpio && sudo systemctl start pigpiod
- 若无法使用 pigpio，可回退到 RPi.GPIO 的 Software PWM（精度较差）。
"""

from __future__ import annotations

from typing import Optional, Sequence

from .raw import PulseSequence

CARRIER_HZ = 38_000  # 载波频率 38kHz

try:
    import pigpio  # type: ignore

    _HAS_PIGPIO = True
except ImportError:  # pragma: no cover
    _HAS_PIGPIO = False


class IRTransmitter:
    """基于 pigpio wave 的红外发射器。

    Args:
        gpio_pin: 连接 IR LED 模块 SIG 的 GPIO（默认 18，BCM 编号）。
        host:     pigpio 守护进程地址（默认本机）。
        carrier_hz: 载波频率。
    """

    def __init__(
        self,
        gpio_pin: int = 18,
        host: str = "127.0.0.1",
        carrier_hz: int = CARRIER_HZ,
    ) -> None:
        if not _HAS_PIGPIO:
            raise RuntimeError(
                "未安装 pigpio。请先: sudo apt install pigpio && "
                "sudo systemctl start pigpiod，然后 pip install pigpio"
            )
        self.gpio_pin = gpio_pin
        self.carrier_hz = carrier_hz
        self.pi = pigpio.pi(host)
        if not self.pi.connected:
            raise RuntimeError(
                f"无法连接 pigpiod({host})。请确认已启动服务: "
                "sudo systemctl start pigpiod"
            )

    def _build_wave(self, seq: PulseSequence) -> int:
        """根据时序构建 pigpio 波形，返回 wave_id。"""
        half_period = int(1_000_000 / (2 * self.carrier_hz))  # 半个载波周期 us
        marks = []
        pulses = []
        for i, us in enumerate(seq.us):
            if us <= 0:
                continue
            if i % 2 == 0:  # mark: 载波开启，即连续方波
                pulses.extend(
                    [
                        pigpio.pulse(
                            1 << self.gpio_pin,
                            0,
                            half_period,
                        ),
                        pigpio.pulse(
                            0,
                            1 << self.gpio_pin,
                            half_period,
                        ),
                    ]
                )
                marks.append(us)
            else:  # space: 载波关闭
                pulses.append(pigpio.pulse(0, 1 << self.gpio_pin, us))

        self.pi.wave_add_generic(pulses)
        return self.pi.wave_create()

    def send(self, seq: PulseSequence, repeat: int = 1, gap_us: int = 100_000) -> None:
        """发射脉冲序列。

        Args:
            seq:     要发送的时序。
            repeat:  重复发送次数（含首次）。
            gap_us:  每次重复之间的间隔，需大于整帧时长，避免粘连。
        """
        wave_id = self._build_wave(seq)
        try:
            for _ in range(repeat):
                self.pi.wave_send_once(wave_id)
                # 等待当前波形播放完毕
                while self.pi.wave_tx_busy():
                    pass
                if repeat > 1:
                    self._sleep_us(gap_us)
        finally:
            self.pi.wave_delete(wave_id)

    @staticmethod
    def _sleep_us(us: int) -> None:
        # pigpio 的 wave_send_once 后需等待完整间隙
        import time

        time.sleep(us / 1_000_000)

    def close(self) -> None:
        """清理 GPIO 与 pigpio 连接。"""
        if hasattr(self, "pi") and self.pi.connected:
            self.pi.wave_clear()
            self.pi.stop()

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.close()
