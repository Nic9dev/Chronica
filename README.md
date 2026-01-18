# Chronica MCP Server

Chronicaは、個人の記憶を管理するMCP（Model Context Protocol）サーバーです。

## プロジェクト構成

```
Chronica/
├── src/chronica/          # MCPサーバー実装
│   ├── server.py          # STDIOサーバー
│   ├── server_http.py     # HTTP/SSEサーバー
│   ├── tools.py           # MCPツール定義
│   ├── store.py           # データベース層
│   └── ...
├── clients/               # クライアントアプリケーション
│   ├── client_gemini.py   # Gemini API版（参考用）
│   └── client_ollama.py   # Ollama版（✅ 実装済み）
├── run_server.py          # MCPサーバー起動（STDIO）
├── run_server_http.py     # MCPサーバー起動（HTTP/SSE）
└── config.json            # 設定ファイル（.gitignore）
```

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

### 起動方法（HTTP/SSE版 - GPT等のリモート接続用）

HTTP/SSE版を起動する場合（GPTでMCPサーバーを登録する場合）：

```powershell
python run_server_http.py
```

または、ホストとポートを指定する場合：

```powershell
python run_server_http.py --host 127.0.0.1 --port 8000
```

起動後、以下のエンドポイントが利用可能になります：
- **SSEエンドポイント**: `http://127.0.0.1:8000/sse`
- **メッセージエンドポイント**: `http://127.0.0.1:8000/messages`

**注意**: ローカル開発用のため、認証なしで動作します。本番環境では適切な認証を実装してください。

### HTTPSで公開する方法（GPTで登録する場合）

GPTでMCPサーバーを登録するには、HTTPS URLが必要です。**cloudflared**または**ngrok**を使用してローカルサーバーをHTTPSで公開できます。

#### 方法1: cloudflaredを使用（推奨）

1. **cloudflaredをインストール:**
   - Windows: [cloudflaredのダウンロードページ](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/)からダウンロード
   - または、Scoopを使用: `scoop install cloudflared`
   - または、Chocolateyを使用: `choco install cloudflared`

2. **トンネルを作成してサーバーを公開:**
   ```powershell
   cloudflared tunnel --url http://127.0.0.1:8000
   ```

3. **表示されたHTTPS URLを使用:**
   - 例: `https://xxxx-xxxx-xxxx.trycloudflare.com`
   - このURLの `/sse` エンドポイントをGPTで使用: `https://xxxx-xxxx-xxxx.trycloudflare.com/sse`

#### 方法2: ngrokを使用

1. **ngrokをインストール:**
   - [ngrokの公式サイト](https://ngrok.com/)からダウンロード
   - または、Scoopを使用: `scoop install ngrok`
   - アカウントを作成して認証トークンを取得

2. **認証トークンを設定:**
   ```powershell
   ngrok config add-authtoken <YourAuthToken>
   ```

3. **トンネルを作成:**
   ```powershell
   ngrok http 8000
   ```

4. **表示されたHTTPS URLを使用:**
   - 例: `https://xxxx-xxxx-xxxx.ngrok.io`
   - このURLの `/sse` エンドポイントをGPTで使用: `https://xxxx-xxxx-xxxx.ngrok.io/sse`

**注意**: トンネルはサーバーと同時に起動する必要があります。サーバーを停止すると、トンネルも停止します。

## MCP Inspectorでの接続テスト

### 前提条件

- Node.jsがインストールされていること

### 手順

1. **MCP Inspectorを起動:**
   
   プロジェクトルート（`C:\Dev\Chronica`）で、以下のコマンドを実行します：
   
   ```powershell
   npx @modelcontextprotocol/inspector python run_server.py
   ```
   
   または、venvが有効化されている場合：
   
   ```powershell
   npx @modelcontextprotocol/inspector .venv\Scripts\python.exe run_server.py
   ```

2. **ブラウザでインターフェースが開きます:**
   - MCP Inspectorのインターフェースが自動的にブラウザで開きます
   - 左側にツール一覧が表示されます

3. **ツールをテスト:**
   - 左側のツール一覧から任意のツールを選択
   - パラメータを入力して「Call Tool」ボタンをクリック
   - 結果が右側に表示されます

### テスト例

**`chronica.get_last_seen`のテスト:**
```json
{
  "thread_type": "normal"
}
```

**`chronica.compose_opening`のテスト:**
```json
{
  "anchor_time": "2026-01-06T12:00:00+09:00",
  "thread_type": "normal",
  "smalltalk_level": "always"
}
```

**`chronica.save_entry`のテスト:**
```json
{
  "entry": {
    "version": "0.1",
    "saved_time": "2026-01-06T12:00:00+09:00",
    "thread": {
      "type": "normal"
    },
    "kind": "note",
    "text": "テストエントリ",
    "tags": ["test"]
  }
}
```

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

## クライアントアプリケーション

### Ollama版（✅ 実装済み）

ローカルLLMを使用したクライアント。API制限なしで利用可能。

**前提条件**:
- Ollamaがインストールされ、起動していること
- 使用するモデルがダウンロードされていること（例: `ollama pull qwen2.5:7b`）

**使用方法**:
```powershell
python clients/client_ollama.py
```

**設定**:
`config.json`に以下の設定を追加してください：
```json
{
  "OLLAMA_MODEL": "qwen3:8b",
  "OLLAMA_BASE_URL": "http://localhost:11434",
  "SHOW_TOOL_LOGS": false
}
```

**推奨モデル**:
- **Qwen 3 (8B)** ⭐: Qwen 2.5の後継モデル。性能が大幅に向上し、JSONの書き間違いが少ない。日本語も非常に上手。最優先推奨。
- **Qwen 3 (4B)**: リソースが限られている場合の軽量版。十分に実用的。
- **Qwen 3 (30B)**: 最高性能が必要な場合。高いVRAMが必要。
- **Gemma 3 (4B)**: Google純正。文脈を読む力が強く、ChronicaのようなパートナーAIに最適。
- **ELYZA Llama-3**: 日本語特化の最高峰。会話だけなら最強だが、複雑なTool指示でQwen 3に一歩譲る場合がある。

詳細は `clients/README.md` を参照してください。

## 参照

- 仕様書: `docs/Chronica_SoT_and_CursorMission_MERGED_v0.1_plus_thread_addendum_2026-01-06.md`

