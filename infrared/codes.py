"""空调码库管理：读写 JSON 格式的遥控码数据。

结构：
{
  "brand": "格力",
  "model": "KFR-35GW",
  "protocol": "NEC",
  "codes": {
    "power":    [9000, 4500, ...],   # 原始 us 时序
    "cool_22":  [9000, 4500, ...]
  }
}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from .raw import PulseSequence


class CodeLibrary:
    """管理一份空调遥控码库文件。"""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.data: Dict = {"brand": "", "model": "", "protocol": "raw", "codes": {}}

    def load(self) -> "CodeLibrary":
        if not self.path.exists():
            raise FileNotFoundError(f"码库文件不存在: {self.path}")
        with self.path.open("r", encoding="utf-8") as f:
            self.data = json.load(f)
        return self

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        tmp.replace(self.path)

    # ---- 元数据 ----
    @property
    def brand(self) -> str:
        return self.data.get("brand", "")

    @brand.setter
    def brand(self, value: str) -> None:
        self.data["brand"] = value

    # ---- 码操作 ----
    def set_code(self, name: str, seq: PulseSequence) -> None:
        self.data.setdefault("codes", {})[name] = seq.us

    def get_code(self, name: str) -> Optional[PulseSequence]:
        raw = self.data.get("codes", {}).get(name)
        if raw is None:
            return None
        try:
            return PulseSequence(raw)
        except ValueError:
            # 数据无效（如长度为偶数的占位示例），返回 None
            return None

    def list_codes(self) -> list:
        return list(self.data.get("codes", {}).keys())

    def remove_code(self, name: str) -> bool:
        if name in self.data.get("codes", {}):
            del self.data["codes"][name]
            return True
        return False
