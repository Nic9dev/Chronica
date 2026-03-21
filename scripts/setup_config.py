"""
Chronica MCP を Claude Desktop / Claude Code の設定に追加・更新するスクリプト
クロスプラットフォーム対応（Windows / macOS / Linux）
"""
import json
import os
import sys
from pathlib import Path


def get_config_path() -> Path:
    """OS に応じた Claude Desktop 設定ファイルのパスを返す"""
    if sys.platform == "win32":
        # MSIX版を優先して探す
        local_app = Path(os.environ.get("LOCALAPPDATA", ""))
        packages_dir = local_app / "Packages"
        if packages_dir.exists():
            claude_dirs = list(packages_dir.glob("Claude_*"))
            if claude_dirs:
                msix_path = claude_dirs[0] / "LocalCache" / "Roaming" / "Claude" / "claude_desktop_config.json"
                if msix_path.parent.exists():
                    return msix_path
        # 従来版にフォールバック
        base = Path(os.environ.get("APPDATA", ""))
        return base / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def get_claude_code_config_path() -> Path:
    """Claude Code の設定ファイルパス（~/.claude.json）"""
    return Path.home() / ".claude.json"


def to_posix_path(p: Path) -> str:
    """Windows でも / 区切りのパスに変換"""
    return str(p).replace("\\", "/")


def merge_mcp_config(config: dict, chronica_config: dict) -> dict:
    """既存 config に chronica をマージ"""
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    config["mcpServers"]["chronica"] = chronica_config
    return config


def write_config(config_path: Path, config: dict) -> bool:
    """設定ファイルを書き込み"""
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except IOError as e:
        print(f"  Error: {e}", file=sys.stderr)
        return False


def main():
    project_root = Path(__file__).resolve().parent.parent

    if sys.platform == "win32":
        python_exe = project_root / ".venv" / "Scripts" / "python.exe"
    else:
        python_exe = project_root / ".venv" / "bin" / "python"

    run_server = project_root / "run_server.py"
    src_dir = project_root / "src"

    # Claude Desktop 用（絶対パス）
    chronica_desktop_config = {
        "command": to_posix_path(python_exe),
        "args": [to_posix_path(run_server)],
        "env": {"PYTHONPATH": to_posix_path(src_dir)},
    }

    # Claude Code 用（~/.claude.json は絶対パスで登録）
    chronica_code_config = chronica_desktop_config

    updated = []

    # 1. Claude Desktop（MSIX版優先、従来版にフォールバック）
    for config_path in [get_config_path()]:
        config = {}
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        merge_mcp_config(config, chronica_desktop_config)
        if write_config(config_path, config):
            updated.append(config_path)

    # 2. Claude Code（~/.claude.json）
    code_config_path = get_claude_code_config_path()
    config = {}
    if code_config_path.exists():
        try:
            with open(code_config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    merge_mcp_config(config, chronica_code_config)
    if write_config(code_config_path, config):
        updated.append(code_config_path)

    if updated:
        print("設定を更新しました:")
        for p in updated:
            print(f"  - {p}")
        print("Claude Desktop / Claude Code を再起動してください。")
    else:
        print("設定の更新に失敗しました。")
        sys.exit(1)


if __name__ == "__main__":
    main()
