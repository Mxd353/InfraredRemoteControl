"""协议无关的原始脉冲时序表示与收发。

红外遥控的本质是一串 载波开启(on) / 关闭(off) 的时间序列。
所谓"载波开启"即 GPIO 输出 38kHz 方波，对应 IR LED 发光；
"载波关闭"即 GPIO 拉低，LED 熄灭。

本模块用微秒(us)为单位的一系列时长表示这种时序：
- 第 0、2、4... 个元素为"载波开启"时长（high/mark）
- 第 1、3、5... 个元素为"载波关闭"时长（low/space）
- 整个序列以 high 开始，总元素个数为奇数

例如 NEC 单帧简化表示为:
    mark=9000, space=4500, mark=560, space=560, mark=560 ...
"""

from __future__ import annotations

from typing import Iterable, List, Sequence

MAX_US = 0xFFFFFF  # 单段时长上限（约 16.7 秒）


class PulseSequence:
    """原始脉冲时序。unit_us 为每个元素代表的微秒数（通常为 1）。"""

    def __init__(self, units: Sequence[int], unit_us: int = 1) -> None:
        if not units:
            raise ValueError("脉冲序列不能为空")
        if len(units) % 2 == 0:
            raise ValueError("脉冲序列必须为奇数长度（以高电平开始和结束）")
        if unit_us <= 0:
            raise ValueError("unit_us 必须为正整数")
        self.units = list(units)
        self.unit_us = unit_us

    @property
    def us(self) -> List[int]:
        """以微秒为单位的完整时长序列。"""
        return [u * self.unit_us for u in self.units]

    @property
    def duration_us(self) -> int:
        """整个序列总时长（微秒）。"""
        return sum(self.us)

    @classmethod
    def from_us(cls, us_list: Sequence[int], unit_us: int = 1) -> "PulseSequence":
        if unit_us == 1:
            return cls(us_list, unit_us=1)
        units = [round(u / unit_us) for u in us_list]
        return cls(units, unit_us=unit_us)

    def __len__(self) -> int:
        return len(self.units)

    def __iter__(self):
        return iter(self.us)

    def __repr__(self) -> str:
        total = len(self.units)
        return f"<PulseSequence {total} segments, {self.duration_us}us>"


def us_to_raw(seq: PulseSequence) -> Sequence[int]:
    """将 PulseSequence 转换为内核收发所需的 raw 数组。"""
    return seq.us


def raw_to_us(raw_array: Sequence[int], unit_us: int = 1) -> List[int]:
    """原始数组转微秒序列。"""
    return [v * unit_us for v in raw_array]
