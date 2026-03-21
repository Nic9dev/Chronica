#!/bin/bash
# Chronica セットアップスクリプト（macOS / Linux）
# README の手順を自動化: venv作成 → 依存インストール → Claude Desktop設定

set -e

echo "=== Chronica セットアップ ==="

# プロジェクトルートで実行されているか確認
if [ ! -f "requirements.txt" ] || [ ! -f "run_server.py" ]; then
    echo "エラー: プロジェクトルート（Chronica/）で実行してください。"
    echo "  cd path/to/Chronica"
    exit 1
fi

# 1. 仮想環境の作成
if [ ! -d ".venv" ]; then
    echo ""
    echo "[1/3] 仮想環境を作成中..."
    python3 -m venv .venv || python -m venv .venv
    echo "  完了"
else
    echo ""
    echo "[1/3] 仮想環境は既に存在します（スキップ）"
fi

# 2. 依存パッケージのインストール
echo ""
echo "[2/3] 依存パッケージをインストール中..."
.venv/bin/pip install -r requirements.txt -q
echo "  完了"

# 3. Claude Desktop 設定の追加
echo ""
echo "[3/3] Claude Desktop に Chronica を登録中..."
.venv/bin/python scripts/setup_config.py

echo ""
echo "=== セットアップ完了 ==="
echo "Claude Desktop を再起動し、新しい会話を開始してください。"
