"""
Chronica MCP Server 起動スクリプト
"""
import sys
from pathlib import Path

# srcディレクトリをパスに追加
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from chronica.server import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())

