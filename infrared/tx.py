"""红外发送器：GPIO 输出 38kHz 载波调制（基于 pigpio DMA 波形）。

无硬件调制的 IR LED 模块需要 GPIO 自行产生 38kHz 载波。
本模块使用 pigpio 的 wave 功能发射：
- mark 段：连续高低电平脉冲形成 38kHz 方波
- space 段：GPIO 保持低电平

关键：pigpio 的 wave 由 DMA 硬件在内核级播放，微秒级时序精度，
是树莓派上红外发射的标准方案（lgpio 的软件定时 wave 抖动太大，
实测会导致 38kHz 载波断续、接收头无法解调）。

需要运行 pigpiod 守护进程:
    sudo apt install pigpio
    sudo systemctl enable pigpiod
    sudo systemctl start pigpiod
"""

from __future__ import annotations

from typing import List, Optional

from .raw import PulseSequence

CARRIER_HZ = 38_000  # 载波频率 38kHz

try:
    import pigpio  # type: ignore

    _HAS_PIGPIO = True
except ImportError:  # pragma: no cover
    _HAS_PIGPIO = False


class IRTransmitter:
    """基于 pigpio DMA 波形功能的红外发射器。

    Args:
        gpio_pin:   连接 IR LED 模块 SIG 的 GPIO（BCM 编号，默认 18）。
        host:       pigpiod 守护进程地址（默认本机）。
        carrier_hz: 载波频率（默认 38kHz）。
    """

    def __init__(
        self,
        gpio_pin: int = 18,
        host: str = "127.0.0.1",
        carrier_hz: int = CARRIER_HZ,
    ) -> None:
        if not _HAS_PIGPIO:
            raise RuntimeError(
                "未安装 pigpio。请在树莓派上安装: "
                "sudo apt install pigpio python3-pigpio"
            )
        self.gpio_pin = gpio_pin
        self.carrier_hz = carrier_hz
        self.pi = pigpio.pi(host)
        if not self.pi.connected:
            raise RuntimeError(
                f"无法连接 pigpiod({host})。请启动守护进程: "
                "sudo systemctl start pigpiod"
            )

    def _build_wave(self, seq: PulseSequence) -> int:
        """根据时序构建 pigpio 波形，返回 wave_id。

        pigpio 的 pulse(gpio_on, gpio_off, delay) 使用 GPIO 位掩码，
        mark 段填充 38kHz 方波，space 段保持低电平。
        """
        half_period = max(1, round(1_000_000 / (2 * self.carrier_hz)))
        on = 1 << self.gpio_pin
        off = 1 << self.gpio_pin
        pulses = []
        for i, us in enumerate(seq.us):
            if us <= 0:
                continue
            if i % 2 == 0:
                # mark: 载波开启，发送连续方波
                full_cycles = us // (2 * half_period)
                for _ in range(full_cycles):
                    pulses.append(pigpio.pulse(on, 0, half_period))
                    pulses.append(pigpio.pulse(0, off, half_period))
                rem = us - full_cycles * 2 * half_period
                if rem > 0:
                    pulses.append(pigpio.pulse(on, 0, rem))
            else:
                # space: 载波关闭，保持低电平
                pulses.append(pigpio.pulse(0, off, us))

        self.pi.wave_add_generic(pulses)
        wave_id = self.pi.wave_create()
        if wave_id < 0:
            raise RuntimeError(f"wave_create 失败: {wave_id}")
        return wave_id

    def send(self, seq: PulseSequence, repeat: int = 1, gap_us: int = 100_000) -> None:
        """发射脉冲序列。

        Args:
            seq:     要发送的时序。
            repeat:  重复发送次数（含首次）。
            gap_us:  每次重复之间的间隔。
        """
        wave_id = self._build_wave(seq)
        try:
            for i in range(repeat):
                self.pi.wave_send_once(wave_id)
                while self.pi.wave_tx_busy():
                    pass
                if i < repeat - 1:
                    import time

                    time.sleep(gap_us / 1_000_000)
        finally:
            self.pi.wave_delete(wave_id)

    def close(self) -> None:
        """清理波形并断开 pigpio 连接。"""
        if not hasattr(self, "pi"):
            return
        try:
            self.pi.wave_clear()
        except Exception:
            pass
        try:
            self.pi.stop()
        except Exception:
            pass

    def __enter__(self) -> "IRTransmitter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
