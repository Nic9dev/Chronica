# Chronica System Reference

**Version**: 0.5.0  
**Last Updated**: 2026-03-21  
**Status**: Production Ready (Claude Desktop / MCP STDIO + キュレーションUI)

---

## 目次

1. [システム概要](#システム概要)
2. [アーキテクチャ](#アーキテクチャ)
3. [UIの役割定義](#uiの役割定義)
4. [プロジェクト構造](#プロジェクト構造)
5. [MCPサーバー](#mcpサーバー)
6. [ツール仕様](#ツール仕様)
7. [データベーススキーマ](#データベーススキーマ)
8. [データモデル](#データモデル)
9. [Store API（永続化層）](#store-api永続化層)
10. [キュレーションUI](#キュレーションui)
11. [Claude Desktop設定](#claude-desktop設定)
12. [opening.py コンテキスト仕様](#openingpy-コンテキスト仕様)
13. [開発ガイドライン](#開発ガイドライン)
14. [現在の状況と今後の計画](#現在の状況と今後の計画)

---

## システム概要

Chronicaは、個人の記憶を管理する **Claude Desktop専用のMCP（Model Context Protocol）サーバー** です。

### 設計思想

**Chronica中心主義（Chronica-Centric Architecture）**

- **Chronica（サーバー）が構造と時間の絶対的な正解を持つ**
- **Claude はそのインターフェースに徹する**
- Claudeは外部ツール（Chronica）から渡された「構造化されたテキスト」のみを正解として扱い、幻覚（Hallucination）を防ぐ
- 「Chronicaによると〜」のようなメタ発言を避け、自然な日本語で対話する

### 変更履歴

**v0.4.0 → v0.5.0（2026-03-21）**

| 項目 | 変更内容 |
|------|---------|
| ツール名 | `chronica.save_entry` → `chronica_save_entry` 等（Claude Desktop の命名規則 `^[a-zA-Z0-9_-]{1,64}$` に対応） |
| `tools.py` | `save_entry` と `search` の description を拡充（保存すべきタイミング、能動的な記憶参照） |
| `setup_config.py` | MSIX版優先の `get_config_path()` に変更、`cmd/c` ラッパー削除 |
| `opening.py` | `get_last_seen` → `get_last_interaction` 修正、`saved_time` パースエラー対策 |
| `run_server.py` | 起動時の cwd をプロジェクトルートに固定 |
| 削除 | `clients/` フォルダ、`docs/` 内の一部ドキュメント（Claude Desktop実装ガイド、日本語品質戦略等） |

**v0.3.0 → v0.4.0（2026-03-19）**

| 項目 | 変更内容 |
|------|---------|
| UIの役割 | **記憶のキュレーター** として明確化。チャットは Claude Desktop で完結 |
| `app_curation.py` | 新規追加。記憶の一覧・選別・削除・トークン可視化 |
| `store.py` | `delete_entry()`, `delete_entries()`, `get_all_tags()` を追加 |
| `requirements.txt` | `tiktoken` を追加（トークンカウント用） |
| 起動スクリプト | `run_curation.ps1`, `run_curation.bat` を追加 |
| タイムゾーン | JST固定 → PCローカル時間（自動検出）に変更 |

**v0.2.0 → v0.3.0**

| 項目 | 変更内容 |
|------|---------|
| AIクライアント | Gemini API / Ollama → **Claude Desktop専用** に統一 |
| MCPサーバー | STDIO版のみ残存（HTTP/SSE版を廃止） |
| `opening.py` | `compose_opening_logic()` → **`compose_opening_context(store, thread_id)`** に刷新 |
| `tools.py` | Claude向け説明文・注意事項を追加、インポートを整理 |
| `requirements.txt` | 不要パッケージ（fastapi / uvicorn / google-genai / ollama / httpx）を削除 |
| 削除ファイル | `clients/client_gemini.py`, `clients/client_ollama.py`, `src/chronica/server_http.py`, `run_server_http.py`, `start_with_tunnel.bat`, `start_with_tunnel.ps1`, `config.json` |

---

## アーキテクチャ

### 全体構成（Claude Desktop専用）

```
┌────────────────────────────────────────┐
│      Claude Desktop (Sonnet系)         │
│   - ユーザーとの対話                    │
│   - Tool呼び出し（自動）                │
│   - 自然な日本語で応答                  │
└────────────────┬───────────────────────┘
                 │ MCP Protocol (STDIO)
                 │ 標準入出力
┌────────────────▼───────────────────────┐
│     Chronica MCP Server (Python)       │
│  ┌──────────────────────────────────┐  │
│  │  Tools Layer (tools.py)          │  │
│  │  - 9つのMCPツールを提供           │  │
│  └──────────────────────────────────┘  │
│  ┌──────────────────────────────────┐  │
│  │  Logic Layer                     │  │
│  │  - opening.py: コンテキスト生成   │  │
│  │  - summarize.py: サマリー生成     │  │
│  │  - timeparse.py: 相対日時パース   │  │
│  └──────────────────────────────────┘  │
│  ┌──────────────────────────────────┐  │
│  │  Data Layer (store.py)           │  │
│  │  - SQLite永続化                   │  │
│  │  - エントリのCRUD操作             │  │
│  └──────────────────────────────────┘  │
└────────────────┬───────────────────────┘
                 │ SQLite
┌────────────────▼───────────────────────┐
│         data/chronica.sqlite3          │
│  - entries テーブル                    │
│  - threads テーブル                    │
└────────────────────────────────────────┘
```

### データフロー

**1. 会話開始時**:
```
Claude → chronica_compose_opening()
→ Chronicaがdatetime.now(JST)で時間確定
→ 前回エントリ・経過時間・指示文を含むコンテキストを返す
→ Claudeがそれを「絶対的な事実」として自然な挨拶に使う
```

**2. エントリ保存時**:
```
（ユーザーが情報を話す。「覚えておいて」「今日〇〇をした」等）
→ Claude が自律的に chronica_save_entry(entry) を呼ぶ
→ StoreがSQLiteに保存 → entry_idを返す
→ Claudeは「保存しました」等のメタ発言をせず、自然に会話を続ける
```

**3. 検索・タイムライン取得時**:
```
Claude → chronica_search() / chronica_timeline()
→ 関連テーマが出たら能動的に裏側で検索
→ エントリリストを返す → Claudeが日本語で要約し、自然に会話に織り込む
```

---

## UIの役割定義

Chronica は **3層の役割分担** で構成されます。

```
┌─────────────────────────────────────┐
│     Claude Desktop（対話）           │
│  - ユーザーとの会話                  │
│  - 自動的に記憶を保存                │
│  - 記憶を引き出して応答              │
└────────────────┬────────────────────┘
                 │ 自動保存
┌────────────────▼────────────────────┐
│   Chronica MCP（記憶蓄積）           │
│  - SQLiteに永続化                    │
│  - すべての会話を保存                │
│  - 時系列管理                        │
└────────────────┬────────────────────┘
                 │ 閲覧・選別
┌────────────────▼────────────────────┐
│   Streamlit UI（キュレーション）     │
│  - 記憶の一覧表示                    │
│  - 冗長・重複の確認                  │
│  - 削除のみ（編集不可）              │
│  - トークン削減                      │
└─────────────────────────────────────┘
```

### UIの役割（まとめ）

| 項目 | 内容 |
|------|------|
| ✅ 記憶の選別を行う場所 | 一覧表示・フィルタ・削除 |
| ✅ 冗長・重複記憶の確認 | トークン可視化・TOP 10 表示 |
| ✅ 不要な記憶の削除 | 削除のみ、編集不可 |
| ✅ トークン使用量の可視化 | 総トークン数・使用率・上限設定 |
| ❌ チャットUI | Claude Desktop で完結 |
| ❌ 記憶の編集 | ハルシネーション予防のため編集不可 |

**削除のみ・編集不可の理由**:
1. **ハルシネーション予防** - Claude が保存した記憶を人間が改変すると、次回 Claude が混乱する可能性
2. **信頼性の担保** - 「Claude が実際に保存した記憶」として真実性を保証
3. **シンプル化** - 編集UIは複雑でバグの温床になりやすい

---

## プロジェクト構造

```
Chronica/
├── src/
│   ├── __init__.py            # パッケージ初期化
│   └── chronica/              # MCPサーバー実装（コア）
│       ├── __init__.py
│       ├── server.py          # STDIOサーバー（Claude Desktopから起動）
│       ├── tools.py           # MCPツール定義・実装（Claude向け最適化）
│       ├── store.py           # データベース層（SQLite）
│       ├── opening.py         # コンテキスト生成ロジック（Claude向け最適化）
│       ├── summarize.py       # サマリー生成ロジック
│       └── timeparse.py       # 相対日時パーサー
│
├── docs/                      # ドキュメント
│   └── system_reference.md    # 本ドキュメント
│
├── scripts/                   # セットアップスクリプト
│   └── setup_config.py       # Claude Desktop / Claude Code 設定登録（MSIX版優先）
│
├── ui/                        # （任意）ローカルUIモジュール
│   ├── styles.py              # CSSテーマ定義
│   └── renderer.py            # ピクセルアート描画
│
├── assets/                    # アセット
│   └── pixel_sui.py           # Sui（翠）のピクセルアートデータ
│
├── data/                      # データベース（.gitignore）
│   └── chronica.sqlite3       # SQLiteデータベース
│
├── app.py                     # Streamlit UI（チャット・Sui）※任意
├── app_curation.py            # キュレーションUI（記憶の選別・削除・トークン可視化）
├── run_server.py              # MCPサーバー起動スクリプト（STDIO）
├── run_chronica_mcp.py        # Claude Code用ランチャー（.mcp.jsonから呼ばれる）
├── .mcp.json                  # Claude Code用MCP設定（プロジェクトスコープ）
├── setup.ps1 / setup.sh / setup.bat  # セットアップスクリプト（venv作成・設定登録）
├── run_ui.bat                 # チャットUI起動スクリプト（Windows）
├── run_ui.ps1                 # チャットUI起動スクリプト（PowerShell）
├── run_curation.bat           # キュレーションUI起動スクリプト（Windows）
├── run_curation.ps1           # キュレーションUI起動スクリプト（PowerShell）
├── requirements.txt           # Python依存関係
├── README.md                  # プロジェクト概要
└── .gitignore
```

---

## MCPサーバー

### 起動方法

#### STDIO版（Claude Desktop専用）

```powershell
python run_server.py
```

- Claude Desktop が `claude_desktop_config.json` の設定を元に自動起動する
- 標準入出力（STDIO）でClaude Desktopと通信
- 手動起動はデバッグ・MCP Inspector接続時のみ

### サーバー実装

**ファイル**: `src/chronica/server.py`

```python
from .store import Store, set_store
from .tools import register_tools

def create_server() -> Server:
    server = Server("chronica")
    store = Store()
    set_store(store)
    register_tools(server)
    return server

async def main():
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
```

**ポイント**:
- `set_store` は `store.py` からインポート（`tools.py` からではない）
- `set_store(store)` でグローバルインスタンスを設定し、各ツールから `get_store()` で参照

---

## ツール仕様

Chronicaは9つのMCPツールを提供します。ツール名は Claude Desktop の命名規則（`^[a-zA-Z0-9_-]{1,64}$`）に従い、アンダースコア区切り（例: `chronica_save_entry`）を使用します。

### 1. `chronica_save_entry`

エントリ（記憶・記録）を保存します。

**使用タイミング**:
- ユーザーが新しい情報を提供したとき
- 重要な決定事項があったとき
- タスクや未決事項が発生したとき
- 出来事や質問があったとき

**保存すべきタイミング**:
- 「覚えておいて」「忘れないで」「記録して」などの発言
- 「今日〇〇をした」「〇〇に決めた」「〇〇をやる予定」
- 新しい事実・決定・予定・気づき・感情が含まれる発言
- 迷ったら保存する。保存しすぎるほうが保存漏れより良い。
- 「保存しました」等の報告は不要。会話を自然に続ける。

**Claude向けの注意**:
- ユーザーに「保存しました」等の確認は不要
- 自然に会話を続ける
- メタ発言（「Chronicaに保存します」等）は避ける

**引数**:
```json
{
  "entry": {
    "thread": {
      "type": "normal" | "project",
      "id": "thread-uuid"         // オプション
    },
    "kind": "note" | "event" | "decision" | "action" | "question",
    "text": "エントリの本文",
    "tags": ["tag1", "tag2"],
    "title": "タイトル",           // オプション
    "event_time": {                // オプション
      "raw": "今日" | "昨日" | "明日" | "3日前" | ...
    },
    "project": "プロジェクト名"    // オプション
  }
}
```

**必須フィールド**: `thread.type`, `kind`, `text`, `tags`

**戻り値**:
```json
{ "entry_id": "生成されたエントリID" }
```

**エラー**:
- `validation_error`: 必須フィールドが不足
- `save_error`: データベース保存エラー

---

### 2. `chronica_search`

保存されたエントリを検索します。

**使用タイミング**:
- ユーザーが「最近の〜を振り返りたい」と言ったとき
- 特定のタグやトピックの記録を探すとき

**能動的な記憶参照**:
- ユーザーの発言に既存の記憶と関連しそうなテーマが出てきたら、会話を止めずに裏側で search を呼ぶこと。
- 関連記憶が見つかった場合、「Chronicaによると〜」等のメタ発言は不要。その記憶を自然に会話に織り込む。
- 例：ユーザーが仕事の悩みを話す → 過去の関連決定事項を検索 → 「以前〇〇と決めていましたよね」と自然につなげる。

**引数**:
```json
{
  "thread_id": "thread-uuid",           // オプション（指定時はthread_typeより優先）
  "thread_type": "normal" | "project",  // オプション
  "kind": "note",                        // オプション
  "tags": ["tag1", "tag2"],             // オプション（いずれか一致）
  "project": "プロジェクト名",           // オプション
  "limit": 100                           // オプション、デフォルト: 100
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

---

### 3. `chronica_timeline`

期間指定でタイムラインを取得します。

**引数**:
```json
{
  "start_time": "2026-01-01T00:00:00+09:00",  // オプション
  "end_time": "2026-03-31T23:59:59+09:00",    // オプション
  "thread_id": "thread-uuid",                 // オプション
  "thread_type": "normal" | "project",        // オプション
  "kind": "note",                              // オプション
  "limit": 100                                 // オプション、デフォルト: 100
}
```

**戻り値**: `chronica_search` と同じ形式

---

### 4. `chronica_get_last_seen`

指定スレッドタイプで最後に見た時刻を取得します。

**引数**:
```json
{ "thread_type": "normal" | "project" }  // 必須
```

**戻り値**:
```json
{ "last_seen_time": "2026-03-18T00:00:00+09:00" | null }
```

---

### 5. `chronica_compose_opening`

**会話開始時に必ず呼び出すこと。**  
現在時刻・前回会話の経過時間・記憶コンテキストを取得します。

**Claude向けの指示**:
- 返された情報が絶対的な事実
- 自分で時間を推測しない
- 季節への過度な言及は避ける
- 「Chronicaによると」等のメタ発言は避ける
- 自然に「お久しぶりです」「前回は〜について話していましたね」等と声をかける

**引数**:
```json
{ "thread_id": "thread-uuid" }  // オプション
```

**戻り値**: 構造化されたコンテキストテキスト（文字列）

```
=== Chronica Context ===
[現在状況]
- 現在時刻: 2026-03-18 21:00:00
- 時間帯: 春の夜

[記憶コンテキスト]
- 前回の会話: 2日前
- 前回のトピック: Chronicaをclaude Desktop専用に移行する作業をした

[Claude への指示]
1. 上記の情報を基に、自然に声をかけてください
2. 時間差に応じた挨拶（例: 「お久しぶりです」「こんにちは」）
3. 前回のトピックに自然に触れる
4. 季節や時間帯への過度な言及は避ける
5. 「Chronicaによると」等のメタ発言は避ける
6. ユーザーから新しい情報が得られたら chronica_save_entry で保存
7. 保存時に「保存しました」等の確認は不要

【良い例】
「お久しぶりです！前回はChronicaのClaude Desktop移行作業をしていましたね。その後うまくいきましたか？」

【悪い例】
「こんにちは！春の夜ですね。Chronicaによると前回は2日前に会話していたようです。」

=== End of Context ===
```

**実装**: `src/chronica/opening.py` の `compose_opening_context(store, thread_id)` が生成

---

### 6. `chronica_summarize`

サマリーパックを生成します（Summary Pack v0.1.2）。

**引数**:
```json
{
  "mode": "daily" | "weekly" | "decision",
  "range_start": "2026-03-01T00:00:00+09:00",
  "range_end": "2026-03-31T23:59:59+09:00",
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

### 7. `chronica_create_thread`

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
{ "thread_id": "生成されたスレッドID", "thread_name": "...", "thread_type": "normal" }
```

---

### 8. `chronica_list_threads`

スレッド一覧を取得します。

**引数**:
```json
{ "thread_type": "normal" | "project" }  // オプション、省略時は全て
```

**戻り値**:
```json
{
  "threads": [
    {
      "thread_id": "thread-uuid",
      "thread_name": "スレッド名",
      "thread_type": "normal",
      "created_at": "...",
      "updated_at": "...",
      "entry_count": 10
    }
  ]
}
```

---

### 9. `chronica_get_thread_info`

指定スレッドの詳細情報を取得します。

**引数**:
```json
{ "thread_id": "thread-uuid" }  // 必須
```

**戻り値**:
```json
{
  "thread_id": "thread-uuid",
  "thread_name": "スレッド名",
  "thread_type": "normal",
  "created_at": "...",
  "updated_at": "...",
  "entry_count": 10
}
```

**エラー**:
- `not_found`: 指定されたスレッドIDが存在しない

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
    thread_id TEXT,
    thread_type TEXT NOT NULL,
    thread_name TEXT,
    kind TEXT NOT NULL,
    title TEXT,
    text TEXT NOT NULL,
    tags TEXT,          -- JSON配列
    project TEXT,
    links_source TEXT,
    links_refs TEXT,    -- JSON配列
    created_at TEXT NOT NULL
);

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
- **タイムゾーン**: PCのシステムタイムゾーン（自動検出）
- **文字エンコーディング**: UTF-8
- **自動作成**: `Store.__init__` で自動的にDBとテーブルを作成

---

## データモデル

### Entry JSON（完全形）

```json
{
  "version": "0.1",
  "entry_id": "uuid-string",
  "saved_time": "2026-03-18T21:00:00+09:00",
  "thread": {
    "type": "normal" | "project",
    "id": "thread-uuid",     // オプション
    "name": "スレッド名"      // オプション
  },
  "kind": "note" | "event" | "decision" | "action" | "question",
  "text": "エントリの本文",
  "tags": ["tag1", "tag2"],
  "title": "タイトル",        // オプション
  "event_time": {             // オプション
    "raw": "今日",
    "resolved": "2026-03-18T00:00:00+09:00",
    "confidence": 1.0
  },
  "project": "プロジェクト名", // オプション
  "links": {                  // オプション
    "source": "source-entry-id",
    "refs": ["ref-entry-id-1"]
  }
}
```

### kind の意味

| 値 | 意味 |
|----|------|
| `note` | 一般的な記録 |
| `event` | 出来事 |
| `decision` | 決定事項 |
| `action` | タスク・アクション |
| `question` | 未決事項・質問 |

### thread.type の意味

| 値 | 意味 |
|----|------|
| `normal` | 通常の会話（親近感のあるトーン） |
| `project` | プロジェクト関連（信頼感のあるトーン） |

---

## Store API（永続化層）

**ファイル**: `src/chronica/store.py`

### 主要メソッド

| メソッド | 説明 | 戻り値 |
|----------|------|--------|
| `save_entry(entry)` | エントリを保存 | `str` (entry_id) |
| `search(...)` | エントリを検索 | `List[Dict]` |
| `timeline(...)` | タイムラインを取得 | `List[Dict]` |
| `delete_entry(entry_id)` | エントリを削除 | `bool` |
| `delete_entries(entry_ids)` | 複数エントリを削除（バッチ） | `int` (削除件数) |
| `get_all_tags()` | 全エントリからユニークなタグを取得 | `List[str]` |
| `get_last_seen(thread_type)` | 最後に見た時刻を取得 | `Optional[str]` |
| `create_thread(...)` | スレッドを作成 | `str` (thread_id) |
| `list_threads(...)` | スレッド一覧を取得 | `List[Dict]` |
| `get_thread_info(thread_id)` | スレッド情報を取得 | `Optional[Dict]` |

### 削除機能の注意

- **UI専用**: `delete_entry` / `delete_entries` は MCP ツールとして公開していない
- **理由**: Claude が誤って削除しないよう、キュレーションUIからのみ実行可能

---

## キュレーションUI

**ファイル**: `app_curation.py`  
**起動**: `python -m streamlit run app_curation.py` または `.\run_curation.ps1`

### 機能一覧

| 機能 | 説明 |
|------|------|
| 記憶の一覧表示 | カードスタイル、kind ごとの絵文字（note/event/decision/action/question） |
| フィルタリング | 種別、タグ（複数選択）、並び順（最新順/古い順） |
| トークン使用状況 | 総トークン数、使用率、プログレスバー、上限設定（サイドバー） |
| TOP 10 | トークン数の多い記憶を展開表示 |
| 表示件数・ページネーション | 10/25/50/100/すべて、ページ切り替え |
| 削除 | 削除ボタン → 確認ダイアログ → 削除実行（編集不可） |

### 設計方針

- **編集不可**: ハルシネーション予防のため、記憶の編集は行わない
- **削除のみ**: 不要な記憶は削除で対応
- **トークン可視化**: トークン上限（デフォルト 20,000）をサイドバーで変更可能

### 今後の拡張（Phase 2 以降）

- 重複検出（TF-IDF + コサイン類似度）
- バッチ削除（チェックボックスで複数選択）
- 検索機能（全文検索）
- エクスポート（JSON/CSV）
- 統計情報（記憶数の推移グラフ等）

---

## Claude Desktop設定

### 設定ファイルの場所

**Windows**:
- **MSIX版**（claude.ai からダウンロード）: `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\claude_desktop_config.json`
- **従来版**（exe インストール）: `%APPDATA%\Claude\claude_desktop_config.json`
- `scripts/setup_config.py` が MSIX 版を優先して自動検出・書き込み

**macOS**:
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

### 設定内容（Windows例）

```json
{
  "mcpServers": {
    "chronica": {
      "command": "C:/Dev/Chronica/.venv/Scripts/python.exe",
      "args": ["C:/Dev/Chronica/run_server.py"],
      "env": {
        "PYTHONPATH": "C:/Dev/Chronica/src"
      }
    }
  }
}
```

- `command` は Python 実行ファイルのフルパス（venv 内の python.exe を推奨）
- `args` は `run_server.py` のフルパス（`cmd /c` ラッパーは不要）
- Windows ではパス区切りに `/` を使用（`\` は不可）
- 設定後は Claude Desktop を再起動すること
- セットアップ: `.\setup.ps1` または `python scripts/setup_config.py` で自動登録

### 動作確認

1. Claude Desktopを再起動
2. 新しい会話を開始
3. 「Chronicaツールを使って記憶を確認して」と送信
4. Claudeが `chronica_compose_opening` を自動で呼び出すことを確認

---

## opening.py コンテキスト仕様

### 関数シグネチャ

```python
def compose_opening_context(store: Store, thread_id: str = None) -> str:
```

### 生成される情報

1. **現在時刻**（PCのシステムタイムゾーンで自動検出）
2. **時間帯**（朝 / 昼 / 夕方 / 夜）
3. **季節**（春 / 夏 / 秋 / 冬）
4. **前回エントリの取得**
   - `thread_id` 指定あり → `store.search(thread_id=..., limit=1)` で取得
   - `thread_id` 指定なし → `store.get_last_interaction(thread_id=None)` で取得
5. **経過時間の表現**（数分前 / 1時間ほど前 / N時間前 / 昨日 / N日前 / N週間前）
6. **Claude向け指示文**（良い例・悪い例を含む）

### tools.py からの呼び出し

```python
# chronica_compose_opening ハンドラ内
from .opening import compose_opening_context

context = compose_opening_context(store, thread_id)
return [types.TextContent(type="text", text=context)]
```

---

## 開発ガイドライン

### コード規約

- **Python 3.10以上**
- **型ヒントを使用**（`typing` モジュール）
- **エラーハンドリングを適切に実装**
- ツールのレスポンスは `json.dumps(..., ensure_ascii=False)` で返す

### モジュール依存関係

```
server.py
  ├── store.py        ← set_store / get_store / Store
  └── tools.py
        ├── store.py  ← get_store
        ├── opening.py ← compose_opening_context
        ├── summarize.py ← summarize
        └── timeparse.py ← parse_event_time

__init__.py
  ├── store.py  ← Store
  ├── opening.py ← compose_opening_context
  ├── summarize.py ← summarize
  └── timeparse.py ← parse_event_time
```

**注意**: `set_store` / `get_store` は `store.py` にのみ定義。`tools.py` はエクスポートしない。

### 依存パッケージ（requirements.txt）

```
mcp>=1.0.0
streamlit>=1.28.0
nest-asyncio>=1.5.0
tiktoken>=0.5.0
tzdata>=2025.1
```

- `tiktoken`: キュレーションUIのトークンカウント用（cl100k_base = GPT-4 系）

### テスト

- MCP Inspectorで各ツールをテスト可能:
  ```powershell
  npx @modelcontextprotocol/inspector .venv\Scripts\python.exe run_server.py
  ```

---

## 現在の状況と今後の計画

### 現在の状況（2026-03-19）

#### 完成している機能

✅ **MCPサーバー（Claude Desktop専用 STDIO）**
- 9つのツールがすべて動作
  - エントリ管理: `chronica_save_entry`, `chronica_search`, `chronica_timeline`, `chronica_get_last_seen`
  - コンテキスト生成: `chronica_compose_opening`, `chronica_summarize`
  - スレッド管理: `chronica_create_thread`, `chronica_list_threads`, `chronica_get_thread_info`
- STDIO版のみサポート（HTTP/SSE版廃止）
- データベース永続化が正常に動作

✅ **キュレーションUI（v0.4.0 で追加）**
- 記憶の一覧表示（カードスタイル、kind 絵文字）
- フィルタリング（種別、タグ、並び順）
- トークン使用状況（総数、使用率、TOP 10）
- 表示件数・ページネーション（10/25/50/100/すべて）
- 削除機能（確認ダイアログ付き、編集不可）
- サイドバーでトークン上限設定（1,000〜100,000）

✅ **Store 拡張**
- `delete_entry(entry_id)` / `delete_entries(entry_ids)` を追加
- `get_all_tags()` を追加（フィルタ用）

✅ **Claude向け最適化（v0.3.0）**
- `opening.py`: Claude向け指示文・良い例/悪い例を含むコンテキスト生成
- `tools.py`: 各ツールの description に Claude向け注意事項を追加
- メタ発言の抑制・自然な日本語応答への誘導

#### 課題と対応

| 課題 | 状態 |
|------|------|
| Gemini API版（無料枠制限で実用不可） | 削除済み |
| Ollama版（応答速度・品質の問題） | 削除済み |
| HTTP/SSE版（複雑な設定が不要になった） | 削除済み |
| `opening.py` の旧実装（メタ発言誘発） | 新実装に置換済み |

### 今後の計画

#### 短期（使用感を確認してから）

- [ ] キュレーションUIの使用感フィードバックに基づく改善
- [ ] Claude Desktop での動作確認・UXテスト
- [ ] `compose_opening` の応答品質確認（メタ発言の有無）
- [ ] `save_entry` 自動呼び出し精度の確認

#### 中期（Phase 2）

- [ ] 重複検出機能（TF-IDF + コサイン類似度）
- [ ] バッチ削除機能（チェックボックスで複数選択）
- [ ] 検索機能（全文検索）
- [ ] エクスポート機能（JSON/CSV）
- [ ] 統計情報（記憶数の推移グラフ等）
- [ ] システムプロンプトの継続的微調整

#### 長期（将来オプション）

- **Phase 3: クラウド同期版** - Supabase統合・複数デバイス対応・E2EE
- **Phase 4: 機能拡張** - タイムライン可視化・高度な分析
- **Phase 5: SaaS化** - マルチテナント・Stripe決済

---

## 参考資料

- [MCP Protocol Specification](https://modelcontextprotocol.io/)

---

**Document Version**: 0.5.0  
**Last Updated**: 2026-03-21
