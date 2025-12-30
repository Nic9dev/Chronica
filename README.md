# Chronica MCP Server

Chronicaは、個人の記憶を管理するMCP（Model Context Protocol）サーバーです。

## 起動方法

### 前提条件

- Python 3.10以上
- venv環境（`.venv`ディレクトリ）

### セットアップ

1. venv環境を作成（未作成の場合）:
   ```powershell
   python -m venv .venv
   ```

2. venvを有効化:
   ```powershell
   .venv\Scripts\Activate.ps1
   ```

3. 依存関係をインストール:
   ```powershell
   pip install -r requirements.txt
   ```

### 起動

venv環境で以下のコマンドを実行:

```powershell
.venv\Scripts\python.exe run_server.py
```

または、venvが有効化されている場合:

```powershell
python run_server.py
```

サーバーはSTDIOで起動し、MCP Inspector等から接続できます。

## 提供ツール（v0.1）

1. `chronica.save_entry` - エントリを保存
2. `chronica.search` - エントリを検索
3. `chronica.timeline` - タイムラインを取得
4. `chronica.get_last_seen` - 最後に見た時刻を取得
5. `chronica.compose_opening` - オープニングパックを生成
6. `chronica.summarize` - サマリーパックを生成

## データベース

SQLiteデータベースは `data/chronica.sqlite3` に自動的に作成されます。
このファイルは `.gitignore` で除外されているため、コミットされません。

## 参照

- 実装タスク: `docs/Cursor_Mission_Chronica_MCP_v0.1.md`
- 仕様書: `docs/Chronica_Spec_Integrated_v0.1.md`

