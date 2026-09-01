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
Pin 18 (GPIO24) ◄────────── OUT
```

## 树莓派部署

### 方法一：一键部署脚本（推荐）

在树莓派上克隆本项目后，在项目根目录执行：

```bash
sudo apt install -y git
git clone https://github.com/Mxd353/InfraredRemoteControl.git
cd InfraredRemoteControl
./deploy.sh
```

`deploy.sh` 会自动完成：更新软件源、安装 `pigpio`/`python3-lgpio`、启动 `pigpiod` 守护进程、安装 Python 依赖、验证导入。

### 方法二：手动安装

```bash
# 发射端: pigpio（DMA 硬件波形，微秒级时序精度）+ 守护进程
# 注意: Raspberry Pi OS Bookworm 起 apt 已移除 pigpio 包，
#       需从源码编译（deploy.sh 会自动处理）
sudo apt install git swig python3-dev build-essential
git clone --depth 1 https://github.com/joan2937/pigpio.git
cd pigpio && make -j4 && sudo make install && cd ..
sudo ldconfig
sudo systemctl enable --now pigpiod

# 接收端: lgpio（直接操作 /dev/gpiochip，无需守护进程）
sudo apt install python3-lgpio

# Python 依赖（树莓派上执行）
pip install -r requirements.txt
```

> 说明：本项目发射端使用 **pigpio**（DMA 硬件波形，实测 lgpio 软件定时波形
> 抖动过大，38kHz 载波断续导致接收端无法解调）；接收端使用 **lgpio**
> （callback 纳秒时间戳，精度足够）。树莓派 5 的 GPIO 位于 /dev/gpiochip4，
> lgpio 会自动探测。

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

### 5. 海尔空调程序化控制（无需学习）

支持按温度/模式/风速程序化生成红外信号，无需逐个录制遥控器按键。

```bash
# 开机 / 关机
python -m infrared haier --on
python -m infrared haier --off

# 设置 26℃ 制冷、自动风
python -m infrared haier --temp 26 --mode cool --fan auto

# 设置 24℃ 制热
python -m infrared haier --temp 24 --mode heat

# 更换协议变体（14B = 新款 YR-W02 遥控器）
python -m infrared haier --on --protocol 14B
```

> 如果你的空调对 **9B**（默认）无反应，尝试加 `--protocol 14B`。
> 若两种协议均无效，说明该型号属于海尔自定义协议，需退回到 `learn` 模式录制原始信号。

## 支持的协议

| 协议      | 常见品牌                          | 状态              |
| --------- | --------------------------------- | ----------------- |
| NEC       | 通用（格力、美的等）              | ✅                 |
| 海尔 9B   | 海尔（HSU07-HEA03 等老款）       | ✅（程序化编码）  |
| 海尔 14B  | 海尔（YR-W02 等新款）            | ✅（程序化编码）  |
| 原始码    | 任何品牌                          | ✅（通过接收学习） |

## 关键设计

- **发射时序精度**：pigpio wave 由 DMA 硬件播放，微秒级精度；接收端用 lgpio callback 纳秒时间戳。
- **协议扩展**：在 `raw.py` 之上可实现任意脉冲协议（如 Sony、RC5、Samsung）。
- **码库格式**：纯 JSON，方便手工编辑或与其他工具交换。
