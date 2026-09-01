"""测试：NEC 编解码的正确性（纯软件，无需硬件）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from infrared import nec, raw


def test_roundtrip() -> None:
    frame = nec.NecFrame(0x00, 0xFF, 0x46, 0xB9)
    seq = nec.encode_frame(frame)
    decoded = nec.decode_frame(seq)
    assert decoded is not None, "解码失败"
    assert decoded.address == frame.address
    assert decoded.command == frame.command
    assert decoded.valid
    print("roundtrip OK:", decoded)


def test_validate() -> None:
    # 反码不匹配的帧应判定无效
    bad = nec.NecFrame(0x00, 0xFF, 0x46, 0x00)
    assert not bad.valid
    assert bad.to_bytes() == bytes([0x00, 0xFF, 0x46, 0x00])
    print("validate OK")


def test_show_timing() -> None:
    frame = nec.NecFrame(0x00, 0xFF, 0x01, 0xFE)
    seq = nec.encode_frame(frame)
    print(f"NEC 单帧: {len(seq)} 段, {seq.duration_us / 1000:.1f}ms")
    print("前 6 段:", seq.us[:6])


if __name__ == "__main__":
    test_roundtrip()
    test_validate()
    test_show_timing()
    print("全部测试通过。")