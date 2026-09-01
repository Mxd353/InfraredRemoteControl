"""测试：海尔空调协议编解码（纯软件，无需硬件）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from infrared import haier


def test_9b_encode_structure():
    """验证 9 字节编码的数据包结构。"""
    state = haier.HaierState(
        power=True,
        mode=haier.MODE_COOL,
        temp=26,
        fan=haier.FAN_AUTO,
        swing_v=haier.SWINGV_OFF,
        protocol="9B",
    )
    seq = haier.encode(state)
    us = seq.us

    # 验证物理层时序开头
    assert us[0] == haier.HDR_MARK
    assert us[1] == haier.HDR_SPACE
    assert us[2] == haier.HDR_MARK
    assert us[3] == haier.HDR_GAP
    print(f"9B 结构 OK: 共 {len(us)} 段, {seq.duration_us / 1000:.1f}ms")


def test_9b_checksum():
    """验证 9 字节校验和计算。"""
    state = haier.HaierState(temp=26, protocol="9B")
    data = haier._encode_9b(state)

    # data[8] 应为前 8 字节之和 mod 256
    expected = sum(data[:8]) & 0xFF
    assert data[8] == expected, (
        f"校验和不匹配: 实际 {data[8]:#x}, 期望 {expected:#x}"
    )
    assert data[0] == haier.PREFIX_9B
    print(f"9B 校验和 OK: 数据 = {[f'{b:#04x}' for b in data]}")


def test_9b_roundtrip():
    """验证 9 字节编解码往返。"""
    state = haier.HaierState(
        power=True,
        mode=haier.MODE_HEAT,
        temp=24,
        fan=haier.FAN_LOW,
        swing_v=haier.SWINGV_UP,
        health=True,
        sleep=False,
        protocol="9B",
    )
    seq = haier.encode(state)
    decoded = haier.decode(seq)
    assert decoded is not None, "9B 解码失败"
    assert decoded.temp == 24
    assert decoded.mode == haier.MODE_HEAT
    assert decoded.fan == haier.FAN_LOW
    assert decoded.swing_v == haier.SWINGV_UP
    print("9B roundtrip OK:", decoded)


def test_14b_encode_structure():
    """验证 14 字节编码的数据包结构。"""
    state = haier.HaierState(
        power=True,
        mode=haier.MODE_COOL,
        temp=26,
        fan=haier.FAN_AUTO,
        protocol="14B",
    )
    seq = haier.encode(state)
    us = seq.us

    assert us[0] == haier.HDR_MARK
    assert us[1] == haier.HDR_SPACE
    assert us[2] == haier.HDR_MARK
    assert us[3] == haier.HDR_GAP
    print(f"14B 结构 OK: 共 {len(us)} 段, {seq.duration_us / 1000:.1f}ms")


def test_14b_checksum():
    """验证 14 字节校验和计算。"""
    state = haier.HaierState(temp=26, protocol="14B")
    data = haier._encode_14b(state)

    assert data[0] == haier.PREFIX_14B_A
    expected = sum(data[:13]) & 0xFF
    assert data[13] == expected
    print(f"14B 校验和 OK: 数据 = {[f'{b:#04x}' for b in data]}")


def test_power_commands():
    """验证开关机命令。"""
    on_seq = haier.power_on("9B")
    off_seq = haier.power_off("9B")
    assert on_seq is not None
    assert off_seq is not None
    print("开关机命令 OK")


if __name__ == "__main__":
    test_9b_encode_structure()
    test_9b_checksum()
    test_9b_roundtrip()
    test_14b_encode_structure()
    test_14b_checksum()
    test_power_commands()
    print("\n全部海尔协议测试通过。")
