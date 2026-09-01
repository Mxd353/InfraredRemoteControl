#!/usr/bin/env bash
# 树莓派部署脚本
# 用法: 在项目根目录执行  ./deploy.sh
set -euo pipefail

echo "==> [1/4] 更新系统软件源索引"
sudo apt-get update

echo "==> [2/4] 安装系统依赖 (lgpio, git)"
sudo apt-get install -y python3-lgpio git

echo "==> [3/4] 安装 Python 依赖"
pip3 install --user --break-system-packages -r requirements.txt

echo "==> [4/4] 验证安装"
python3 - <<'PY'
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
echo "  python3 -m infrared test-tx   # 发射器自检"
echo "  python3 -m infrared test-rx   # 接收器自检"
echo "  python3 -m infrared haier --on  # 海尔空调开机"
