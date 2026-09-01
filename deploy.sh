#!/usr/bin/env bash
# 树莓派部署脚本
# 用法: 在项目根目录执行  ./deploy.sh
set -euo pipefail

echo "==> [1/6] 更新系统软件源索引"
sudo apt-get update

echo "==> [2/6] 安装系统依赖 (lgpio, git, 构建工具)"
sudo apt-get install -y python3-lgpio git swig python3-dev build-essential

echo "==> [3/6] 安装 pigpio（优先 apt，Bookworm 已移除则源码编译）"
if sudo apt-get install -y pigpio python3-pigpio; then
    echo "    ✓ pigpio 通过 apt 安装"
else
    echo "    apt 无 pigpio 包，从源码编译安装（官方推荐方式）..."
    if [ ! -d /tmp/pigpio-src ]; then
        git clone --depth 1 https://github.com/joan2937/pigpio.git /tmp/pigpio-src
    fi
    (cd /tmp/pigpio-src && make -j4 && sudo make install)
    sudo ldconfig
    echo "    ✓ pigpio 源码编译安装完成"
fi

echo "==> [4/6] 启动 pigpiod 守护进程（发射端 DMA 波形必需）"
sudo systemctl enable pigpiod
sudo systemctl start pigpiod

echo "==> [5/6] 安装 Python 依赖"
pip3 install --user --break-system-packages -r requirements.txt

echo "==> [6/6] 验证安装"
python3 - <<'PY'
try:
    import pigpio
    pi = pigpio.pi()
    print("pigpio:", getattr(pigpio, "VERSION", "?"),
          "| pigpiod 连接:", "OK" if pi.connected else "失败")
    if not pi.connected:
        raise SystemExit(1)
    pi.stop()
except ImportError as e:
    print("pigpio 导入失败:", e)
    raise SystemExit(1)

try:
    import lgpio
    print("lgpio OK:", getattr(lgpio, "__version__", "未知版本"))
except ImportError as e:
    print("lgpio 导入失败:", e)
    raise SystemExit(1)

import infrared
print("infrared 包导入 OK:", infrared.__all__)
PY

echo ""
echo "部署完成！接下来："
echo "  python3 -m infrared test-tx   # 发射器自检（闪烁 3 次）"
echo "  python3 -m infrared test-rx   # 接收器自检"
echo "  python3 -m infrared haier --on  # 海尔空调开机"
