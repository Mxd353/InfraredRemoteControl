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

    tx.send(original, repeat=args.repeat)
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
    max_dev = 0.0
    print(f"捕获: {len(cap_us)} 段, {captured.duration_us / 1000:.0f}ms"
          f"  | 原始: {len(orig_us)} 段, {original.duration_us / 1000:.0f}ms")
    print("前 8 段对比（原始 -> 捕获 -> 偏差）:")
    for i in range(min(8, n)):
        o, c = orig_us[i], cap_us[i]
        dev = abs(c - o) / o if o else 0
        bad += dev > TOLERANCE
        max_dev = max(max_dev, dev)
        flag = "" if dev <= TOLERANCE else "  <-- 超差"
        print(f"  段{i:>2}: {o:>6}us -> {c:>6}us  偏差 {dev * 100:>5.1f}%{flag}")

    if n > 8:
        for i in range(8, n):
            o, c = orig_us[i], cap_us[i]
            dev = abs(c - o) / o if o else 0
            bad += dev > TOLERANCE
            max_dev = max(max_dev, dev)

    print(f"\n段数: 捕获{len(cap_us)} / 原始{len(orig_us)}"
          f"  | 超差段数: {bad}/{n}  | 最大偏差: {max_dev * 100:.0f}%")
    if len(cap_us) == len(orig_us) and bad == 0:
        print("\n✅ 波形保真 —— 发射链路正常。空调无反应是以下原因之一：")
        print("   1. 发射距离/角度：需要更近、对准空调红外接收窗")
        print("   2. 发射强度不足：模块供电或用三极管放大驱动")
        print("   3. 需重复发射：加 --repeat 2~3")
    else:
        print("\n❌ 波形失真（软件定时精度不足）—— lgpio 的 tx_wave 是")
        print("   软件定时，微秒级 tick 在 Linux 上抖动大，38kHz 载波")
        print("   时序被破坏。需要更换发射方案（pigpio DMA 或内核驱动）。")


if __name__ == "__main__":
    main()
