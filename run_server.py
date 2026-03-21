"""
Chronica MCP Server 起動スクリプト
プロジェクトルートから実行: python run_server.py
"""
import os
import sys
from pathlib import Path

# プロジェクトルートに移動（Claude Desktop 等から任意の cwd で起動される場合に対応）
project_root = Path(__file__).resolve().parent
os.chdir(project_root)

# srcディレクトリをパスに追加
src_dir = project_root / "src"
sys.path.insert(0, str(src_dir))

# サーバーを起動
if __name__ == "__main__":
    from chronica.server import main
    import asyncio
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nChronica MCP Server stopped.", file=sys.stderr)
        sys.exit(0)
