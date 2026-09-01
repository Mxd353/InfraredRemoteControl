#!/usr/bin/env python3
"""红外发射器诊断脚本（在树莓派上运行）。

逐步定位发射不工作的问题：
  步骤1: 检查 pigpio 连接与 GPIO 输出
  步骤2: GPIO 写高电平 —— 验证接线与基本 GPIO 输出
  步骤3: wave 发送 38kHz 载波 —— 验证 DMA 波形发射

用法: python3 examples/diag_tx.py [GPIO号]
"""

import sys
import time

try:
    import pigpio
except ImportError:
    print("❌ pigpio 未安装，请先: sudo apt install pigpio python3-pigpio")
    sys.exit(1)

GPIO = int(sys.argv[1]) if len(sys.argv) > 1 else 18
HALF_PERIOD = 13  # 38kHz 半个周期 (us)


def main() -> None:
    print("=" * 50)
    print("pigpio 版本:", getattr(pigpio, "VERSION", "未知"))
    print(f"目标 GPIO: {GPIO}")
    print("=" * 50)

    # ── 步骤 0: 连接 pigpiod ──
    pi = pigpio.pi()
    if not pi.connected:
        print("❌ 无法连接 pigpiod 守护进程")
        print("  请先: sudo systemctl enable --now pigpiod")
        sys.exit(1)
    print("\n[0] ✓ pigpiod 连接成功")

    try:
        pi.set_mode(GPIO, pigpio.OUTPUT)
        print("    ✓ GPIO 已声明为输出")

        # ── 步骤 1: GPIO 高低电平 ──
        print(f"\n[1] GPIO{GPIO} 写高电平 2 秒 —— IR LED 应常亮")
        print("    如果 LED 不亮：检查接线(VCC/GND/SIG)、LED 极性、")
        print("    以及模块是否需要三极管驱动（GPIO 电流不足）")
        pi.write(GPIO, 1)
        time.sleep(2)
        pi.write(GPIO, 0)
        print("    ✓ 已拉低，观察 LED 是否亮过")

        # ── 步骤 2: pigpio wave 发送 ──
        print(f"\n[2] pigpio wave 发送 38kHz 载波（亮1s + 灭0.5s + 亮1s）")
        pulses = []
        on = 1 << GPIO
        off = 1 << GPIO
        for _ in range(1_000_000 // (2 * HALF_PERIOD)):
            pulses.append(pigpio.pulse(on, 0, HALF_PERIOD))
            pulses.append(pigpio.pulse(0, off, HALF_PERIOD))
        pulses.append(pigpio.pulse(0, off, 500_000))
        for _ in range(1_000_000 // (2 * HALF_PERIOD)):
            pulses.append(pigpio.pulse(on, 0, HALF_PERIOD))
            pulses.append(pigpio.pulse(0, off, HALF_PERIOD))
        print(f"    脉冲总数: {len(pulses)}")

        # 分批添加（pigpio 单次命令缓冲约 8192 字节 ≈ 682 个脉冲）
        BATCH = 500
        pi.wave_add_new()
        for i in range(0, len(pulses), BATCH):
            pi.wave_add_generic(pulses[i : i + BATCH])
        wid = pi.wave_create()
        if wid < 0:
            print(f"    ❌ wave_create 失败: {wid}")
            return
        print(f"    ✓ wave 创建成功 (id={wid})")

        pi.wave_send_once(wid)
        print("    等待波形播放完毕（期间 LED 应闪烁 2 次）...")
        while pi.wave_tx_busy():
            time.sleep(0.02)
        print("    ✓ 波形播放完毕")

        pi.wave_delete(wid)
    finally:
        try:
            pi.wave_clear()
        except Exception:
            pass
        try:
            pi.stop()
        except Exception:
            pass

    print("\n" + "=" * 50)
    print("诊断完成。如果步骤1亮但步骤2不亮，说明 pigpio 波形")
    print("未生效；如果步骤1都不亮，是接线问题。")
    print("=" * 50)


if __name__ == "__main__":
    main()
