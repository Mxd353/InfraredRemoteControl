#!/usr/bin/env python3
"""红外遥控空调命令行工具。

用法示例：
    python -m infrared learn power            # 学习按键存为 power
    python -m infrared send power             # 发射 power
    python -m infrared send power --repeat 3  # 发射 3 次
    python -m infrared list                   # 列出码库
    python -m infrared haier --on             # 海尔空调开机
    python -m infrared haier --temp 26 --mode cool  # 26度制冷
    python -m infrared test-tx                # 发射器硬件自检
"""

from __future__ import annotations

import argparse
import sys
import textwrap

from .codes import CodeLibrary
from .tx import IRTransmitter
from .rx import IRReceiver
from . import haier

DEFAULT_CODES = "codes/ac.json"
TX_PIN = 18
RX_PIN = 24


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="红外遥控空调")
    p.add_argument(
        "--codes", default=DEFAULT_CODES, help=f"码库文件路径（默认 {DEFAULT_CODES}）"
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_learn = sub.add_parser("learn", help="学习遥控器按键")
    p_learn.add_argument("name", help="按键/命令名，如 power、cool_22")
    p_learn.add_argument("--rx-pin", type=int, default=RX_PIN, help="接收头 GPIO")
    p_learn.add_argument(
        "--retries", type=int, default=1, help="学习次数（取最后一次）"
    )

    p_send = sub.add_parser("send", help="发射一个已存命令")
    p_send.add_argument("name", help="要发射的命令名")
    p_send.add_argument("--repeat", type=int, default=1, help="重复次数")
    p_send.add_argument("--tx-pin", type=int, default=TX_PIN, help="发射 GPIO")

    sub.add_parser("list", help="列出码库中所有命令")

    p_tx = sub.add_parser("test-tx", help="发射器自检")
    p_tx.add_argument("--tx-pin", type=int, default=TX_PIN, help="发射 GPIO")

    p_rx = sub.add_parser("test-rx", help="接收器自检（打印捕获时序）")
    p_rx.add_argument("--rx-pin", type=int, default=RX_PIN, help="接收头 GPIO")

    p_info = sub.add_parser("info", help="显示码库元数据")

    # 海尔空调专用命令
    p_haier = sub.add_parser("haier", help="海尔空调控制")
    p_haier.add_argument("--on", action="store_true", help="开机")
    p_haier.add_argument("--off", action="store_true", help="关机")
    p_haier.add_argument("--temp", type=int, help="设置温度 (16-30)")
    p_haier.add_argument(
        "--mode",
        choices=["auto", "cool", "dry", "heat", "fan"],
        help="设置模式",
    )
    p_haier.add_argument(
        "--fan", choices=["auto", "high", "med", "low"], help="设置风速"
    )
    p_haier.add_argument(
        "--protocol",
        choices=["9B", "14B"],
        default="9B",
        help="协议类型（默认 9B）",
    )
    p_haier.add_argument("--repeat", type=int, default=1, help="重复发射次数")
    p_haier.add_argument("--tx-pin", type=int, default=TX_PIN, help="发射 GPIO")
    return p


def cmd_learn(args) -> int:
    lib = CodeLibrary(args.codes)
    try:
        lib.load()
    except FileNotFoundError:
        print(f"(新建码库) {args.codes}")
    rx = IRReceiver(args.rx_pin)
    captured = None
    for i in range(args.retries):
        print(f"[{i+1}/{args.retries}] 请对着接收头按住遥控器按键（{args.name}）...")
        captured = rx.capture()
        if captured is None:
            print("  未捕获到信号，重试。")
        else:
            print(f"  捕获 {len(captured)} 段，共 {captured.duration_us / 1000:.1f}ms")
    rx.cleanup()
    if captured is None:
        print("学习失败：没有捕获到任何信号。")
        return 1
    lib.set_code(args.name, captured)
    lib.save()
    print(f"已保存命令 '{args.name}' -> {args.codes}")
    return 0


def cmd_send(args) -> int:
    lib = CodeLibrary(args.codes).load()
    seq = lib.get_code(args.name)
    if seq is None:
        print(f"码库中不存在命令 '{args.name}'。可用: {lib.list_codes()}")
        return 1
    with IRTransmitter(args.tx_pin) as tx:
        tx.send(seq, repeat=args.repeat)
    print(f"已发射 '{args.name}' × {args.repeat}")
    return 0


def cmd_list(args) -> int:
    lib = CodeLibrary(args.codes)
    try:
        lib.load()
    except FileNotFoundError:
        print(f"码库为空或不存在: {args.codes}")
        return 0
    print(f"品牌: {lib.brand}  协议: {lib.data.get('protocol')}")
    print("命令:")
    for name in lib.list_codes():
        seq = lib.get_code(name)
        print(f"  - {name:20s} ({len(seq)} 段, {seq.duration_us/1000:.0f}ms)")
    return 0


def cmd_test_tx(args) -> int:
    from .raw import PulseSequence

    # 测试时序：亮-灭-亮，共 2.5 秒，便于观察
    seq = PulseSequence([500_000, 500_000, 500_000, 500_000, 500_000])
    with IRTransmitter(args.tx_pin) as tx:
        tx.send(seq)
    print("发射器自检完成：LED 应闪烁 3 次（每 0.5 秒一次）。")
    return 0


def cmd_test_rx(args) -> int:
    rx = IRReceiver(args.rx_pin)
    print(f"请对着接收头发出遥控信号（比如按空调遥控任意键）...")
    seq = rx.capture()
    rx.cleanup()
    if seq is None:
        print("未捕获到信号。")
        return 1
    print("捕获的时序（us）：")
    print(textwrap.fill(" ".join(str(u) for u in seq.us[:80]), width=80))
    return 0


def cmd_info(args) -> int:
    import json

    lib = CodeLibrary(args.codes).load()
    print(json.dumps(lib.data, ensure_ascii=False, indent=2))
    return 0


def cmd_haier(args) -> int:
    """海尔空调控制命令。"""
    protocol = args.protocol
    seq = None

    if args.on:
        seq = haier.power_on(protocol)
        print("海尔空调：开机")
    elif args.off:
        seq = haier.power_off(protocol)
        print("海尔空调：关机")
    else:
        state = haier.HaierState(protocol=protocol)
        parts = []

        if args.mode:
            mode_map = {
                "auto": haier.MODE_AUTO,
                "cool": haier.MODE_COOL,
                "dry": haier.MODE_DRY,
                "heat": haier.MODE_HEAT,
                "fan": haier.MODE_FAN,
            }
            state.mode = mode_map[args.mode]
            parts.append(f"模式={args.mode}")

        if args.temp is not None:
            state.temp = args.temp
            parts.append(f"温度={args.temp}℃")

        if args.fan:
            fan_map = {
                "auto": haier.FAN_AUTO,
                "high": haier.FAN_HIGH,
                "med": haier.FAN_MED,
                "low": haier.FAN_LOW,
            }
            state.fan = fan_map[args.fan]
            parts.append(f"风速={args.fan}")

        if not parts:
            print("请指定至少一个参数：--on/--off/--temp/--mode/--fan")
            return 1

        seq = haier.encode(state)
        print(f"海尔空调：{', '.join(parts)}")

    if seq is None:
        return 1

    with IRTransmitter(args.tx_pin) as tx:
        tx.send(seq, repeat=args.repeat)
    print(f"已发射（重复 {args.repeat} 次）")
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "learn": cmd_learn,
        "send": cmd_send,
        "list": cmd_list,
        "test-tx": cmd_test_tx,
        "test-rx": cmd_test_rx,
        "info": cmd_info,
        "haier": cmd_haier,
    }
    try:
        return handlers[args.command](args)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())