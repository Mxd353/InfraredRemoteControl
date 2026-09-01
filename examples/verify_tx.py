#!/usr/bin/env python3
"""回环验证：发射码库命令并用接收头捕获，对比时序保真度。

发射头对准接收头（5-10cm），脚本自动完成发射+捕获+对比，
判断发射波形是否与码库一致（定位空调无反应的原因）。

用法: python3 examples/verify_tx.py [命令名]
      python3 examples/verify_tx.py power --repeat 2
"""

import argparse
import sys
import threading
import time

sys.path.insert(0, "")
from infrared.tx import IRTransmitter  # noqa: E402
from infrared.rx import IRReceiver  # noqa: E402
from infrared.codes import CodeLibrary  # noqa: E402

TOLERANCE = 0.30  # 每段时长允许偏差 30%（与 NEC/海尔协议容差一致）
GLITCH_US = 10    # 忽略接收头解调 38kHz 载波边界的极短毛刺段


def main() -> None:
    p = argparse.ArgumentParser(description="发射回环验证")
    p.add_argument("name", nargs="?", default="power", help="码库命令名")
    p.add_argument("--codes", default="codes/ac.json")
    p.add_argument("--tx-pin", type=int, default=18)
    p.add_argument("--rx-pin", type=int, default=24)
    p.add_argument("--repeat", type=int, default=1)
    args = p.parse_args()

    lib = CodeLibrary(args.codes).load()
    original = lib.get_code(args.name)
    if original is None:
        print(f"命令 '{args.name}' 不存在或无效。")
        sys.exit(1)

    print(f"将发射: '{args.name}' ({len(original)} 段, "
          f"{original.duration_us / 1000:.0f}ms)")
    print("请确保发射头对准接收头（5-10cm）...\n")

    rx = IRReceiver(args.rx_pin)
    tx = IRTransmitter(args.tx_pin)

    result: dict = {}

    def do_capture() -> None:
        result["seq"] = rx.capture()

    t = threading.Thread(target=do_capture, daemon=True)
    t.start()
    time.sleep(0.3)  # 等待接收监听就绪

    t_send = time.monotonic()
    tx.send(original, repeat=args.repeat)
    t_send = time.monotonic() - t_send
    print(f"发射完成，耗时 {t_send * 1000:.0f}ms"
          f"（波形理论时长 {original.duration_us / 1000 * args.repeat:.0f}ms）")
    print(f"  提交脉冲 {getattr(tx, '_last_pulses_submitted', '?')}"
          f" / 实际添加 {getattr(tx, '_last_pulses_added', '?')}"
          f" / DMA CB {getattr(tx, '_last_cb_count', '?')}\n")
    t.join(timeout=5)
    captured = result.get("seq")

    rx.cleanup()
    tx.close()

    if captured is None:
        print("❌ 未捕获到回环信号 —— 发射头未对准接收头，或发射无输出")
        sys.exit(1)

    orig_us = original.us
    cap_us = captured.us
    n = min(len(orig_us), len(cap_us))
    bad = 0
    considered = 0
    max_dev = 0.0
    print(f"捕获: {len(cap_us)} 段, {captured.duration_us / 1000:.0f}ms"
          f"  | 原始: {len(orig_us)} 段, {original.duration_us / 1000:.0f}ms")
    print("前 8 段对比（原始 -> 捕获 -> 偏差）:")
    for i in range(min(8, n)):
        o, c = orig_us[i], cap_us[i]
        dev = abs(c - o) / o if o else 0
        if c >= GLITCH_US:  # 忽略接收头解调边界毛刺
            considered += 1
            if dev > TOLERANCE:
                bad += 1
        max_dev = max(max_dev, dev)
        flag = "" if dev <= TOLERANCE else "  <-- 超差"
        print(f"  段{i:>2}: {o:>6}us -> {c:>6}us  偏差 {dev * 100:>5.1f}%{flag}")

    if n > 8:
        for i in range(8, n):
            o, c = orig_us[i], cap_us[i]
            dev = abs(c - o) / o if o else 0
            if c >= GLITCH_US:
                considered += 1
                if dev > TOLERANCE:
                    bad += 1
            max_dev = max(max_dev, dev)

    ratio = bad / considered if considered else 1.0
    print(f"\n段数: 捕获{len(cap_us)} / 原始{len(orig_us)}"
          f"  | 超差段数: {bad}/{considered}（已忽略 <{GLITCH_US}us 毛刺）"
          f"  | 最大偏差: {max_dev * 100:.0f}%")
    if (len(cap_us) == len(orig_us) and ratio < 0.10):
        print("\n✅ 波形保真（超差占比 <10%）—— 发射链路正常。")
        print("   可以直接对空调发射。若空调无反应，检查：")
        print("   1. 发射距离/角度：需要更近、对准空调红外接收窗")
        print("   2. 发射强度不足：模块供电或用三极管放大驱动")
        print("   3. 需重复发射：加 --repeat 2~3")
    else:
        print("\n❌ 波形失真 —— 发射链路仍异常，需继续排查。")
        print("   （超差占比 >10% 或段数不一致）")


if __name__ == "__main__":
    main()
