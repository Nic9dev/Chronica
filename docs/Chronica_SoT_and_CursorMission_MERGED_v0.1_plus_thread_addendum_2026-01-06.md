# Chronica Integrated SoT + Cursor Mission (Merged)

This document merges the following sources **without summarization, omission, or deletion**.

- `Chronica_Spec_Integrated_v0.1.md` (verbatim)
- `Cursor_Mission_Chronica_MCP_v0.1.md` (verbatim)

An addendum is appended to record decisions made in the associated conversation thread.

---

## Source 1 (Verbatim): Chronica_Spec_Integrated_v0.1.md

# Chronica 統合仕様書（Integrated Spec）v0.1
作成日：2025-12-30（JST）  
対象リポジトリ：`C:\Dev\Chronica\`（ユーザー環境）

> **本書が「正（Single Source of Truth）」**です。  
> `docs/` 内の個別ドキュメントは参照用（分割資料）として残して構いませんが、実装判断に迷った場合は **必ず本書を優先**します。

---

## 0. 目的と前提
### 0.1 目的
- **A（ワンショット）→B（定期）→C（常駐）** を、呼び出し元の差し替えだけで段階的に伸ばせる設計にする
- **ローカルLLM不要**。自然文の生成はホスト（ChatGPT）が担当し、Chronica（MCPサーバー）は **材料生成＋保存**に徹する
- **通常（normal）＝親近感** / **プロジェクト（project）＝信頼感** を、スレッド分離で両立する

### 0.2 非目標（v0.1）
- UI/アプリ化はしない
- 高度な自然言語日時パーサはしない（嘘を作らない最小対応のみ）
- 多人数（マルチテナント）はしない（将来拡張に回す）

---

## 1. バージョン一覧（本書で採用する“正”）
| 領域 | 採用バージョン | 備考 |
|---|---:|---|
| Core保存（Entry/Store） | v0.1 | SQLite 1ファイル想定 |
| MCP Tool Surface（API面） | v0.1 | 6ツール |
| Internal Architecture（内部構造） | v0.1 | 4層＋SQLite |
| Summary Pack | **v0.1.2** | `memory_keep / next_talk_seed` を含む |
| Opening Pack | v0.1.1 | `compose_opening`返却 |
| 衛星：週次レビュー職人 | v0.1 | 出力テンプレ固定 |
| 衛星：意思決定ログメーカー | v0.1 | Decision中心で欠落回避 |
| 衛星：日次ダイジェスト | v0.1 | 通常/プロジェクト両対応 |
| 定期B1：日次（通常） | v0.1 | ChatGPT側スケジュール |

---

## 2. 体験設計（通常 / プロジェクト）
### 2.1 通常（normal）
- 狙い：**「覚えていてくれてる」「そんなところに気付くんだ」**を出す
- 日次の価値が高い（突発的に会話量が増える前提）
- オープニング：時間別挨拶＋空けた時間の一言＋季節の軽い話題（毎回でもOK）

### 2.2 プロジェクト（project）
- 狙い：**「整合性が取れてる」「時系列がきちんとしてる」**を出す
- Decision / Action / Question（D/A/Q）を欠落させない
- オープニング：短く（雑談抑制）

---

## 3. Core：保存レコード（Entry）v0.1
### 3.1 コア概念
- Chronicaが保持する1件の記憶を **Entry** と呼ぶ  
  （メモ、週次レビュー、決定ログ、日次ダイジェスト、要約結果…全てEntry）
- 混線防止のため `thread.type` を必ず持つ（`normal` / `project`）

### 3.2 2つの時刻（必須の考え方）
- `saved_time`：Chronicaが保存した時刻（JST固定）
- `event_time`：話題が指す時刻（締切・予定・「来週」等／任意）
  - 解釈できない場合は **resolvedを作らない**（嘘を作らない）

### 3.3 Entry JSON（保存形式・最小）
```json
{
  "version": "0.1",
  "entry_id": "uuid",
  "saved_time": "2025-12-29T09:00:00+09:00",

  "event_time": {
    "raw": "来週火曜",
    "resolved": "2026-01-06T00:00:00+09:00",
    "confidence": 0.6
  },

  "thread": { "type": "project", "name": "Chronica-Project" },

  "kind": "decision_log",
  "title": "意思決定ログ：UIを作らない方針",
  "text": "（本文：Markdown可）",

  "tags": ["chronica", "decision_log"],
  "project": "Chronica",

  "links": { "source": "chatgpt", "refs": ["e_01", "d_01"] }
}
```

### 3.4 フィールド定義（要点）
**必須**
- `version` / `entry_id` / `saved_time` / `thread.type` / `kind` / `text` / `tags`

**任意（あると強い）**
- `event_time`（raw/resolved/confidence）
- `title`, `project`, `links.source`, `links.refs`

---

## 4. MCP Tool Surface（API面）v0.1
Chronicaは以下の6ツールを公開します（最小面）。

### 4.1 Save / Read
1) `chronica.save_entry(...) -> { entry_id }`  
2) `chronica.search(...) -> entries[]`  
3) `chronica.timeline(...) -> entries[]`  
4) `chronica.get_last_seen(...) -> { last_seen_time }`

### 4.2 Compose / Summarize
5) `chronica.compose_opening(...) -> opening_pack`  
6) `chronica.summarize(...) -> summary_pack`

> v0.1方針：Chronicaは「材料を返す」。自然文生成はホスト（ChatGPT）。

---

## 5. Opening Pack（compose_opening）v0.1.1
### 5.1 目的
- 冒頭の1〜2文で、**通常＝親近感** / **プロジェクト＝信頼感** の方向性を安定させる

### 5.2 入力（要点）
- `anchor_time`（JST ISO, 必須）
- `thread_type`（`normal|project`, 必須）
- `last_seen_time`（任意：無ければ `get_last_seen` で補える）
- `smalltalk_level`（推奨：normal=`always`, project=`off`）

### 5.3 出力（要点）
- `opening_text`：冒頭に貼れる文章
- `parts`：greeting / gap / season
- `meta`：time_bucket / gap_bucket / season_key

---

## 6. Summary Pack v0.1.2（Chronicaが返す“材料”）
### 6.1 目的
- ChatGPTが「要約・レビュー・ログ」を作りやすいように、材料を構造化して返す
- 粒度問題（要約＝削除が強い）に備え、**落としたくないものを構造で救う**

### 6.2 トップレベル（要点）
- `meta`：条件・統計・thread
- `timeline_items[]`：時系列の要点
- `decisions[]`：意思決定
- `actions[]`：次アクション
- `open_questions[]`：未決・論点
- `digest_candidates`：要約骨格（v0.1.2拡張）

### 6.3 meta.thread（通常/プロジェクト）
- `meta.thread.type`：`normal | project`
- `meta.thread.opening_style`：`normal_default | project_default`

### 6.4 digest_candidates（v0.1.2）
- `highlights[]`（推奨：最大10）
- `blockers[]`（最大5）
- `next_priorities[]`（最大5）
- `memory_keep[]`（最大5）※通常スレッド向け
- `next_talk_seed`（1行）※通常スレッド向け

> プロジェクトスレッドでは `memory_keep/next_talk_seed` は原則空でOK（雑談抑制）。

---

## 7. 粒度問題の設計解（欠落させない3カテゴリ）
要約本文は圧縮されても構わないが、これだけは欠落させない。

- **Decision**
- **Action**
- **Question**

Chronica側は Summary Pack で `decisions/actions/open_questions` を一次ソースとして返す。  
ホストは出力テンプレで **必ずこの3カテゴリを出す**（ゼロなら「なし」）。

---

## 8. 衛星Apps（出力テンプレ）v0.1
### 8.1 週次レビュー職人 v0.1
- 章立て固定：TL;DR / 出来事 / Decision / Action / Question / リスク / 来週優先 / メタ
- D/A/Q は必ず出す（ゼロなら「なし」）
- Actionは最大3（期限が無ければ「未定」）

### 8.2 意思決定ログメーカー v0.1
- Decision中心で「理由・却下理由・リスク」を残す
- 選択肢が不足する場合は推測しない（不明/保留を明示）
- Actions最大3 / Questionsは欠落させない

### 8.3 日次ダイジェスト v0.1（通常/プロジェクト両対応）
**通常（normal）**
- ハイライト / 気づき / memory_keep / next_talk_seed / メタ  
（親近感優先。D/A/Qを無理に出さない）

**プロジェクト（project）**
- TL;DR / 時系列 / Decision / Action / Question / リスク / メタ  
（信頼感優先。D/A/Qを必ず出す）

---

## 9. 定期B1：日次（通常）v0.1（ChatGPT側スケジュール）
- 対象：`thread_type=normal` のみ
- タイミング：毎日 23:30（JST、暫定）
- フロー：`summarize(daily,today,normal)` → ホストが本文生成 → `save_entry(kind=daily_summary)`
- 失敗時：その日はスキップ（再試行しない）

---

## 10. 内部アーキテクチャ v0.1（実装の背骨）
### 10.1 4層
1) Transport（MCP）  
2) Service（use-case：各ツール）  
3) Domain（ルール：thread/時間/抽出）  
4) Store（永続化）

### 10.2 永続化（v0.1推奨）
- SQLite 1ファイル（導入が軽く、検索/期間絞りが実用）
- 将来、必要が出たら tags 正規化や relations 追加（v0.2）

### 10.3 event_time パーサ（v0.1最小）
- 対応：今日/昨日/明日、今週/来週、今月/来月、月末、〇日（当月） など
- ルール：確信が低いなら resolved を作らず raw だけ残す

---

## 11. エラー方針 v0.1
- 例外を生で投げず、短い理由コードで返す
  - `invalid_range`, `invalid_thread`, `storage_unavailable`, `internal_error`
- 定期B1（日次）は失敗時スキップ

---

## 12. フォルダ構成（ユーザー環境の現状）
現状（確認済み）：
- `C:\Dev\Chronica\docs\`：仕様ドキュメント一式
- `C:\Dev\Chronica\src\chronica\`：実装置き場
- `C:\Dev\Chronica\data\`：DBファイル置き場
- `C:\Dev\Chronica\tests\`：テスト置き場

---

## 13. 参照（分割資料：docs内）
本書は以下を統合しています（分割資料は参照用）。

- `chronica_core_entry_store_v0.1.md`
- `chronica_mcp_tool_surface_v0.1.md`
- `chronica_mcp_internal_arch_v0.1.md`
- `chronica_summary_pack_v0.1.2.md`（※v0.1.1は置換済み）
- `chronica_satellite_weekly_review_v0.1.md`
- `chronica_satellite_decision_log_v0.1.md`
- `chronica_satellite_daily_digest_v0.1.md`
- `chronica_schedule_B1_daily_normal_v0.1.md`

---

## 14. 変更履歴（最小）
- v0.1.1：thread（通常/プロジェクト）導入、`compose_opening`導入
- v0.1.2：通常スレッドの日次価値向上のため、`digest_candidates` に `memory_keep / next_talk_seed` を追加
- v0.1（本書）：上記を統合し、Cursorが迷わない “正” を1本化



---

## Source 2 (Verbatim): Cursor_Mission_Chronica_MCP_v0.1.md

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



---

# Addendum: Decisions and Clarifications from This Thread (2026-01-06 JST)

## 1) Core Product Intent (Corrected Understanding)
- Chronica is a **behind-the-scenes tool**. On the surface, the user continues normal GPT conversations and project work.
- By introducing Chronica, the **hidden prompt** can include structured context that enables:
  - **time awareness** (time-of-day / elapsed time)
  - **timeline organization** (ordering and retrieving past conversation topics)
  - **human-like follow-up** (e.g., “the thing from 3 nights ago”)
  - **project consideration** (e.g., gently checking on tasks that have likely elapsed or been left unattended)
- Chronica’s output must be **structured** so that the front GPT can render it in the user’s own preferred tone/voice without mismatch.

## 2) Output Policy: Structured Only (No Natural-Language Voice)
- Chronica should return **structured packs** (fields/keys/IDs/intents), not user-facing prose.
- Reason: the front GPT often varies speaking style by user; Chronica emitting natural language would easily become unnatural or conflicting.

## 3) Locale / Residence Handling (Privacy-First)
- The user should not be asked to pre-configure residence/area in a way that feels like collecting personal data.
- Chronica may store residence/area **only when the user explicitly mentions it** in conversation.
- If distributed as an app, a **privacy policy must be clearly provided**, consistent with storing and using remembered information.

## 4) Language Support Stance
- Because Chronica outputs structured packs used in the hidden prompt, explicit “language support” in Chronica is not required in principle.
- However, culture/region-dependent considerations (seasonal topics, local norms) are treated as **localization concepts**, and should remain as structured “seeds”/concepts rather than fixed phrasing.

## 5) Thread Types and “Automatic Frequency” (Both Dimensions)
- There are two distinct “frequency” concepts, both separated by `thread_type`:
  1) **Scheduled daily automation**: applies to `normal` thread only (per current SoT).
  2) **In-conversation smalltalk/consideration output**: recommended as `normal=always` and `project=off` (per mission/implementation guidance).
- The user confirmed: “both” of the above separations are intended.

## 6) Communication Constraint for This Collaboration
- Avoid suggesting extra expansions framed as optional add-ons (e.g., “if needed”), because repeated acceptance of such proposals has historically caused over-complexity and collapse in prior systems.
