"""
Pixel Art Renderer for Sui (翠)
"""
import streamlit as st
from typing import List, Dict
from assets.pixel_sui import get_frame, COLOR_PALETTE


def render_pixel_art(grid: List[List[int]], theme: str = "basic", size: int = 8) -> str:
    """
    ピクセルアートグリッドをHTML/CSSで描画
    
    Args:
        grid: ピクセルアートのグリッドデータ
        theme: テーマ名（"basic", "pop", "tech"）
        size: 1ピクセルのサイズ（px）
    
    Returns:
        HTML文字列
    """
    palette = COLOR_PALETTE.get(theme, COLOR_PALETTE["basic"])
    html = '<div style="display: inline-block; image-rendering: pixelated; image-rendering: crisp-edges;">'
    html += '<table style="border-collapse: collapse; margin: 0 auto;">'
    
    for row in grid:
        html += '<tr>'
        for pixel in row:
            color = palette.get(pixel, "transparent")
            html += f'<td style="width: {size}px; height: {size}px; background-color: {color};"></td>'
        html += '</tr>'
    
    html += '</table></div>'
    return html


def render_avatar(state: str = "idle", theme: str = "basic", frame: int = 0, size: int = 8) -> None:
    """
    Suiのアバターを描画
    
    Args:
        state: 状態（"idle", "thinking", "action"）
        theme: テーマ名
        frame: フレーム番号（アニメーション用）
        size: ピクセルサイズ
    """
    grid = get_frame(state, frame)
    html = render_pixel_art(grid, theme, size)
    st.markdown(html, unsafe_allow_html=True)


def render_memory_card(entry: Dict, theme: str = "basic") -> None:
    """
    メモリカードを描画
    
    Args:
        entry: エントリデータ（kind, text, tags等）
        theme: テーマ名
    """
    kind = entry.get("kind", "note")
    text = entry.get("text", "")[:100]  # 100文字まで
    tags = entry.get("tags", [])
    saved_time = entry.get("saved_time", "")
    
    # カードの色をkindに応じて変更
    kind_colors = {
        "note": "#E3F2FD",
        "event": "#FFF3E0",
        "decision": "#E8F5E9",
        "action": "#FCE4EC",
        "question": "#F3E5F5"
    }
    card_color = kind_colors.get(kind, "#F5F5F5")
    
    st.markdown(f"""
    <div class="memory-card" style="background-color: {card_color};">
        <div style="font-size: 0.8em; color: #666; margin-bottom: 5px;">
            [{kind}] {saved_time[:19] if saved_time else ""}
        </div>
        <div style="font-weight: 500; margin-bottom: 5px;">
            {text}
        </div>
        {f'<div style="font-size: 0.7em; color: #999;">{" ".join([f"#{tag}" for tag in tags[:3]])}</div>' if tags else ""}
    </div>
    """, unsafe_allow_html=True)
