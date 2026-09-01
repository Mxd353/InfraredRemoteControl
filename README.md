# InfraredRemoteControl

树莓派红外遥控空调项目（Python）。

## 硬件接线

```
树莓派 4B                   红外发射模块
──────────────────────────────────
Pin 2  (5V)     ─────────── VCC
Pin 6  (GND)    ─────────── GND
Pin 12 (GPIO18) ─────────── DAT
```

若使用接收头学习功能（可选）：

```
树莓派 4B                   红外接收模块
──────────────────────────────────
Pin 4  (5V)     ─────────── VCC
Pin 9  (GND)    ─────────── GND
Pin 13 (GPIO27) ◄────────── OUT
```

## 依赖安装

```bash
# pigpio（精确时序发射）
sudo apt install pigpio python3-pigpio
sudo systemctl enable pigpiod
sudo systemctl start pigpiod

# Python 依赖
pip install pigpio RPi.GPIO

# 或一步完成
pip install -r requirements.txt
```

## 项目结构

```
InfraredRemoteControl/
├── infrared/
│   ├── __init__.py   # 包入口
│   ├── __main__.py   # 支持 python -m infrared
│   ├── raw.py        # 协议无关：原始脉冲时序表示
│   ├── nec.py        # NEC 协议编解码
│   ├── tx.py         # 发送器（GPIO 38kHz 载波调制）
│   ├── rx.py         # 接收器（红外接收头学习）
│   ├── codes.py      # 码库管理（JSON 读写）
│   └── cli.py        # 命令行工具
├── codes/
│   └── ac.json       # 空调遥控码库示例
├── examples/
│   ├── send_nec.py   # NEC 发送示例
│   └── learn_loop.py # 连续学习示例
├── tests/
│   └── test_nec.py   # NEC 编解码单测
├── docs/
│   └── protocol.md   # NEC 协议说明
├── requirements.txt
├── setup.py
└── README.md
```

## 快速上手

### 1. 自检硬件

```bash
# 测试发射器：按下回车后，红外 LED 应发出 500ms 信号
python -m infrared test-tx

# 测试接收器：用空调遥控器对准接收头按任意键，应打印时序
python -m infrared test-rx
```

### 2. 学习遥控器码

```bash
# 学习电源键
python -m infrared learn power

# 学习温度 22°C 制冷键
python -m infrared learn cool_22
```

### 3. 发射信号

```bash
# 发射电源键（关/开空调）
python -m infrared send power

# 连续发射 3 次（空调未响应时可重发）
python -m infrared send cool_22 --repeat 3

# 列出码库中已存命令
python -m infrared list
```

### 4. 直接编程使用

```python
from infrared.tx import IRTransmitter
from infrared.codes import CodeLibrary

lib = CodeLibrary("codes/ac.json").load()
seq = lib.get_code("power")

with IRTransmitter(gpio_pin=18) as tx:
    tx.send(seq, repeat=2)
```

## 支持的协议

| 协议   | 常见品牌             | 状态              |
| ------ | -------------------- | ----------------- |
| NEC    | 通用（格力、美的等） | ✅                 |
| 原始码 | 任何品牌             | ✅（通过接收学习） |

## 关键设计

- **发射时序精度**：使用 pigpio 波形功能，在内核级生成脉冲，避免 Python 解释器的抖动干扰。
- **协议扩展**：在 `raw.py` 之上可实现任意脉冲协议（如 Sony、RC5、Samsung）。
- **码库格式**：纯 JSON，方便手工编辑或与其他工具交换。
