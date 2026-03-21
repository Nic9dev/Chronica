"""
Chronica MCP ランチャー（Claude Code 用）
.mcp.json から呼ばれ、プロジェクトの venv を使って run_server.py を起動する。
クロスプラットフォーム対応（Windows / macOS / Linux）
"""
import os
import sys
from pathlib import Path

def main():
    root = Path(__file__).resolve().parent
    if sys.platform == "win32":
        python = root / ".venv" / "Scripts" / "python.exe"
    else:
        python = root / ".venv" / "bin" / "python"

    run_server = root / "run_server.py"
    if not python.exists():
        print(f"Error: venv not found at {python}. Run setup.ps1 or setup.sh first.", file=sys.stderr)
        sys.exit(1)
    if not run_server.exists():
        print(f"Error: run_server.py not found at {run_server}", file=sys.stderr)
        sys.exit(1)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")

    os.execv(str(python), [str(python), str(run_server)])

if __name__ == "__main__":
    main()
