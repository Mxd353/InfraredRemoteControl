"""红外发送器：GPIO 输出 38kHz 载波调制（基于 lgpio）。

无硬件调制的 IR LED 模块需要 GPIO 自行产生 38kHz 载波。
本模块使用 lgpio 库的波形功能（tx_wave）发射：
- mark 段：连续高低电平脉冲形成 38kHz 方波
- space 段：GPIO 保持低电平

注意：
- lgpio 由 pigpio 作者维护，直接操作 /dev/gpiochip*，无需守护进程。
- 树莓派 5 的 GPIO 位于 /dev/gpiochip4（Pi 4 及更早为 gpiochip0），
  本模块会自动探测 GPIO 所属的 gpiochip。
- 本机无需运行，直接部署到树莓派即可。
"""

from __future__ import annotations

import glob
import time
from typing import List, Optional

from .raw import PulseSequence

CARRIER_HZ = 38_000  # 载波频率 38kHz

try:
    import lgpio

    _HAS_LGPIO = True
except ImportError:  # pragma: no cover
    _HAS_LGPIO = False


def _find_gpiochip(gpio: int) -> int:
    """在 /dev/gpiochip* 中查找 GPIO 所属的 gpiochip 编号。

    树莓派 4B 及更早: GPIO 18 在 /dev/gpiochip0
    树莓派 5:        GPIO 18 在 /dev/gpiochip4
    """
    devices = sorted(glob.glob("/dev/gpiochip*"))
    if not devices:
        raise RuntimeError(
            "未找到 /dev/gpiochip* 设备。请确认运行在树莓派上且具备权限。"
        )
    for dev in devices:
        try:
            num = int(dev.rsplit("chip", 1)[1])
        except ValueError:
            continue
        h = lgpio.gpiochip_open(num)
        try:
            try:
                info = lgpio.gpio_get_line_info(h, gpio)
                if info[0] >= 0:
                    return num
            except Exception:
                pass
        finally:
            lgpio.gpiochip_close(h)
    raise RuntimeError(f"GPIO{gpio} 未在任何 /dev/gpiochip* 中找到")


class IRTransmitter:
    """基于 lgpio 波形功能的红外发射器。

    Args:
        gpio_pin:   连接 IR LED 模块 SIG 的 GPIO（BCM 编号，默认 18）。
        chip:       gpiochip 编号。None 时自动探测（推荐）。
        carrier_hz: 载波频率（默认 38kHz）。
    """

    def __init__(
        self,
        gpio_pin: int = 18,
        chip: Optional[int] = None,
        carrier_hz: int = CARRIER_HZ,
    ) -> None:
        if not _HAS_LGPIO:
            raise RuntimeError(
                "未安装 lgpio。请在树莓派上安装: "
                "sudo apt install python3-lgpio  或  pip install lgpio"
            )
        self.gpio_pin = gpio_pin
        self.carrier_hz = carrier_hz
        self.chip_num = chip if chip is not None else _find_gpiochip(gpio_pin)

        self.h = lgpio.gpiochip_open(self.chip_num)
        if self.h < 0:
            raise RuntimeError(f"无法打开 /dev/gpiochip{self.chip_num}")
        lgpio.gpio_claim_output(self.h, gpio_pin, 0)

    def _build_pulses(self, seq: PulseSequence) -> List:
        """将时序转换为 lgpio.pulse 列表（mark 段填充 38kHz 载波）。

        lgpio 的 wave 使用"组内偏移位"作为 mask（bit 0 = 组内第一个 GPIO）。
        单 GPIO 声明为一个单成员组，因此 mask 固定为 1（偏移 0），
        而不是 1 << gpio_pin —— 否则 xGroupWrite 无法匹配任何位，
        GPIO 将一直保持低电平（这就是之前"步骤1亮、步骤2不亮"的原因）。
        """
        half_period = max(1, round(1_000_000 / (2 * self.carrier_hz)))
        mask = 1  # 组内偏移位：bit 0 = 单成员组的唯一 GPIO
        pulses: List = []
        for i, us in enumerate(seq.us):
            if us <= 0:
                continue
            if i % 2 == 0:
                # mark: 载波开启，发送连续方波
                full_cycles = us // (2 * half_period)
                for _ in range(full_cycles):
                    pulses.append(lgpio.pulse(mask, mask, half_period))
                    pulses.append(lgpio.pulse(0, mask, half_period))
                rem = us - full_cycles * 2 * half_period
                if rem > 0:
                    pulses.append(lgpio.pulse(mask, mask, rem))
            else:
                # space: 载波关闭，保持低电平
                pulses.append(lgpio.pulse(0, mask, us))
        return pulses

    def send(self, seq: PulseSequence, repeat: int = 1, gap_us: int = 100_000) -> None:
        """发射脉冲序列。

        Args:
            seq:     要发送的时序。
            repeat:  重复发送次数（含首次）。
            gap_us:  每次重复之间的间隔。
        """
        pulses = self._build_pulses(seq)
        for i in range(repeat):
            lgpio.tx_wave(self.h, self.gpio_pin, pulses)
            while lgpio.tx_busy(self.h, self.gpio_pin, lgpio.TX_WAVE) == 1:
                pass
            if i < repeat - 1:
                time.sleep(gap_us / 1_000_000)

    def close(self) -> None:
        """释放 GPIO 并关闭 gpiochip。"""
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

    def __enter__(self) -> "IRTransmitter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
