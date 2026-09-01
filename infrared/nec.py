"""NEC 红外协议编解码。

NEC 协议（38kHz 载波）单帧格式：
- Leader:      mark 9000us, space 4500us
- 32 bit 数据: 每位 = mark 560us + space
    - "0": space 560us
    - "1": space 1690us
- 低字节优先（LSB first）发送

32 bit 组成（地址 8bit + 地址反码 8bit + 命令 8bit + 命令反码 8bit）：
    [address][~address][command][~command]

空调遥控器常使用 NEC 扩展 / 更长帧，这里同时提供通用原始码支持，
详见 codes 模块。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .raw import PulseSequence

# NEC 标准时序（微秒）
LEADER_MARK = 9000
LEADER_SPACE = 4500
BIT_MARK = 560
BIT_0_SPACE = 560
BIT_1_SPACE = 1690
REPEAT_MARK = 9000
REPEAT_SPACE = 2250
REPEAT_TAIL_MARK = 560

TOLERANCE = 0.3  # 时序容差比例


@dataclass
class NecFrame:
    """一个 NEC 帧的 32 位数据。"""

    address: int
    address_inv: int
    command: int
    command_inv: int

    @property
    def valid(self) -> bool:
        return (
            ((self.address ^ 0xFF) & 0xFF) == self.address_inv
            and ((self.command ^ 0xFF) & 0xFF) == self.command_inv
        )

    def to_bytes(self) -> bytes:
        return bytes(
            [self.address, self.address_inv, self.command, self.command_inv]
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> "NecFrame":
        if len(data) != 4:
            raise ValueError(f"NEC 帧需 4 字节，给定 {len(data)}")
        return cls(data[0], data[1], data[2], data[3])

    @property
    def raw_bits(self) -> List[int]:
        """32 位原始比特（LSB first）。"""
        bits: List[int] = []
        for byte in self.to_bytes():
            for i in range(8):
                bits.append((byte >> i) & 1)
        return bits

    def __repr__(self) -> str:
        tag = "OK" if self.valid else "BAD"
        return (
            f"<NecFrame addr=0x{self.address:02X} "
            f"cmd=0x{self.command:02X} [{tag}]>"
        )


def encode_frame(frame: NecFrame, repeat: bool = False) -> PulseSequence:
    """将 NEC 帧编码为原始脉冲序列。repeat=True 生成重复帧。"""
    if repeat:
        return PulseSequence(
            [
                REPEAT_MARK,
                REPEAT_SPACE,
                REPEAT_TAIL_MARK,
            ]
        )

    us_list: List[int] = [LEADER_MARK, LEADER_SPACE]
    for bit in frame.raw_bits:
        us_list.append(BIT_MARK)
        us_list.append(BIT_1_SPACE if bit else BIT_0_SPACE)
    us_list.append(BIT_MARK)  # 尾部结束 mark
    return PulseSequence(us_list)


def decode_frame(seq: PulseSequence) -> Optional[NecFrame]:
    """尝试将原始脉冲序列解码为 NEC 帧。失败返回 None。"""
    us = seq.us
    if len(us) < 66:  # leader(2) + 32*2 + tail(1)+ ... 最少 需要 2+64+1=67? 保守用 60
        # NEC 32bit 至少 2 + 64 + 1 = 67 段
        if len(us) < 67:
            return None
    us = us[:67]

    def close(a: int, b: int) -> bool:
        return abs(a - b) <= b * TOLERANCE

    if not (close(us[0], LEADER_MARK) and close(us[1], LEADER_SPACE)):
        # 尝试匹配重复帧
        if close(us[0], REPEAT_MARK) and close(us[1], REPEAT_SPACE):
            return None  # 重复帧不携带新数据
        return None

    data: List[int] = []
    idx = 2
    for _ in range(32):
        if not close(us[idx], BIT_MARK):
            return None
        space = us[idx + 1]
        if close(space, BIT_0_SPACE):
            data.append(0)
        elif close(space, BIT_1_SPACE):
            data.append(1)
        else:
            return None
        idx += 2

    # 组装为 4 字节
    bytes_list = [0, 0, 0, 0]
    for bit_idx, bit in enumerate(data):
        byte_idx = bit_idx // 8
        bytes_list[byte_idx] |= bit << (bit_idx % 8)

    frame = NecFrame.from_bytes(bytes(bytes_list))
    return frame
