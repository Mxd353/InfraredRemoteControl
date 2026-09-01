#!/usr/bin/env python3
"""红外遥控空调命令行工具。

用法示例：
    python -m infrared.cli learn power            # 学习按键存为 power
    python -m infrared.cli send power             # 发射 power
    python -m infrared.cli send power --repeat 3  # 发射 3 次
    python -m infrared.cli list                   # 列出码库
    python -m infrared.cli test-tx                # 发射器硬件自检
"""

from __future__ import annotations

import argparse
import sys
import textwrap

from .codes import CodeLibrary
from .tx import IRTransmitter
from .rx import IRReceiver

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

    # 短促测试时序：500ms 载波
    seq = PulseSequence([500_000])
    with IRTransmitter(args.tx_pin) as tx:
        tx.send(seq)
    print("发射器自检完成：应能看到模块闪烁。")
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


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "learn": cmd_learn,
        "send": cmd_send,
        "list": cmd_list,
        "test-tx": cmd_test_tx,
        "test-rx": cmd_test_rx,
        "info": cmd_info,
    }
    try:
        return handlers[args.command](args)
    except RuntimeError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())