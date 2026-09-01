#!/usr/bin/env python3
"""示例：直接编程发送一个 NEC 帧。"""

from infrared import raw, nec


def main() -> None:
    # 构造一个 NEC 帧：地址 0x00，命令 0x46
    frame = nec.NecFrame(0x00, 0xFF, 0x46, 0xB9)
    seq = nec.encode_frame(frame)

    print(f"协议: {frame}")
    print(f"片段数: {len(seq)}")
    print(f"总时长: {seq.duration_us / 1000:.1f} ms")
    print("时序(us, 前 12 段):", seq.us[:12])

    # 发送（需要树莓派 + pigpio + GPIO18）
    try:
        from infrared.tx import IRTransmitter

        with IRTransmitter(gpio_pin=18) as tx:
            tx.send(seq, repeat=2)
        print("已发射（重复 2 次）。")
    except RuntimeError as e:
        print("未在真实硬件上运行，仅打印时序:", e)


if __name__ == "__main__":
    main()