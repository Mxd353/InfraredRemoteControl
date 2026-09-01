#!/usr/bin/env python3
"""示例：程序化生成海尔空调遥控信号并发射。

用法：
    python examples/haier_control.py --on
    python examples/haier_control.py --temp 26 --mode cool --fan auto
"""

import argparse
import sys

sys.path.insert(0, "")

from infrared import haier
from infrared.tx import IRTransmitter


def main() -> None:
    p = argparse.ArgumentParser(description="海尔空调控制")
    p.add_argument("--on", action="store_true")
    p.add_argument("--off", action="store_true")
    p.add_argument("--temp", type=int)
    p.add_argument("--mode", choices=["auto", "cool", "dry", "heat", "fan"])
    p.add_argument("--fan", choices=["auto", "high", "med", "low"])
    p.add_argument("--protocol", choices=["9B", "14B"], default="9B")
    p.add_argument("--tx-pin", type=int, default=18)
    p.add_argument("--dry-run", action="store_true", help="只打印时序不发送")
    args = p.parse_args()

    protocol = args.protocol

    if args.on:
        seq = haier.power_on(protocol)
        desc = "开机"
    elif args.off:
        seq = haier.power_off(protocol)
        desc = "关机"
    else:
        state = haier.HaierState(protocol=protocol)
        desc_parts = []
        if args.mode:
            mode_map = {
                "auto": haier.MODE_AUTO,
                "cool": haier.MODE_COOL,
                "dry": haier.MODE_DRY,
                "heat": haier.MODE_HEAT,
                "fan": haier.MODE_FAN,
            }
            state.mode = mode_map[args.mode]
            desc_parts.append(args.mode)
        if args.temp is not None:
            state.temp = args.temp
            desc_parts.append(f"{args.temp}℃")
        if args.fan:
            fan_map = {
                "auto": haier.FAN_AUTO,
                "high": haier.FAN_HIGH,
                "med": haier.FAN_MED,
                "low": haier.FAN_LOW,
            }
            state.fan = fan_map[args.fan]
            desc_parts.append(args.fan)
        if not desc_parts:
            print("请提供至少一个控制参数。")
            sys.exit(1)
        seq = haier.encode(state)
        desc = " ".join(desc_parts)

    print(f"海尔空调 ({protocol}): {desc}")
    print(f"脉冲段数: {len(seq)}  总时长: {seq.duration_us / 1000:.1f}ms")
    print("时序 us (前 12 段):", seq.us[:12])

    if args.dry_run:
        print("(dry-run，未发送)")
        return

    with IRTransmitter(args.tx_pin) as tx:
        tx.send(seq, repeat=1)
    print("已发射。")


if __name__ == "__main__":
    main()