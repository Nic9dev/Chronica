"""
Chronica MCP Server 起動スクリプト
venv前提: C:\Dev\Chronica\.venv\Scripts\python.exe
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

