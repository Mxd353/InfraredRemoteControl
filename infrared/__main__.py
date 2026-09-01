"""支持 `python -m infrared` 直接运行 CLI。"""

from .cli import main
import sys

if __name__ == "__main__":
    sys.exit(main())