"""
Timeparse - 相対日時パーサ（v0.1最小対応）
確信が持てる範囲だけ resolved を作る（嘘を作らない）
"""
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


def parse_event_time(raw: str, anchor_time: Optional[str] = None) -> Dict[str, Any]:
    """
    相対日時をパース
    
    Args:
        raw: 生の日時文字列（例: "来週火曜", "今日", "明日"）
        anchor_time: 基準時刻（ISO文字列、JST）。無ければ現在時刻
    
    Returns:
        {
            "raw": str,
            "resolved": Optional[str],  # ISO文字列（JST）
            "confidence": float  # 0.0-1.0
        }
    """
    if not raw:
        return {"raw": raw, "confidence": 0.0}
    
    if anchor_time:
        anchor = datetime.fromisoformat(anchor_time.replace("Z", "+00:00"))
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=JST)
        else:
            anchor = anchor.astimezone(JST)
    else:
        anchor = datetime.now(JST)
    
    result = {"raw": raw, "confidence": 0.0}
    
    # 今日 / 昨日 / 明日
    if raw in ["今日", "きょう", "today"]:
        resolved = anchor.replace(hour=0, minute=0, second=0, microsecond=0)
        result["resolved"] = resolved.isoformat()
        result["confidence"] = 1.0
        return result
    
    if raw in ["昨日", "きのう", "yesterday"]:
        resolved = (anchor - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        result["resolved"] = resolved.isoformat()
        result["confidence"] = 1.0
        return result
    
    if raw in ["明日", "あした", "あす", "tomorrow"]:
        resolved = (anchor + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        result["resolved"] = resolved.isoformat()
        result["confidence"] = 1.0
        return result
    
    # 今週 / 来週（週の開始日00:00）
    if raw in ["今週", "こんしゅう", "this week"]:
        # 月曜日を週の開始とする
        days_since_monday = anchor.weekday()
        week_start = anchor - timedelta(days=days_since_monday)
        resolved = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        result["resolved"] = resolved.isoformat()
        result["confidence"] = 0.8
        return result
    
    if raw in ["来週", "らいしゅう", "next week"]:
        days_since_monday = anchor.weekday()
        week_start = anchor - timedelta(days=days_since_monday)
        next_week_start = week_start + timedelta(days=7)
        resolved = next_week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        result["resolved"] = resolved.isoformat()
        result["confidence"] = 0.8
        return result
    
    # 今月 / 来月
    if raw in ["今月", "こんげつ", "this month"]:
        resolved = anchor.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        result["resolved"] = resolved.isoformat()
        result["confidence"] = 0.8
        return result
    
    if raw in ["来月", "らいげつ", "next month"]:
        if anchor.month == 12:
            resolved = anchor.replace(year=anchor.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            resolved = anchor.replace(month=anchor.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
        result["resolved"] = resolved.isoformat()
        result["confidence"] = 0.8
        return result
    
    # 月末（当月末の00:00）
    if raw in ["月末", "げつまつ", "end of month"]:
        # 来月の1日の前日
        if anchor.month == 12:
            next_month = anchor.replace(year=anchor.year + 1, month=1, day=1)
        else:
            next_month = anchor.replace(month=anchor.month + 1, day=1)
        month_end = next_month - timedelta(days=1)
        resolved = month_end.replace(hour=0, minute=0, second=0, microsecond=0)
        result["resolved"] = resolved.isoformat()
        result["confidence"] = 0.7
        return result
    
    # 「〇日」（当月の指定日）
    day_match = re.match(r"^(\d+)日$", raw)
    if day_match:
        day = int(day_match.group(1))
        if 1 <= day <= 31:
            try:
                # 当月の指定日を試す
                resolved = anchor.replace(day=day, hour=0, minute=0, second=0, microsecond=0)
                # 過去の日付なら来月と解釈
                if resolved < anchor:
                    if anchor.month == 12:
                        resolved = anchor.replace(year=anchor.year + 1, month=1, day=day, hour=0, minute=0, second=0, microsecond=0)
                    else:
                        resolved = anchor.replace(month=anchor.month + 1, day=day, hour=0, minute=0, second=0, microsecond=0)
                result["resolved"] = resolved.isoformat()
                result["confidence"] = 0.6
                return result
            except ValueError:
                # 無効な日付（例: 2月30日）
                pass
    
    # パターンに一致しない場合は raw のみ返す（resolved を作らない）
    return result

