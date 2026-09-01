"""树莓派红外遥控空调项目包。

模块划分：
- raw:      原始脉冲/间隙序列的编解码与收发（协议无关）
- nec:      NEC 协议编解码（基于 raw）
- haier:    海尔空调协议编码器（9字节/14字节）
- tx:       发送器，GPIO 输出 38kHz 载波调制
- rx:       接收器，GPIO 读取红外接收头脉冲
- codes:    空调码库的读写管理（JSON）
"""

from .tx import IRTransmitter
from .rx import IRReceiver
from . import raw, nec, haier, codes

__all__ = [
    "IRTransmitter",
    "IRReceiver",
    "raw",
    "nec",
    "haier",
    "codes",
]
