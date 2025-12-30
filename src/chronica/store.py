"""
Chronica Store - SQLite永続化層
"""
import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


class Store:
    """SQLiteベースの永続化層"""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # デフォルトパス: data/chronica.sqlite3
            base_dir = Path(__file__).parent.parent.parent
            db_path = base_dir / "data" / "chronica.sqlite3"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """データベースとテーブルを初期化"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # entriesテーブル作成
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                entry_id TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                saved_time TEXT NOT NULL,
                event_time_raw TEXT,
                event_time_resolved TEXT,
                event_time_confidence REAL,
                thread_type TEXT NOT NULL,
                thread_name TEXT,
                kind TEXT NOT NULL,
                title TEXT,
                text TEXT NOT NULL,
                tags TEXT,
                project TEXT,
                links_source TEXT,
                links_refs TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        # インデックス作成
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_saved_time ON entries(saved_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_thread_kind ON entries(thread_type, kind)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_thread_type ON entries(thread_type)")
        
        conn.commit()
        conn.close()
    
    def save_entry(self, entry: Dict[str, Any]) -> str:
        """エントリを保存"""
        if "entry_id" not in entry or not entry["entry_id"]:
            entry["entry_id"] = str(uuid.uuid4())
        
        if "saved_time" not in entry or not entry["saved_time"]:
            entry["saved_time"] = datetime.now(JST).isoformat()
        
        event_time = entry.get("event_time", {})
        thread = entry.get("thread", {})
        links = entry.get("links", {})
        
        tags_json = json.dumps(entry.get("tags", []), ensure_ascii=False)
        links_refs_json = json.dumps(links.get("refs", []), ensure_ascii=False)
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO entries (
                entry_id, version, saved_time,
                event_time_raw, event_time_resolved, event_time_confidence,
                thread_type, thread_name,
                kind, title, text,
                tags, project,
                links_source, links_refs,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry["entry_id"],
            entry.get("version", "0.1"),
            entry["saved_time"],
            event_time.get("raw"),
            event_time.get("resolved"),
            event_time.get("confidence"),
            thread.get("type", "normal"),
            thread.get("name"),
            entry["kind"],
            entry.get("title"),
            entry["text"],
            tags_json,
            entry.get("project"),
            links.get("source"),
            links_refs_json,
            datetime.now(JST).isoformat()
        ))
        
        conn.commit()
        conn.close()
        return entry["entry_id"]
    
    def search(
        self,
        thread_type: Optional[str] = None,
        kind: Optional[str] = None,
        tags: Optional[List[str]] = None,
        project: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """エントリを検索"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        conditions = []
        params = []
        
        if thread_type:
            conditions.append("thread_type = ?")
            params.append(thread_type)
        if kind:
            conditions.append("kind = ?")
            params.append(kind)
        if project:
            conditions.append("project = ?")
            params.append(project)
        if tags:
            for tag in tags:
                conditions.append("tags LIKE ?")
                params.append(f'%"{tag}"%')
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT * FROM entries WHERE {where_clause} ORDER BY saved_time DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_entry(row) for row in rows]
    
    def timeline(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        thread_type: Optional[str] = None,
        kind: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """タイムラインを取得"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        conditions = []
        params = []
        
        if start_time:
            conditions.append("saved_time >= ?")
            params.append(start_time)
        if end_time:
            conditions.append("saved_time <= ?")
            params.append(end_time)
        if thread_type:
            conditions.append("thread_type = ?")
            params.append(thread_type)
        if kind:
            conditions.append("kind = ?")
            params.append(kind)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT * FROM entries WHERE {where_clause} ORDER BY saved_time ASC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_entry(row) for row in rows]
    
    def get_last_seen(self, thread_type: str) -> Optional[str]:
        """最後に見た時刻を取得"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT saved_time FROM entries
            WHERE thread_type = ?
            ORDER BY saved_time DESC
            LIMIT 1
        """, (thread_type,))
        
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    
    def _row_to_entry(self, row: sqlite3.Row) -> Dict[str, Any]:
        """DB行をEntry JSONに変換"""
        entry = {
            "version": row["version"],
            "entry_id": row["entry_id"],
            "saved_time": row["saved_time"],
            "thread": {"type": row["thread_type"]},
            "kind": row["kind"],
            "text": row["text"],
            "tags": json.loads(row["tags"]) if row["tags"] else [],
        }
        
        if row["thread_name"]:
            entry["thread"]["name"] = row["thread_name"]
        if row["title"]:
            entry["title"] = row["title"]
        if row["project"]:
            entry["project"] = row["project"]
        
        if row["event_time_raw"]:
            event_time = {"raw": row["event_time_raw"]}
            if row["event_time_resolved"]:
                event_time["resolved"] = row["event_time_resolved"]
            if row["event_time_confidence"] is not None:
                event_time["confidence"] = row["event_time_confidence"]
            entry["event_time"] = event_time
        
        if row["links_source"] or row["links_refs"]:
            links = {}
            if row["links_source"]:
                links["source"] = row["links_source"]
            if row["links_refs"]:
                links["refs"] = json.loads(row["links_refs"])
            entry["links"] = links
        
        return entry
