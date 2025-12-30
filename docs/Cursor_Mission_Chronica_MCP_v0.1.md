# Cursor Mission：Chronica MCP Server 実装指示 v0.1（Python）
作成日：2025-12-30（JST）  
対象リポジトリ：`C:\Dev\Chronica\`  
正（Single Source of Truth）：`docs/Chronica_Spec_Integrated_v0.1.md`（統合版）

> 本書は **Cursorに投げるための実装指示書**です。  
> このスレッドではコーディングしない前提のため、実装内容（何をどう作るか）だけを明確化します。

---

## 1. ゴール（v0.1）
- Pythonで **Chronica MCP Server** を実装する
- ツール面（Tool Surface）を v0.1 として提供する（6ツール）
- 永続化は **SQLite 1ファイル**（`C:\Dev\Chronica\data\chronica.sqlite3`）
- Chronicaは **自然文を生成しない**（Summary Pack / Opening Pack の“材料”を返す＋保存）
- テストは **MCP Inspector** で Tools の手動呼び出しが通るところまで

根拠：MCPの公式Python SDKと開発ガイド／Inspector。 citeturn0search1turn0search4turn0search0turn0search6

---

## 2. 非目標（v0.1）
- UI/アプリ化（Apps SDKのUI）はやらない（将来） citeturn0search17
- 高度な自然言語日時パーサはやらない（嘘を作らない最小対応のみ）
- マルチユーザー、認証、公開HTTPSは v0.2+（将来）  
  ※ChatGPTへリモート接続する場合は HTTPS 到達性が必要になるが v0.1では優先しない。 citeturn0search13turn0search7

---

## 3. 採用技術（固定）
- 言語：Python
- MCP：**modelcontextprotocol/python-sdk**（公式） citeturn0search1
- 永続化：SQLite（1ファイル）
- OS：Windows（ユーザー環境）

補助：スキャフォールドとして `create-python-server` を利用しても良い（任意）。 citeturn0search3

---

## 4. 実装対象（Tool Surface v0.1）
以下の6ツールを実装する。引数名・戻り値は統合版に従う。

### 4.1 Save / Read
- `chronica.save_entry(...) -> { entry_id }`
- `chronica.search(...) -> entries[]`
- `chronica.timeline(...) -> entries[]`
- `chronica.get_last_seen(...) -> { last_seen_time }`

### 4.2 Compose / Summarize
- `chronica.compose_opening(...) -> opening_pack`
- `chronica.summarize(...) -> summary_pack`

---

## 5. フォルダ構造（現状に合わせる）
- `C:\Dev\Chronica\src\chronica\`：実装（既存）
- `C:\Dev\Chronica\data\`：SQLite DB置き場（既存）
- `C:\Dev\Chronica\tests\`：テスト（既存）
- `C:\Dev\Chronica\docs\`：仕様（統合版が正）

---

## 6. Store（SQLite）実装要件（v0.1）
### 6.1 テーブル
- `entries` を作る（統合版に準拠）
- 最低限必要なインデックス：
  - `saved_time`（期間検索）
  - `thread_type, kind`（フィルタ）

### 6.2 保存仕様
- `saved_time` はChronicaがJSTで付与（ISO文字列）
- `event_time` は v0.1 では raw/resolved/confidence を持つが、解釈不能なら resolved を作らない（rawのみでも可）
- `tags` は v0.1では JSON配列として保存して良い（正規化は v0.2）

---

## 7. timeparse（相対日時）要件（v0.1最小）
### 7.1 目的
- `event_time_raw` を受け取ったときに、**確信が持てる範囲だけ** `resolved` を作る

### 7.2 最小対応（JST anchor_time 基準）
- 今日 / 昨日 / 明日
- 今週 / 来週（代表点でよい：週の開始日00:00 等）
- 今月 / 来月
- 月末（当月末の00:00）
- 「〇日」（当月の指定日：anchor_time との整合が取れない場合は resolved を作らない）

### 7.3 ポリシー
- **嘘を作らない**：自信が低ければ `resolved` を省略し、rawを残す
- `confidence` は 0.0〜1.0（目安でよい）

---

## 8. compose_opening 実装要件（v0.1.1）
### 8.1 入力
- `anchor_time`（必須）
- `thread_type`（必須：normal/project）
- `last_seen_time`（任意：無ければDBから `get_last_seen` で補える）
- `smalltalk_level`（推奨：normal=always, project=off）

### 8.2 出力
- `opening_text`
- `parts`: greeting / gap / season
- `meta`: time_bucket / gap_bucket / season_key

### 8.3 ルール（固定）
- time_bucket：morning / afternoon / evening / late
- gap_bucket：within_2h / within_24h / within_7d / over_7d
- season_key：month→ winter/spring/summer/autumn（厳密でなくてよい）

---

## 9. summarize 実装要件（Summary Pack v0.1.2）
### 9.1 基本
- 入力：mode（daily/weekly/decision）, range, thread_type（normal/project）
- DBから entries を取得し、構造化して返す（自然文を作らない）

### 9.2 出力（必須フィールド群）
- `meta`（thread/range/stats など）
- `timeline_items[]`
- `decisions[]`
- `actions[]`
- `open_questions[]`
- `digest_candidates`（v0.1.2拡張を含む）
  - `highlights[]`
  - `blockers[]`
  - `next_priorities[]`
  - `memory_keep[]`（通常スレッド向け）
  - `next_talk_seed`（通常スレッド向け）

### 9.3 スレッド方針
- project：D/A/Q を欠落させない（ゼロなら空配列で返す）
- normal：`memory_keep` と `next_talk_seed` を生成できると価値が出る（捏造は不要。無理なら空で返す）

---

## 10. MCPサーバー起動とデバッグ要件
### 10.1 起動
- Python SDKでサーバーを構成し、STDIOで起動できること（ローカル運用の最小） citeturn0search4turn0search1

### 10.2 Inspectorで確認
- MCP Inspector から接続し、Toolsが呼べること  
  （Inspectorは `mcp.json` のエクスポートができ、Cursor等への接続設定にも流用できる） citeturn0search0turn0search6

---

## 11. 受け入れ条件（Definition of Done）
- DBファイルが `data/chronica.sqlite3` に作成される
- `save_entry` が1件保存でき、`search/timeline/get_last_seen` が正しく動く
- `compose_opening` が thread_type に応じた opening_pack を返す
- `summarize(daily, today, normal)` が Summary Pack v0.1.2 の構造を満たして返る
- Inspector上で6ツールが呼べる（手動テストでOK） citeturn0search0turn0search6

---

## 12. 実装順（推奨：手戻り最小）
- Store（DB + save/search/timeline/get_last_seen）
- Opening（compose_opening）
- Summarize（summary_packの骨格 → timeline_items → digest_candidates → D/A/Q）
- Inspectorで結線と動作確認

---

## 13. 将来（v0.2+）メモ（今は実装しない）
- リモート接続（SSE / streaming HTTP）＋認証（OAuth等）  
  ※ChatGPT Developer Modeでの接続要件として公式に言及あり。 citeturn0search7turn0search13
- relations（Entry間リンク）
- tags正規化、multi-user
