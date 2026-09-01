#!/usr/bin/env python3
"""示例：连续学习多个按键，存入同一个码库。

用法：python examples/learn_loop.py
按提示依次按遥控器上的各个键。
"""

from infrared.codes import CodeLibrary
from infrared.rx import IRReceiver

CODES_FILE = "codes/ac.json"
RX_PIN = 24

TO_LEARN = [
    ("power",    "电源键"),
    ("mode",     "模式键"),
    ("temp_up",  "温度+"),
    ("temp_down","温度-"),
    ("fan_low",  "低风"),
    ("fan_high", "高风"),
]


def main() -> None:
    lib = CodeLibrary(CODES_FILE)
    try:
        lib.load()
    except FileNotFoundError:
        lib.brand = "示例"
        lib.data["protocol"] = "raw"

    rx = IRReceiver(RX_PIN)

    print("=== 空调遥控器批量学习 ===")
    print(f"将存入：{CODES_FILE}\n")

    for key_name, label in TO_LEARN:
        input(f"请对准接收头，按遥控器【{label}】，然后回车确认...")
        seq = rx.capture()
        if seq is None:
            print(f"  ✗ 未捕获信号，跳过 {label}\n")
            continue
        lib.set_code(key_name, seq)
        print(f"  ✓ 已记录 {label} ({len(seq)} 段)\n")

    rx.cleanup()
    lib.save()
    print(f"\n完成，共 {len(lib.list_codes())} 个命令已保存到 {CODES_FILE}")
    print("用法：python -m infrared send <命令名>")


if __name__ == "__main__":
    main()