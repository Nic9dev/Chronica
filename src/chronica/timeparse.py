"""
Timeparse - 相対日時パーサ（v0.1最小対応）
"""
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


def parse_event_time(raw: str, anchor_time: Optional[str] = None) -> Dict[str, Any]:
    """相対日時をパース"""
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
    
    # 今週 / 来週
    if raw in ["今週", "こんしゅう", "this week"]:
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
    
    # 月末
    if raw in ["月末", "げつまつ", "end of month"]:
        if anchor.month == 12:
            next_month = anchor.replace(year=anchor.year + 1, month=1, day=1)
        else:
            next_month = anchor.replace(month=anchor.month + 1, day=1)
        month_end = next_month - timedelta(days=1)
        resolved = month_end.replace(hour=0, minute=0, second=0, microsecond=0)
        result["resolved"] = resolved.isoformat()
        result["confidence"] = 0.7
        return result
    
    # 「〇日」
    day_match = re.match(r"^(\d+)日$", raw)
    if day_match:
        day = int(day_match.group(1))
        if 1 <= day <= 31:
            try:
                resolved = anchor.replace(day=day, hour=0, minute=0, second=0, microsecond=0)
                if resolved < anchor:
                    if anchor.month == 12:
                        resolved = anchor.replace(year=anchor.year + 1, month=1, day=day, hour=0, minute=0, second=0, microsecond=0)
                    else:
                        resolved = anchor.replace(month=anchor.month + 1, day=day, hour=0, minute=0, second=0, microsecond=0)
                result["resolved"] = resolved.isoformat()
                result["confidence"] = 0.6
                return result
            except ValueError:
                pass
    
    return result
