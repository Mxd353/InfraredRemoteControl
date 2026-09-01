#!/usr/bin/env python3
"""红外发射器诊断脚本（在树莓派上运行）。

逐步定位发射不工作的问题：
  步骤1: 检查 lgpio 版本与 gpiochip 探测
  步骤2: GPIO 写高电平 —— 验证接线与基本 GPIO 输出
  步骤3: tx_wave 发送 38kHz 载波 —— 验证波形发射

用法: python3 examples/diag_tx.py [GPIO号]
"""

import sys
import time

try:
    import lgpio
except ImportError:
    print("❌ lgpio 未安装，请先: sudo apt install python3-lgpio")
    sys.exit(1)

sys.path.insert(0, "")
from infrared.tx import _find_gpiochip  # noqa: E402

GPIO = int(sys.argv[1]) if len(sys.argv) > 1 else 18
HALF_PERIOD = 13  # 38kHz 半个周期 (us)


def main() -> None:
    print("=" * 50)
    print("lgpio 版本:", getattr(lgpio, "__version__", "未知"))
    print(f"目标 GPIO: {GPIO}")
    print("=" * 50)

    # ── 步骤 0: 打开 gpiochip ──
    try:
        chip = _find_gpiochip(GPIO)
        print(f"\n[0] GPIO{GPIO} 位于 gpiochip{chip}")
        h = lgpio.gpiochip_open(chip)
        if h < 0:
            print(f"❌ gpiochip_open 失败: {h}")
            sys.exit(1)
        print(f"    ✓ gpiochip 打开成功 (handle={h})")
    except Exception as e:
        print(f"❌ 打开 gpiochip 失败: {e}")
        print("  可能原因: 未以 root/pi 用户运行、或 GPIO 已被占用")
        sys.exit(1)

    try:
        lgpio.gpio_claim_output(h, GPIO, 0)
        print("    ✓ GPIO 已声明为输出")

        # ── 步骤 1: GPIO 高低电平 ──
        print(f"\n[1] GPIO{GPIO} 写高电平 2 秒 —— IR LED 应常亮")
        print("    如果 LED 不亮：检查接线(VCC/GND/SIG)、LED 极性、")
        print("    以及模块是否需要三极管驱动（GPIO 电流不足）")
        lgpio.gpio_write(h, GPIO, 1)
        time.sleep(2)
        lgpio.gpio_write(h, GPIO, 0)
        print("    ✓ 已拉低，观察 LED 是否亮过")

        # ── 步骤 2: tx_wave 发送 ──
        print(f"\n[2] tx_wave 发送 38kHz 载波（亮1s + 灭0.5s + 亮1s）")
        pulses = []
        for _ in range(1_000_000 // (2 * HALF_PERIOD)):
            pulses.append(lgpio.pulse(1 << GPIO, 1 << GPIO, HALF_PERIOD))
            pulses.append(lgpio.pulse(0, 1 << GPIO, HALF_PERIOD))
        pulses.append(lgpio.pulse(0, 1 << GPIO, 500_000))
        for _ in range(1_000_000 // (2 * HALF_PERIOD)):
            pulses.append(lgpio.pulse(1 << GPIO, 1 << GPIO, HALF_PERIOD))
            pulses.append(lgpio.pulse(0, 1 << GPIO, HALF_PERIOD))
        print(f"    脉冲总数: {len(pulses)}")

        room = lgpio.tx_room(h, GPIO, lgpio.TX_WAVE)
        print(f"    wave 队列空余: {room}")
        if room <= 0:
            print("    ⚠️ 队列已满，可能有未完成的波形")

        r = lgpio.tx_wave(h, GPIO, pulses)
        print(f"    tx_wave 返回值: {r}  (负数 = 错误)")
        if r < 0:
            print(f"    ❌ tx_wave 失败: {lgpio.error_text(r)}")
            return

        # 轮询发送状态
        print("    等待波形播放完毕（期间 LED 应闪烁 2 次）...")
        while True:
            busy = lgpio.tx_busy(h, GPIO, lgpio.TX_WAVE)
            if busy < 0:
                print(f"    ⚠️ tx_busy 错误: {lgpio.error_text(busy)}")
                break
            if busy == 0:
                print("    ✓ 波形播放完毕")
                break
            time.sleep(0.02)
    finally:
        try:
            lgpio.gpio_free(h, GPIO)
        except Exception:
            pass
        try:
            lgpio.gpiochip_close(h)
        except Exception:
            pass

    print("\n" + "=" * 50)
    print("诊断完成。如果步骤1亮但步骤2不亮，说明 lgpio 波形")
    print("未生效（软件/驱动问题）；如果步骤1都不亮，是接线问题。")
    print("=" * 50)


if __name__ == "__main__":
    main()
