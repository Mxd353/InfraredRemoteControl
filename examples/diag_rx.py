#!/usr/bin/env python3
"""红外接收器诊断脚本（在树莓派上运行）。

分步定位"学习不到信号"的问题：
  步骤1: GPIO 空闲电平 —— 验证接线（IR 接收头空闲输出应为高）
  步骤2: 轮询检测电平翻转 —— 按遥控器时电平是否变化（硬件层）
  步骤3: lgpio callback 触发 —— 验证软件回调链路

用法: python3 examples/diag_rx.py [GPIO号]
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

GPIO = int(sys.argv[1]) if len(sys.argv) > 1 else 24


def main() -> None:
    print("=" * 50)
    print("lgpio 版本:", getattr(lgpio, "__version__", "未知"))
    print(f"目标 GPIO: {GPIO}（接收头 OUT）")
    print("=" * 50)

    try:
        chip = _find_gpiochip(GPIO)
        print(f"\n[0] GPIO{GPIO} 位于 gpiochip{chip}")
        h = lgpio.gpiochip_open(chip)
        if h < 0:
            print(f"❌ gpiochip_open 失败: {h}")
            sys.exit(1)
        print("    ✓ gpiochip 打开成功")
    except Exception as e:
        print(f"❌ 打开 gpiochip 失败: {e}")
        sys.exit(1)

    try:
        lgpio.gpio_claim_alert(
            h, GPIO, lgpio.BOTH_EDGES, lFlags=lgpio.SET_PULL_UP
        )
        print("    ✓ GPIO 已声明为输入(双边沿告警 + 上拉)")

        # ── 步骤 1: 空闲电平 ──
        time.sleep(0.3)
        lv = lgpio.gpio_read(h, GPIO)
        print(f"\n[1] GPIO 空闲电平: {lv}  （IR 接收头空闲应为 1/高）")
        if lv == 0:
            print("    ⚠️ 空闲为低 —— 常见原因：")
            print("       · VCC/GND 接反")
            print("       · OUT 接到别的脚（确认是 GPIO" + str(GPIO) + " Pin "
                  + str(18 if GPIO == 24 else "") + " 之外的口）")
            print("       · 接收头损坏")
        else:
            print("    ✓ 空闲高电平正常")

        # ── 步骤 2: 轮询检测电平翻转 ──
        print(f"\n[2] 请把遥控器对准接收头，连按任意键 3 秒...")
        edges = []
        last = lgpio.gpio_read(h, GPIO)
        t0 = time.monotonic()
        while time.monotonic() - t0 < 3:
            v = lgpio.gpio_read(h, GPIO)
            if v != last:
                edges.append((time.monotonic() - t0, v))
                last = v
            time.sleep(0.00005)  # 50us 轮询
        print(f"    轮询检测到 {len(edges)} 次电平翻转")
        if edges:
            print("    ✓ 接收头有信号输出，硬件链路 OK")
            print("    前几个翻转时刻/电平:")
            for i, (t, v) in enumerate(edges[:6]):
                print(f"      #{i}: t={t*1000:.2f}ms  电平={v}")
            print("    → 问题可能出在 lgpio callback，继续步骤 3")
        else:
            print("    ✗ 无任何电平变化 —— 问题在硬件层：")
            print("       · 接收头供电/接地/OUT 接线确认")
            print("       · 遥控器电池/是否真的对准接收头")
            print("       · 接收头（如 VS1838B）是否损坏")
            return

        # ── 步骤 3: lgpio callback 测试 ──
        print(f"\n[3] lgpio callback 测试：再连按遥控器 3 秒...")
        counter = {"n": 0}

        def on_edge(chip_, gpio_, level, ts):
            counter["n"] += 1
            if counter["n"] <= 5:
                print(f"      callback: 电平={level} 时间戳={ts}ns")

        cb = lgpio.callback(h, GPIO, lgpio.BOTH_EDGES, on_edge)
        t0 = time.monotonic()
        while time.monotonic() - t0 < 3:
            time.sleep(0.1)
        cb.cancel()
        print(f"    callback 触发 {counter['n']} 次边沿")
        if counter["n"] > 0:
            print("    ✓ callback 正常 → rx.py 学习功能应该可用")
        else:
            print("    ✗ callback 未触发 —— lgpio 回调线程异常")
            print("      建议: 检查 lgpio 版本，或换 gpiod 库")
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
    print("诊断完成。按上方判断执行下一步。")
    print("=" * 50)


if __name__ == "__main__":
    main()
