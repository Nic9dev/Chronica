# Chronica System Reference

**Version**: 0.2.0  
**Last Updated**: 2026-01-18  
**Status**: Production Ready (MCP Server + Ollama Client)

---

## 目次

1. [システム概要](#システム概要)
2. [アーキテクチャ](#アーキテクチャ)
3. [プロジェクト構造](#プロジェクト構造)
4. [MCPサーバー](#mcpサーバー)
5. [ツール仕様](#ツール仕様)
6. [データベーススキーマ](#データベーススキーマ)
7. [データモデル](#データモデル)
8. [クライアント実装ガイドライン](#クライアント実装ガイドライン)
9. [設定ファイル](#設定ファイル)
10. [開発ガイドライン](#開発ガイドライン)
11. [現在の状況と今後の計画](#現在の状況と今後の計画)

---

## システム概要

Chronicaは、個人の記憶を管理するMCP（Model Context Protocol）サーバーです。

### 設計思想

**Chronica中心主義（Chronica-Centric Architecture）**

- **Chronica（サーバー）が構造と時間の絶対的な正解を持つ**
- **AI（クライアント）はそのインターフェースに徹する**
- AIは外部ツール（Chronica）から渡された「構造化されたテキスト」のみを正解として扱い、幻覚（Hallucination）を防ぐ

### 主な機能

1. **エントリの保存・検索・タイムライン取得**
2. **時間認識の自律管理**（Chronicaが`datetime.now()`で時間を確定）
3. **記憶コンテキストの提供**（前回の会話、時間差、季節・時間帯）
4. **サマリー生成**（日次・週次・決定事項の要約）

---

## アーキテクチャ

### 全体構成

```
┌─────────────────────────────────────────────────────────┐
│                    AI Client Layer                       │
│  (Ollama / Gemini / Claude Desktop / etc.)              │
│  - 自然言語の理解と生成                                  │
│  - Tool呼び出し（JSON形式）                              │
└────────────────────┬────────────────────────────────────┘
                     │ MCP Protocol (STDIO / HTTP/SSE)
                     │
┌────────────────────▼────────────────────────────────────┐
│              Chronica MCP Server                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Tools Layer (tools.py)                           │  │
│  │  - 6つのMCPツールを提供                             │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Logic Layer                                      │  │
│  │  - opening.py: コンテキスト生成                    │  │
│  │  - summarize.py: サマリー生成                      │  │
│  │  - timeparse.py: 相対日時パース                    │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Data Layer (store.py)                            │  │
│  │  - SQLite永続化                                    │  │
│  │  - エントリのCRUD操作                              │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                     │
                     │ SQLite
                     │
┌────────────────────▼────────────────────────────────────┐
│         data/chronica.sqlite3                           │
│  - entries テーブル                                     │
│  - インデックス（saved_time, thread_type, thread_id, kind）│
└─────────────────────────────────────────────────────────┘
```

### データフロー

1. **会話開始時**:
   ```
   AI Client → chronica.compose_opening() 
   → Chronicaがdatetime.now()で時間確定
   → 構造化されたコンテキストを返す
   → AI Clientがそれを「絶対的な事実」として扱う
   ```

2. **エントリ保存時**:
   ```
   AI Client → chronica.save_entry(entry)
   → StoreがSQLiteに保存
   → entry_idを返す
   ```

3. **検索・タイムライン取得時**:
   ```
   AI Client → chronica.search() / chronica.timeline()
   → StoreがSQLiteから検索
   → エントリリストを返す
   ```

---

## プロジェクト構造

```
Chronica/
├── src/chronica/              # MCPサーバー実装（コア）
│   ├── __init__.py           # パッケージ初期化
│   ├── server.py             # STDIOサーバー
│   ├── server_http.py        # HTTP/SSEサーバー
│   ├── tools.py              # MCPツール定義・実装
│   ├── store.py              # データベース層（SQLite）
│   ├── opening.py            # コンテキスト生成ロジック
│   ├── summarize.py          # サマリー生成ロジック
│   └── timeparse.py          # 相対日時パーサー
│
├── clients/                  # クライアントアプリケーション
│   ├── README.md            # クライアント説明
│   ├── client_gemini.py     # Gemini API版（アーカイブ）
│   └── client_ollama.py      # Ollama版（実装予定）
│
├── docs/                     # ドキュメント
│   ├── system_reference.md   # 本ドキュメント
│   ├── japanese_quality_strategy.md  # 日本語品質向上戦略
│   └── Chronica_SoT_and_CursorMission_MERGED_v0.1_plus_thread_addendum_2026-01-06.md
│
├── data/                     # データベース（.gitignore）
│   └── chronica.sqlite3      # SQLiteデータベース
│
├── tests/                    # テスト（空）
│
├── run_server.py             # MCPサーバー起動（STDIO）
├── run_server_http.py        # MCPサーバー起動（HTTP/SSE）
├── start_with_tunnel.bat     # HTTP/SSE + cloudflared起動（Windows）
├── start_with_tunnel.ps1     # HTTP/SSE + cloudflared起動（PowerShell）
├── config.json               # 設定ファイル（.gitignore）
├── requirements.txt          # Python依存関係
├── README.md                 # プロジェクト概要
└── .gitignore               # Git除外設定
```

---

## MCPサーバー

### 起動方法

#### STDIO版（推奨）

```powershell
python run_server.py
```

- MCP Inspector、Claude Desktop、Cursor等から接続可能
- 標準入出力で通信

#### HTTP/SSE版

```powershell
python run_server_http.py
```

- リモート接続用（GPT等）
- エンドポイント:
  - SSE: `http://127.0.0.1:8000/sse`
  - Messages: `http://127.0.0.1:8000/messages`

**HTTPSトンネリング（リモート接続時のみ必要）**

GPT等のリモート接続を使用する場合は、HTTPS URLが必要です。外部ツール（cloudflared/ngrok）を使用します。

**方法1: cloudflared（推奨）**
```powershell
# 1. サーバーを起動
python run_server_http.py

# 2. 別ターミナルでトンネルを作成
cloudflared tunnel --url http://127.0.0.1:8000
```

または、自動化スクリプトを使用：
```powershell
.\start_with_tunnel.ps1
```

**方法2: ngrok**
```powershell
# 1. サーバーを起動
python run_server_http.py

# 2. 別ターミナルでトンネルを作成
ngrok http 8000
```

**注意**: 
- HTTPSトンネリングは**外部ツールを使う手順**であり、MCPサーバー自体の機能ではない
- ローカル利用（MCP Inspector、Claude Desktop、Cursor等）では不要
- リモート接続（GPT等）を使用する場合のみ必要

### サーバー実装

**ファイル**: `src/chronica/server.py`

```python
def create_server() -> Server:
    """MCPサーバーを作成"""
    server = Server("chronica")
    store = Store()
    set_store(store)
    register_tools(server)
    return server
```

---

## ツール仕様

Chronicaは9つのMCPツールを提供します。

### 1. `chronica.save_entry`

エントリを保存します。

**引数**:
```json
{
  "entry": {
    "version": "0.1",              // オプション、デフォルト: "0.1"
    "entry_id": "uuid",            // オプション、自動生成
    "saved_time": "ISO文字列",     // オプション、自動生成
    "thread": {
      "type": "normal" | "project",
      "id": "thread-uuid",        // オプション、スレッドID
      "name": "スレッド名"         // オプション
    },
    "kind": "note" | "event" | "decision" | "action" | "question",
    "text": "エントリの本文",
    "tags": ["tag1", "tag2"],
    "title": "タイトル",           // オプション
    "event_time": {                // オプション
      "raw": "今日" | "昨日" | "明日" | ...
    },
    "project": "プロジェクト名"    // オプション
  }
}
```

**必須フィールド**: `thread.type`, `kind`, `text`, `tags`

**戻り値**:
```json
{
  "entry_id": "生成されたエントリID"
}
```

**エラー**:
- `validation_error`: 必須フィールドが不足
- `save_error`: データベース保存エラー

### 2. `chronica.search`

エントリを検索します。

**引数**:
```json
{
  "thread_id": "thread-uuid",          // オプション、スレッドID（指定時はthread_typeより優先）
  "thread_type": "normal" | "project",  // オプション
  "kind": "note",                       // オプション
  "tags": ["tag1", "tag2"],            // オプション（いずれか一致）
  "project": "プロジェクト名",          // オプション
  "limit": 100                          // オプション、デフォルト: 100
}
```

**戻り値**:
```json
{
  "entries": [
    {
      "version": "0.1",
      "entry_id": "...",
      "saved_time": "...",
      "thread": {"type": "normal"},
      "kind": "note",
      "text": "...",
      "tags": [...]
    }
  ]
}
```

### 3. `chronica.timeline`

タイムラインを取得します（期間指定）。

**引数**:
```json
{
  "start_time": "2026-01-01T00:00:00+09:00",  // オプション
  "end_time": "2026-01-31T23:59:59+09:00",    // オプション
  "thread_id": "thread-uuid",                 // オプション、スレッドID（指定時はthread_typeより優先）
  "thread_type": "normal" | "project",        // オプション
  "kind": "note",                              // オプション
  "limit": 100                                 // オプション、デフォルト: 100
}
```

**戻り値**: `chronica.search`と同じ形式

### 4. `chronica.get_last_seen`

最後に見た時刻を取得します。

**引数**:
```json
{
  "thread_type": "normal" | "project"  // 必須
}
```

**戻り値**:
```json
{
  "last_seen_time": "2026-01-18T00:00:00+09:00" | null
}
```

### 5. `chronica.compose_opening`

会話開始時に必ず呼び出すこと。Chronicaから現在時刻や記憶構造を取得します。

**引数**:
```json
{
  "thread_id": "thread-uuid"  // オプション、スレッドID（指定時はそのスレッドの最後の対話を取得）
}
```

**戻り値**: 構造化されたテキスト（文字列）

```
=== Chronica Context Structure ===
[現在状況]
- 現在時刻: 2026-01-18 00:00:00
- 季節・時間帯: 冬の深夜

[記憶コンテキスト]
- 前回の会話日時: 2026-01-17T12:00:00+09:00
- 現在との時間差: お久しぶり（1週間以内）
- 前回のトピック: 大規模改修は成功。

[AIへの指示]
あなたは上記の「Chronica構造」に基づき、ユーザーに声をかけてください。
1. 「時間差」に言及すること（久しぶり、さっきは、等）。
2. 「季節/時間帯」に合わせたトーンで話すこと。
3. 自分の内部時計ではなく、この構造情報を絶対的な正解とすること。
==================================
```

**重要なポイント**:
- Chronicaが`datetime.now(JST)`で時間を確定
- 引数不要（Chronicaが自律的に状況を確定）
- 返されるテキストがAIにとっての「世界の全て」

### 6. `chronica.summarize`

サマリーパックを生成します（Summary Pack v0.1.2）。

**引数**:
```json
{
  "mode": "daily" | "weekly" | "decision",
  "range_start": "2026-01-01T00:00:00+09:00",
  "range_end": "2026-01-31T23:59:59+09:00",
  "thread_type": "normal" | "project"
}
```

**戻り値**:
```json
{
  "meta": {
    "mode": "daily",
    "range": {"start": "...", "end": "..."},
    "thread": {"type": "normal"},
    "stats": {
      "total_entries": 10,
      "by_kind": {"note": 5, "event": 3, "decision": 2}
    }
  },
  "timeline_items": [...],
  "decisions": [...],
  "actions": [...],
  "open_questions": [...],
  "digest_candidates": {
    "highlights": [...],
    "blockers": [...],
    "next_priorities": [...],
    "memory_keep": [...],
    "next_talk_seed": "..."
  }
}
```

### 7. `chronica.create_thread`

新しいスレッドを作成します。

**引数**:
```json
{
  "thread_name": "スレッド名",
  "thread_type": "normal" | "project"  // オプション、デフォルト: "normal"
}
```

**戻り値**:
```json
{
  "thread_id": "生成されたスレッドID",
  "thread_name": "スレッド名",
  "thread_type": "normal"
}
```

### 8. `chronica.list_threads`

スレッド一覧を取得します。

**引数**:
```json
{
  "thread_type": "normal" | "project"  // オプション、省略時は全て
}
```

**戻り値**:
```json
{
  "threads": [
    {
      "thread_id": "thread-uuid",
      "thread_name": "スレッド名",
      "thread_type": "normal",
      "created_at": "2026-01-18T00:00:00+09:00",
      "updated_at": "2026-01-18T00:00:00+09:00",
      "entry_count": 10
    }
  ]
}
```

### 9. `chronica.get_thread_info`

指定されたスレッドの情報を取得します。

**引数**:
```json
{
  "thread_id": "thread-uuid"
}
```

**戻り値**:
```json
{
  "thread_id": "thread-uuid",
  "thread_name": "スレッド名",
  "thread_type": "normal",
  "created_at": "2026-01-18T00:00:00+09:00",
  "updated_at": "2026-01-18T00:00:00+09:00",
  "entry_count": 10
}
```

**エラー**:
- `not_found`: 指定されたスレッドIDが存在しない

**引数**:
```json
{
  "mode": "daily" | "weekly" | "decision",
  "range_start": "2026-01-01T00:00:00+09:00",
  "range_end": "2026-01-31T23:59:59+09:00",
  "thread_type": "normal" | "project"
}
```

**戻り値**:
```json
{
  "meta": {
    "mode": "daily",
    "range": {"start": "...", "end": "..."},
    "thread": {"type": "normal"},
    "stats": {
      "total_entries": 10,
      "by_kind": {"note": 5, "event": 3, "decision": 2}
    }
  },
  "timeline_items": [...],
  "decisions": [...],
  "actions": [...],
  "open_questions": [...],
  "digest_candidates": {
    "highlights": [...],
    "blockers": [...],
    "next_priorities": [...],
    "memory_keep": [...],
    "next_talk_seed": "..."
  }
}
```

---

## データベーススキーマ

### entries テーブル

```sql
CREATE TABLE entries (
    entry_id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    saved_time TEXT NOT NULL,
    event_time_raw TEXT,
    event_time_resolved TEXT,
    event_time_confidence REAL,
    thread_id TEXT,               -- スレッドID（UUID）
    thread_type TEXT NOT NULL,
    thread_name TEXT,
    kind TEXT NOT NULL,
    title TEXT,
    text TEXT NOT NULL,
    tags TEXT,                    -- JSON配列
    project TEXT,
    links_source TEXT,
    links_refs TEXT,              -- JSON配列
    created_at TEXT NOT NULL
);

-- インデックス
CREATE INDEX idx_saved_time ON entries(saved_time);
CREATE INDEX idx_thread_kind ON entries(thread_type, kind);
CREATE INDEX idx_thread_type ON entries(thread_type);
CREATE INDEX idx_thread_id ON entries(thread_id);
```

### threads テーブル

```sql
CREATE TABLE threads (
    thread_id TEXT PRIMARY KEY,
    thread_name TEXT NOT NULL,
    thread_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### データベースファイル

- **パス**: `data/chronica.sqlite3`
- **タイムゾーン**: JST (Asia/Tokyo)
- **文字エンコーディング**: UTF-8

---

## データモデル

### Entry JSON

エントリの完全なJSON構造：

```json
{
  "version": "0.1",
  "entry_id": "uuid-string",
  "saved_time": "2026-01-18T00:00:00+09:00",
  "thread": {
    "type": "normal" | "project",
    "id": "thread-uuid",        // オプション、スレッドID
    "name": "スレッド名"         // オプション
  },
  "kind": "note" | "event" | "decision" | "action" | "question",
  "text": "エントリの本文",
  "tags": ["tag1", "tag2"],
  "title": "タイトル",  // オプション
  "event_time": {       // オプション
    "raw": "今日",
    "resolved": "2026-01-18T00:00:00+09:00",
    "confidence": 1.0
  },
  "project": "プロジェクト名",  // オプション
  "links": {            // オプション
    "source": "source-entry-id",
    "refs": ["ref-entry-id-1", "ref-entry-id-2"]
  }
}
```

### kind の推奨値

- `note`: 一般的な記録
- `event`: 出来事
- `decision`: 決定事項
- `action`: タスク・アクション
- `question`: 未決事項・質問

### thread.type の意味

- `normal`: 通常の会話（親近感のあるトーン）
- `project`: プロジェクト関連（信頼感のあるトーン）

### thread.id の意味

- スレッドID（UUID）を指定することで、複数のスレッドに分けて記憶・記録を管理できます
- `chronica.create_thread`でスレッドを作成し、`thread.id`を指定してエントリを保存すると、そのスレッドに紐付けられます
- スレッドごとに記憶・記録を分離管理できるため、GPT/Geminiのような複数スレッド機能を実現できます

---

## クライアント実装ガイドライン

### 基本原則

1. **スレッド管理（GPT/Geminiスタイル）**
   - クライアント起動時にスレッド一覧を表示
   - ユーザーがスレッドを選択（または新規作成）
   - 選択したスレッドIDを保持し、そのスレッド内で会話
   - エントリ保存時に選択中のスレッドIDを自動的に適用

2. **Chronica絶対主義**
   - 会話開始時、必ず`chronica.compose_opening`を呼び出す（スレッドIDを指定）
   - 返ってきた情報を「絶対的な事実」として扱う
   - AI自身の時間認識を使わない

3. **構造の維持**
   - ユーザーから得た新しい情報は即座に`chronica.save_entry`で保存
   - 選択中のスレッドIDを自動的に`entry.thread.id`に設定
   - 重要な決定事項、タスク、未決事項は必ず保存

4. **自然な対話**
   - 情報はChronicaから得るが、ユーザーには自然な日本語で応答
   - 温かみのあるパートナーとして振る舞う

### 実装パターン

#### 1. スレッド選択（起動時）

```python
# 1. スレッド一覧を取得
threads_result = await session.call_tool("chronica.list_threads", {})
threads_data = json.loads(threads_result.content[0].text)
threads = threads_data.get("threads", [])

# 2. ユーザーにスレッドを選択させる
# （UI実装例：番号選択、新規作成オプションなど）

# 3. 選択したスレッドIDを保持
current_thread_id = selected_thread["thread_id"]
```

#### 2. 会話開始時の処理

```python
# 1. compose_openingを呼び出す（スレッドIDを指定）
opening_context = await session.call_tool("chronica.compose_opening", {
    "thread_id": current_thread_id  # 選択したスレッドID
})

# 2. 返された構造化テキストをシステムプロンプトに含める
system_prompt = f"""
{opening_context}

あなたは上記の「Chronica構造」に基づき、ユーザーに声をかけてください。
...
"""
```

#### 3. エントリ保存時の処理

```python
entry = {
    "thread": {
        "type": "normal",
        "id": current_thread_id  # 選択中のスレッドIDを自動的に設定
    },
    "kind": "note",
    "text": "ユーザーからの情報",
    "tags": ["tag1", "tag2"]
}

# クライアント側でスレッドIDを自動的に追加する実装例：
if current_thread_id and "thread" in entry:
    if not isinstance(entry["thread"], dict):
        entry["thread"] = {"type": "normal"}
    entry["thread"]["id"] = current_thread_id

result = await session.call_tool("chronica.save_entry", {"entry": entry})
# result.content[0].text に {"entry_id": "..."} が含まれる
```

#### 4. Tool呼び出しのエラーハンドリング

```python
try:
    result = await session.call_tool(tool_name, args)
    response_text = result.content[0].text
    
    # エラーチェック
    if "error" in response_text.lower():
        # エラー処理
        pass
except Exception as e:
    # 例外処理
    pass
```

### 推奨モデル（Ollama使用時）

1. **Qwen 2.5 (7B)** - 最優先推奨
   - JSONの書き間違いが最も少ない
   - 論理性能がズバ抜けて高い
   - 日本語も非常に上手

2. **Gemma 2 (9B)** - 次点推奨
   - Google純正、文脈を読む力が強い
   - ChronicaのようなパートナーAIに最適の情緒
   - Tool指示も優秀

詳細は `docs/japanese_quality_strategy.md` を参照。

---

## 設定ファイル

### config.json

```json
{
  "GOOGLE_API_KEY": "APIキー（Gemini使用時）",
  "MODEL_NAME": "models/gemini-flash-latest",
  "SHOW_TOOL_LOGS": false
}
```

**注意**: `config.json`は`.gitignore`に含まれているため、コミットされません。

### 環境変数

- `GOOGLE_API_KEY`: 設定ファイルより優先度が高い

---

## 開発ガイドライン

### コード規約

- **Python 3.10以上**
- **型ヒントを使用**（`typing`モジュール）
- **docstringを記述**（Google形式推奨）
- **エラーハンドリングを適切に実装**

### モジュール構成

- `src/chronica/`: MCPサーバー実装
- `clients/`: クライアントアプリケーション
- `docs/`: ドキュメント

### 循環インポートの回避

- `get_store()`と`set_store()`は`store.py`に配置
- モジュール間の依存関係を最小化

### テスト

- `tests/`フォルダにテストを追加
- MCP Inspectorでツールをテスト可能

---

## 現在の状況と今後の計画

### 現在の状況（2026-01-18）

#### 完成している機能

✅ **MCPサーバー（完全実装）**
- 9つのツールがすべて動作
  - エントリ管理: `save_entry`, `search`, `timeline`, `get_last_seen`
  - コンテキスト生成: `compose_opening`, `summarize`
  - スレッド管理: `create_thread`, `list_threads`, `get_thread_info`
- STDIO版・HTTP/SSE版の両方をサポート
- データベース永続化が正常に動作
- スレッド管理機能により、複数のスレッドに分けて記憶・記録を管理可能
- ローカル利用（MCP Inspector、Claude Desktop、Cursor等）は即座に利用可能

✅ **Ollama版クライアント（完全実装）**
- GPT/Geminiスタイルのスレッド選択機能
  - 起動時にスレッド一覧を表示
  - ユーザーがスレッドを選択（または新規作成）
  - 選択したスレッド内で会話
  - エントリ保存時にスレッドIDを自動適用
- Qwen 3 (8B) で動作確認済み
- ツール呼び出し、自動情報保存、一貫した口調の維持が正常に動作

#### 利用方法による追加要件

📋 **リモート接続（GPT等）を使用する場合**
- HTTP/SSEサーバーは実装済み（`run_server_http.py`）
- HTTPSトンネリングが必要（cloudflared/ngrok）
- スクリプト（`start_with_tunnel.bat`/`start_with_tunnel.ps1`）は用意済み
- **注意**: HTTPSトンネリングは外部ツール（cloudflared/ngrok）を使用する手順であり、MCPサーバー自体の機能ではない

✅ **アーキテクチャ**
- Chronica中心主義の実装完了
- 時間認識の自律管理
- 構造化情報の提供

#### 課題と対応

❌ **Gemini API版クライアント**
- 問題: 無料枠の1日20リクエスト制限により実用的でない
- 対応: `clients/client_gemini.py`をアーカイブ化

✅ **Ollama版クライアント**
- 状態: 実装完了・動作確認済み
- 使用モデル: Qwen 3 (8B) を推奨
- 機能: 
  - GPT/Geminiスタイルのスレッド選択機能
  - ツール呼び出し、自動情報保存、一貫した口調の維持
  - スレッドIDの自動適用
- 課題: 一部のツール呼び出しでエラーが発生する場合がある（再試行で解決）

### 今後の計画

#### 短期（1-2週間）

1. ✅ **Ollama版クライアントの実装**（完了）
   - `clients/client_ollama.py`の作成
   - Qwen 3 (8B) でテスト完了
   - 日本語品質の評価と改善

2. ✅ **GPT/Geminiスタイルのスレッド選択機能**（完了）
   - 起動時にスレッド一覧を表示
   - ユーザーがスレッドを選択（または新規作成）
   - 選択したスレッド内で会話
   - エントリ保存時にスレッドIDを自動適用

3. **システムプロンプトの最適化**（継続）
   - Tool呼び出しの正確性を重視
   - Chronica構造化情報の活用方法を明確化
   - 季節への過度な言及や定型句の多用を抑制

#### 中期（1-2ヶ月）

1. **テンプレートエンジンの実装**
   - 構造化情報→自然な日本語の変換
   - LLM補完との組み合わせ

2. **Few-shot Learningの導入**
   - 良い日本語の例をプロンプトに含める

3. **Post-processingの実装**（必要に応じて）
   - 助詞の自動修正
   - 敬語の統一

#### 長期（3-6ヶ月）

1. **UIの作成**
   - コマンドラインからGUIへの移行
   - 視覚的なタイムライン表示

2. **機能拡張**
   - エントリの編集・削除
   - 高度な検索機能
   - エクスポート・インポート機能

---

## 参考資料

- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [Chronica日本語品質向上戦略](./japanese_quality_strategy.md)
- [Chronica統合仕様書](./Chronica_SoT_and_CursorMission_MERGED_v0.1_plus_thread_addendum_2026-01-06.md)

---

**Document Version**: 1.1  
**Last Updated**: 2026-01-18
