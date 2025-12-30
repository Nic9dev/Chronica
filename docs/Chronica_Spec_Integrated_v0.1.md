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

