"""
Chronica - 記憶のキュレーション UI

役割:
- 記憶の一覧表示・選別
- 冗長・重複記憶の確認
- 不要な記憶の削除（削除のみ、編集不可）
- トークン使用量の可視化

※ チャットは Claude Desktop で完結
"""
import json
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
ROOT = Path(__file__).resolve().parent
CURATION_SETTINGS_PATH = ROOT / "data" / "curation_ui_settings.json"

# トークン上限のデフォルト・UI最大値（モデルコンテキストに合わせて調整可）
DEFAULT_TOKEN_BUDGET = 500_000
MAX_TOKEN_BUDGET_UI = 5_000_000
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import html
import streamlit as st
import tiktoken
from datetime import datetime
from zoneinfo import ZoneInfo

from src.chronica.store import Store

JST = ZoneInfo("Asia/Tokyo")

# kind ごとの絵文字
KIND_EMOJI = {
    "note": "🗒️",
    "event": "📅",
    "decision": "✅",
    "action": "🎯",
    "question": "❓",
}

# トークンカウント（cl100k_base = GPT-4 系）
def count_tokens(text: str, model: str = "gpt-4") -> int:
    """テキストのトークン数をカウント"""
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def init_store() -> Store:
    """Store を初期化"""
    return Store()


def load_token_budget() -> int:
    """保存済みトークン上限を読み込む（失敗時はデフォルト）"""
    if not CURATION_SETTINGS_PATH.exists():
        return DEFAULT_TOKEN_BUDGET
    try:
        with open(CURATION_SETTINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        n = int(data.get("token_budget", DEFAULT_TOKEN_BUDGET))
        return max(1000, min(n, MAX_TOKEN_BUDGET_UI))
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return DEFAULT_TOKEN_BUDGET


def save_token_budget(n: int) -> None:
    """トークン上限を JSON に保存（ページ更新後も維持）"""
    CURATION_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CURATION_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump({"token_budget": int(n)}, f, indent=2, ensure_ascii=False)


def main():
    st.set_page_config(
        page_title="Chronica - 記憶のキュレーション",
        page_icon="📚",
        layout="wide"
    )

    st.title("📚 Chronica - 記憶のキュレーション")
    st.caption("記憶の選別・冗長確認・削除（編集不可）")

    store = init_store()

    # 全エントリ取得（フィルタ前）
    all_entries = store.search(limit=10000)

    # タグ一覧（Store + エントリからフォールバック）
    all_tags = store.get_all_tags()
    if not all_tags:
        all_tags = sorted(set(t for e in all_entries for t in (e.get("tags") or [])))

    # サイドバー（トークン上限設定・ファイル永続化）
    if "curation_token_budget" not in st.session_state:
        st.session_state.curation_token_budget = load_token_budget()

    def _persist_token_budget() -> None:
        save_token_budget(st.session_state.curation_token_budget)

    with st.sidebar:
        st.header("⚙️ 設定")
        st.number_input(
            "トークン上限",
            min_value=1000,
            max_value=MAX_TOKEN_BUDGET_UI,
            step=1000,
            key="curation_token_budget",
            on_change=_persist_token_budget,
            help=(
                "使用率の基準。変更は data/curation_ui_settings.json に保存され、"
                "ページを更新しても維持されます。"
            ),
        )
        max_tokens = st.session_state.curation_token_budget
        st.divider()

    # フィルタUI
    st.header("フィルタ")
    col1, col2, col3 = st.columns(3)

    with col1:
        kind_options = ["すべて", "note", "decision", "action", "question", "event"]
        kind_filter = st.selectbox("種別", kind_options, index=0)

    with col2:
        tag_filter = st.multiselect(
            "タグ（いずれか一致）",
            all_tags,
            default=[],
            placeholder="タグを選択..." if all_tags else "（タグがありません）"
        )

    with col3:
        sort_options = ["最新順", "古い順"]
        sort_order = st.selectbox("並び順", sort_options, index=0)

    # フィルタ適用
    filtered = all_entries
    if kind_filter != "すべて":
        filtered = [e for e in filtered if e.get("kind") == kind_filter]
    if tag_filter:
        filtered = [e for e in filtered if any(t in (e.get("tags") or []) for t in tag_filter)]
    if sort_order == "古い順":
        filtered = sorted(filtered, key=lambda e: e.get("saved_time", ""))
    else:
        filtered = sorted(filtered, key=lambda e: e.get("saved_time", ""), reverse=True)

    # トークン使用状況
    st.header("トークン使用状況")
    total_tokens = sum(count_tokens(e.get("text", "")) for e in all_entries)
    progress = min(total_tokens / max_tokens, 1.0)

    col_metric, col_bar = st.columns([1, 3])
    with col_metric:
        st.metric("現在の記憶総トークン数", f"{total_tokens:,} tokens")
    with col_bar:
        st.progress(progress, text=f"{progress*100:.0f}% (上限 {max_tokens:,} tokens)")

    # トークン数の多い記憶 TOP 10
    entries_with_tokens = [(e, count_tokens(e.get("text", ""))) for e in all_entries]
    entries_with_tokens.sort(key=lambda x: x[1], reverse=True)
    top_10 = entries_with_tokens[:10]

    with st.expander("トークン数の多い記憶 TOP 10"):
        if not top_10:
            st.caption("（該当する記憶がありません）")
        else:
            for i, (entry, tokens) in enumerate(top_10, 1):
                text = entry.get("text", "")
                preview = (text[:50] + "..." if len(text) > 50 else text) or "（タイトルなし）"
                saved = (entry.get("saved_time", "")[:19].replace("T", " ") if entry.get("saved_time") else "?")
                eid = entry.get("entry_id", "")[:8]
                st.write(f"{i}. {preview} ({tokens:,} tokens)")
                st.caption(f"ID: {eid}... | {saved}")

    st.divider()

    # 記憶の一覧（表示件数・ページネーション）
    st.header("記憶の一覧")

    if "pending_delete" not in st.session_state:
        st.session_state.pending_delete = None
    if "selected_ids" not in st.session_state:
        st.session_state.selected_ids = set()
    if "batch_confirm" not in st.session_state:
        st.session_state.batch_confirm = False

    items_options = [10, 25, 50, 100]
    items_plus_all = items_options + ["すべて"]
    items_per_page = st.session_state.get("curation_ipp", items_options[0])
    if items_per_page not in items_plus_all:
        items_per_page = items_options[0]
    items_per_page_val = items_per_page if items_per_page != "すべて" else len(filtered) or 1
    total_pages = max(1, (len(filtered) + items_per_page_val - 1) // items_per_page_val)
    if "curation_pg" not in st.session_state:
        st.session_state.curation_pg = 1
    st.session_state.curation_pg = min(max(1, int(st.session_state.curation_pg)), total_pages)
    page = st.session_state.curation_pg
    start = (page - 1) * items_per_page_val
    display_entries = filtered[start : start + items_per_page_val]

    # 全選択 / 全解除ボタン
    col_sel_all, col_sel_none, col_batch_del = st.columns([1, 1, 3])
    display_ids = [e.get("entry_id", "") for e in display_entries]

    with col_sel_all:
        if st.button("☑️ 全選択"):
            st.session_state.selected_ids.update(display_ids)
            for eid in display_ids:
                if eid:
                    st.session_state[f"chk_{eid}"] = True
            st.rerun()
    with col_sel_none:
        if st.button("⬜ 全解除"):
            st.session_state.selected_ids.difference_update(display_ids)
            for eid in display_ids:
                if eid:
                    st.session_state[f"chk_{eid}"] = False
            st.rerun()
    with col_batch_del:
        n_selected = len(st.session_state.selected_ids)
        if n_selected > 0:
            if st.button(f"🗑️ 選択した {n_selected} 件を削除", type="primary"):
                st.session_state.batch_confirm = True
                st.rerun()
        else:
            st.button("🗑️ 削除（記憶を選択してください）", disabled=True)

    if st.session_state.batch_confirm:
        n = len(st.session_state.selected_ids)
        st.warning(f"⚠️ {n} 件の記憶を削除しますか？この操作は取り消せません。")
        bc1, bc2 = st.columns(2)
        with bc1:
            if st.button("✓ まとめて削除する", type="primary", key="batch_confirm_btn"):
                ids_removed = list(st.session_state.selected_ids)
                deleted = store.delete_entries(ids_removed)
                st.session_state.selected_ids.clear()
                for eid in ids_removed:
                    if eid:
                        st.session_state.pop(f"chk_{eid}", None)
                st.session_state.batch_confirm = False
                st.success(f"{deleted} 件削除しました")
                st.rerun()
        with bc2:
            if st.button("✕ キャンセル", key="batch_cancel_btn"):
                st.session_state.batch_confirm = False
                st.rerun()

    col_items, col_page = st.columns([1, 2])
    with col_items:
        st.selectbox(
            "表示件数",
            items_plus_all,
            index=0,
            key="curation_ipp",
            format_func=lambda x: str(x) if x != "すべて" else "すべて"
        )
    with col_page:
        st.number_input("ページ", min_value=1, max_value=total_pages, step=1, key="curation_pg")

    st.caption(f"表示: {len(display_entries)} 件 / 全 {len(filtered)} 件")

    for entry in display_entries:
        entry_id = entry.get("entry_id", "")
        saved_time = entry.get("saved_time", "?")[:19].replace("T", " ")
        kind = entry.get("kind", "?")
        tags = entry.get("tags") or []
        tags_str = " ".join(f"#{t}" for t in tags) if tags else "-"
        text_preview = (entry.get("text") or "")[:80] + ("..." if len(entry.get("text", "")) > 80 else "")
        tokens = count_tokens(entry.get("text", ""))
        emoji = KIND_EMOJI.get(kind, "📌")
        tags_safe = html.escape(tags_str)
        text_safe = html.escape(text_preview)

        with st.container():
            # チェックボックス（バッチ削除用）
            # key 付きウィジェットの状態が表示を支配するため、全選択/全解除では chk_* も同期すること
            chk_key = f"chk_{entry_id}"
            if chk_key not in st.session_state:
                st.session_state[chk_key] = entry_id in st.session_state.selected_ids
            checked = st.checkbox(
                f"選択（ID: {entry_id[:8]}...）",
                key=chk_key,
                label_visibility="collapsed"
            )
            if checked:
                st.session_state.selected_ids.add(entry_id)
            elif entry_id in st.session_state.selected_ids:
                st.session_state.selected_ids.discard(entry_id)

            # カード風スタイル
            st.markdown(f"""
<div style="
    border: 1px solid #333;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 8px;
    background-color: #1a1a1a;
">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <span style="font-size: 1.1em;">{emoji} {kind}</span>
            <span style="color: #888; margin-left: 10px;">{saved_time}</span>
        </div>
    </div>
    <div style="margin: 8px 0; color: #aaa;">{tags_safe}</div>
    <div style="margin: 8px 0;">{text_safe}</div>
    <div style="color: #888; font-size: 0.9em;">💬 {tokens:,} tokens | 🆔 {entry_id[:8]}...</div>
</div>
""", unsafe_allow_html=True)

            if st.session_state.pending_delete == entry_id:
                st.warning("⚠️ 本当にこの記憶を削除しますか？この操作は取り消せません。")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✓ 削除する", key=f"confirm_{entry_id}", type="primary"):
                        if store.delete_entry(entry_id):
                            st.session_state.pending_delete = None
                            st.success("削除しました")
                            st.rerun()
                        else:
                            st.error("削除に失敗しました")
                with c2:
                    if st.button("✕ キャンセル", key=f"cancel_{entry_id}"):
                        st.session_state.pending_delete = None
                        st.rerun()
            else:
                if st.button("🗑️ 削除", key=f"del_{entry_id}"):
                    st.session_state.pending_delete = entry_id
                    st.rerun()

        st.divider()

    if not filtered:
        st.info("該当する記憶がありません。")


if __name__ == "__main__":
    main()
