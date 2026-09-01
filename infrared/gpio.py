"""GPIO 公共工具：gpiochip 探测（供 lgpio 相关模块使用）。"""

from __future__ import annotations

import glob

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
    if not _HAS_LGPIO:
        raise RuntimeError(
            "未安装 lgpio。请在树莓派上安装: "
            "sudo apt install python3-lgpio  或  pip install lgpio"
        )
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
