"""
Chronica MCP Server 起動スクリプト
プロジェクトルートから実行: python run_server.py
"""
import sys
from pathlib import Path

# srcディレクトリをパスに追加
src_dir = Path(__file__).parent / "src"
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
