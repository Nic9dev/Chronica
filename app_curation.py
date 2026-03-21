"""
Chronica - 記憶のキュレーション UI

役割:
- 記憶の一覧表示・選別
- 冗長・重複記憶の確認
- 不要な記憶の削除（削除のみ、編集不可）
- トークン使用量の可視化

※ チャットは Claude Desktop で完結
"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
ROOT = Path(__file__).resolve().parent
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

    # サイドバー（トークン上限設定）
    with st.sidebar:
        st.header("⚙️ 設定")
        max_tokens = st.number_input(
            "トークン上限",
            min_value=1000,
            max_value=100000,
            value=20000,
            step=1000,
            help="使用率の基準となる上限値"
        )
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
    col_items, col_page = st.columns([1, 2])
    with col_items:
        items_options = [10, 25, 50, 100]
        items_per_page = st.selectbox(
            "表示件数",
            items_options + ["すべて"],
            index=0,
            format_func=lambda x: str(x) if x != "すべて" else "すべて"
        )
    items_per_page_val = items_per_page if items_per_page != "すべて" else len(filtered) or 1
    total_pages = max(1, (len(filtered) + items_per_page_val - 1) // items_per_page_val)
    with col_page:
        page = st.number_input("ページ", min_value=1, max_value=total_pages, value=1, step=1)
    start = (page - 1) * items_per_page_val
    display_entries = filtered[start : start + items_per_page_val]
    st.caption(f"表示: {len(display_entries)} 件 / 全 {len(filtered)} 件")

    # 削除対象（確認用）
    if "pending_delete" not in st.session_state:
        st.session_state.pending_delete = None

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
