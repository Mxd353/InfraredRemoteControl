"""海尔空调红外协议编码器。

支持两种海尔空调协议变体：
- 9 字节 (72 bit): HAIER_AC，适用于 HSU07-HEA03 等老款遥控器
- 14 字节 (112 bit): HAIER_AC_YRW02，适用于 YR-W02 等新款遥控器

两种变体共用相同的物理层时序参数（38kHz 载波），仅数据包结构不同。

协议时序（来源: IRremoteESP8266 ir_Haier.cpp）：
- Pre-Header: mark 3000us + space 3000us
- Header:     mark 3000us + space 4300us
- Bit Mark:   520us
- '1' Space:  1650us
- '0' Space:  650us
- Footer:     mark 520us + gap >= 150000us
- 编码方式:   MSB first（高位在前）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .raw import PulseSequence

# ── 物理层时序常量（微秒） ──────────────────────────────────────
HDR_MARK = 3000
HDR_SPACE = 3000       # Pre-Header space 与 Header gap 不同
HDR_GAP = 4300         # Header 后的 gap
BIT_MARK = 520
ONE_SPACE = 1650
ZERO_SPACE = 650
MIN_GAP = 150000       # 帧间最小间隔

# ── 9 字节协议常量 ─────────────────────────────────────────────
PREFIX_9B = 0xA5       # 9 字节协议前缀

# Command 字段值
CMD_OFF = 0x0
CMD_ON = 0x1
CMD_MODE = 0x2
CMD_FAN = 0x3
CMD_TEMP_UP = 0x6
CMD_TEMP_DOWN = 0x7
CMD_SLEEP = 0x8
CMD_HEALTH = 0xA
CMD_SWING = 0xC

# Mode 字段值
MODE_AUTO = 0x0
MODE_COOL = 0x1
MODE_DRY = 0x2
MODE_HEAT = 0x3
MODE_FAN = 0x4

# Fan 字段值
FAN_AUTO = 0x0
FAN_HIGH = 0x1
FAN_MED = 0x2
FAN_LOW = 0x3

# SwingV 字段值
SWINGV_OFF = 0x0
SWINGV_UP = 0x1
SWINGV_DOWN = 0x2
SWINGV_CHG = 0x3

# 温度范围
MIN_TEMP = 16
MAX_TEMP = 30

# ── 14 字节协议常量 ────────────────────────────────────────────
PREFIX_14B_A = 0xA6    # 14 字节协议前缀（Model A）
PREFIX_14B_B = 0x59    # 14 字节协议前缀（Model B）

# 14 字节 Button 字段值
BUTTON_TEMP_UP = 0x0
BUTTON_TEMP_DOWN = 0x1
BUTTON_SWING_V = 0x2
BUTTON_SWING_H = 0x3
BUTTON_FAN = 0x4
BUTTON_POWER = 0x5
BUTTON_MODE = 0x6
BUTTON_HEALTH = 0x7
BUTTON_TURBO = 0x8
BUTTON_SLEEP = 0xB
BUTTON_LOCK = 0x9
BUTTON_CFAB = 0xA

# 14 字节 Mode 字段值（与 9 字节不同）
YRW02_MODE_AUTO = 0x0
YRW02_MODE_COOL = 0x2
YRW02_MODE_DRY = 0x4
YRW02_MODE_HEAT = 0x8
YRW02_MODE_FAN = 0xC

# 14 字节 Fan 字段值
YRW02_FAN_AUTO = 0xA
YRW02_FAN_HIGH = 0x2
YRW02_FAN_MED = 0x4
YRW02_FAN_LOW = 0x6

# 14 字节 SwingV 字段值
YRW02_SWINGV_OFF = 0x0
YRW02_SWINGV_TOP = 0x1
YRW02_SWINGV_MIDDLE = 0x2
YRW02_SWINGV_BOTTOM = 0x3
YRW02_SWINGV_DOWN = 0xA
YRW02_SWINGV_AUTO = 0xC


@dataclass
class HaierState:
    """海尔空调状态。"""
    power: bool = True
    mode: int = MODE_COOL
    temp: int = 26
    fan: int = FAN_AUTO
    swing_v: int = SWINGV_OFF
    health: bool = False
    sleep: bool = False
    protocol: str = "9B"  # "9B" 或 "14B"

    def __post_init__(self) -> None:
        self.temp = max(MIN_TEMP, min(MAX_TEMP, self.temp))


def _checksum_9b(data: List[int]) -> int:
    """9 字节协议校验和：前 8 字节之和 mod 256。"""
    return sum(data[:8]) & 0xFF


def _checksum_14b_first(data: List[int]) -> int:
    """14 字节协议第一个校验和：bytes[0..12] 之和的低 8 位。"""
    return sum(data[:13]) & 0xFF


def _encode_9b(state: HaierState) -> List[int]:
    """将状态编码为 9 字节数据包。"""
    data = [0] * 9

    # Byte 0: 前缀
    data[0] = PREFIX_9B

    # Byte 1: Command(高4位) + Temp(低4位)
    # 根据状态变化推断 command
    cmd = CMD_ON
    data[1] = (cmd << 4) | ((state.temp - MIN_TEMP) & 0x0F)

    # Byte 2: CurrHours(5) + unknown(1) + SwingV(2)
    data[2] = (0x01 << 5) | (state.swing_v & 0x03)

    # Byte 3: CurrMins(6) + OffTimer(1) + OnTimer(1)
    data[3] = 0x00

    # Byte 4: OffHours(5) + Health(1)
    data[4] = (0x0C << 2) | (0x01 if state.health else 0x00)

    # Byte 5: OffMins(6) + Fan(2)
    data[5] = state.fan & 0x03

    # Byte 6: OnHours(5) + Mode(3)
    data[6] = state.mode & 0x07

    # Byte 7: OnMins(6) + Sleep(1)
    data[7] = (0x01 if state.sleep else 0x00) << 6

    # Byte 8: 校验和
    data[8] = _checksum_9b(data)

    return data


def _encode_14b(state: HaierState) -> List[int]:
    """将状态编码为 14 字节数据包（YRW02 格式）。"""
    data = [0] * 14

    # Byte 0: 前缀
    data[0] = PREFIX_14B_A

    # Byte 1: Temp(高4位) + 未知(低4位)
    data[1] = ((state.temp - MIN_TEMP) & 0x0F) << 4

    # Byte 2-3: 全 0
    data[2] = 0x00
    data[3] = 0x00

    # Byte 4: Power(6bit) + unknown
    data[4] = 0x40 if state.power else 0x00

    # Byte 5: Fan(高4位) + unknown(低4位)
    yrw02_fan_map = {
        FAN_AUTO: YRW02_FAN_AUTO,
        FAN_HIGH: YRW02_FAN_HIGH,
        FAN_MED: YRW02_FAN_MED,
        FAN_LOW: YRW02_FAN_LOW,
    }
    fan_val = yrw02_fan_map.get(state.fan, YRW02_FAN_AUTO)
    data[5] = (fan_val & 0x0F) << 4

    # Byte 6: 全 0
    data[6] = 0x00

    # Byte 7: Health(1bit) + unknown
    data[7] = 0x20 if state.health else 0x00

    # Byte 8: Sleep(1bit) + unknown
    data[8] = 0x80 if state.sleep else 0x00

    # Byte 9-10: 全 0
    data[9] = 0x00
    data[10] = 0x00

    # Byte 11: 全 0
    data[11] = 0x00

    # Byte 12: Button（默认 Power）
    data[12] = BUTTON_POWER

    # Byte 13: 校验和
    data[13] = _checksum_14b_first(data)

    return data


def _build_pulse_sequence(data: List[int]) -> PulseSequence:
    """将字节数据转换为脉冲时序序列（物理层编码）。"""
    us_list: List[int] = []

    # Pre-Header
    us_list.append(HDR_MARK)
    us_list.append(HDR_SPACE)

    # Header
    us_list.append(HDR_MARK)
    us_list.append(HDR_GAP)

    # 数据位（MSB first）
    for byte in data:
        for bit_idx in range(7, -1, -1):
            us_list.append(BIT_MARK)
            if (byte >> bit_idx) & 1:
                us_list.append(ONE_SPACE)
            else:
                us_list.append(ZERO_SPACE)

    # Footer（结束 mark，结尾为高电平以满足奇数长度约束）
    us_list.append(BIT_MARK)

    return PulseSequence(us_list)


def encode(state: HaierState) -> PulseSequence:
    """将海尔空调状态编码为可发射的脉冲时序。"""
    if state.protocol == "14B":
        data = _encode_14b(state)
    else:
        data = _encode_9b(state)
    return _build_pulse_sequence(data)


def encode_with_command(state: HaierState, command: int) -> PulseSequence:
    """使用指定命令字编码（9 字节协议）。"""
    if state.protocol != "9B":
        return encode(state)
    data = _encode_9b(state)
    data[1] = (command << 4) | ((state.temp - MIN_TEMP) & 0x0F)
    data[8] = _checksum_9b(data)
    return _build_pulse_sequence(data)


def encode_with_button(state: HaierState, button: int) -> PulseSequence:
    """使用指定按钮字编码（14 字节协议）。"""
    if state.protocol != "14B":
        return encode(state)
    data = _encode_14b(state)
    data[12] = button
    data[13] = _checksum_14b_first(data)
    return _build_pulse_sequence(data)


def decode(seq: PulseSequence) -> Optional[HaierState]:
    """尝试从脉冲时序解码海尔空调状态。返回 None 表示解码失败。"""
    us = seq.us
    if len(us) < 10:
        return None

    # 匹配 Pre-Header + Header
    def close(a: int, b: int, tol: float = 0.25) -> bool:
        return abs(a - b) <= b * tol

    idx = 0
    # Pre-Header: mark + space
    if not (close(us[idx], HDR_MARK) and close(us[idx + 1], HDR_SPACE)):
        return None
    idx += 2

    # Header: mark + gap
    if not (close(us[idx], HDR_MARK) and close(us[idx + 1], HDR_GAP)):
        return None
    idx += 2

    # 解码数据位
    bits: List[int] = []
    while idx + 1 < len(us) and len(bits) < 200:
        if not close(us[idx], BIT_MARK, 0.4):
            break
        space = us[idx + 1]
        if close(space, ONE_SPACE):
            bits.append(1)
        elif close(space, ZERO_SPACE):
            bits.append(0)
        else:
            break
        idx += 2

    if len(bits) < 72:
        return None

    # 组装字节
    data = []
    for i in range(0, len(bits) - 7, 8):
        byte_val = 0
        for j in range(8):
            byte_val = (byte_val << 1) | bits[i + j]
        data.append(byte_val)

    # 判断协议类型
    if data[0] == PREFIX_9B and len(data) >= 9:
        return _decode_9b(data[:9])
    elif data[0] in (PREFIX_14B_A, PREFIX_14B_B) and len(data) >= 14:
        return _decode_14b(data[:14])
    return None


def _decode_9b(data: List[int]) -> HaierState:
    """解码 9 字节数据包。"""
    cmd = (data[1] >> 4) & 0x0F
    temp = (data[1] & 0x0F) + MIN_TEMP
    swing_v = data[2] & 0x03
    health = bool((data[4] >> 1) & 1)
    fan = data[5] & 0x03
    mode = data[6] & 0x07
    sleep = bool((data[7] >> 6) & 1)

    power = cmd != CMD_OFF

    return HaierState(
        power=power,
        mode=mode,
        temp=temp,
        fan=fan,
        swing_v=swing_v,
        health=health,
        sleep=sleep,
        protocol="9B",
    )


def _decode_14b(data: List[int]) -> HaierState:
    """解码 14 字节数据包。"""
    temp = ((data[1] >> 4) & 0x0F) + MIN_TEMP
    power = bool(data[4] & 0x40)
    fan_raw = (data[5] >> 4) & 0x0F
    health = bool(data[7] & 0x20)
    sleep = bool(data[8] & 0x80)

    # 反向映射 fan
    fan_map_rev = {
        YRW02_FAN_AUTO: FAN_AUTO,
        YRW02_FAN_HIGH: FAN_HIGH,
        YRW02_FAN_MED: FAN_MED,
        YRW02_FAN_LOW: FAN_LOW,
    }
    fan = fan_map_rev.get(fan_raw, FAN_AUTO)

    return HaierState(
        power=power,
        mode=MODE_COOL,  # 14 字节协议的 mode 编码不同，此处简化
        temp=temp,
        fan=fan,
        swing_v=SWINGV_OFF,
        health=health,
        sleep=sleep,
        protocol="14B",
    )


# ── 便捷函数 ────────────────────────────────────────────────────

def power_on(protocol: str = "9B") -> PulseSequence:
    """开机。"""
    state = HaierState(power=True, protocol=protocol)
    return encode_with_command(state, CMD_ON) if protocol == "9B" else encode(state)


def power_off(protocol: str = "9B") -> PulseSequence:
    """关机。"""
    state = HaierState(power=False, protocol=protocol)
    return encode_with_command(state, CMD_OFF) if protocol == "9B" else encode(state)


def set_temp(temp: int, protocol: str = "9B") -> PulseSequence:
    """设置温度。"""
    state = HaierState(temp=temp, protocol=protocol)
    cmd = CMD_TEMP_UP if temp >= 26 else CMD_TEMP_DOWN
    return encode_with_command(state, cmd) if protocol == "9B" else encode(state)


def set_mode(mode: int, protocol: str = "9B") -> PulseSequence:
    """设置模式。"""
    state = HaierState(mode=mode, protocol=protocol)
    return encode_with_command(state, CMD_MODE) if protocol == "9B" else encode(state)


def set_fan(fan: int, protocol: str = "9B") -> PulseSequence:
    """设置风速。"""
    state = HaierState(fan=fan, protocol=protocol)
    return encode_with_command(state, CMD_FAN) if protocol == "9B" else encode(state)
