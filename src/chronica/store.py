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

# グローバルStoreインスタンス（循環インポート回避のためここに配置）
_store: Optional['Store'] = None


def set_store(store: 'Store'):
    """Storeインスタンスを設定"""
    global _store
    _store = store


def get_store() -> 'Store':
    """Storeインスタンスを取得"""
    global _store
    if _store is None:
        _store = Store()
    return _store


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
                thread_id TEXT,
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
        
        # thread_idカラムが存在しない場合は追加（マイグレーション）
        cursor.execute("PRAGMA table_info(entries)")
        columns = [row[1] for row in cursor.fetchall()]
        if "thread_id" not in columns:
            cursor.execute("ALTER TABLE entries ADD COLUMN thread_id TEXT")
        
        # threadsテーブル作成（スレッド管理用）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS threads (
                thread_id TEXT PRIMARY KEY,
                thread_name TEXT NOT NULL,
                thread_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # インデックス作成
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_saved_time ON entries(saved_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_thread_kind ON entries(thread_type, kind)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_thread_type ON entries(thread_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_thread_id ON entries(thread_id)")
        
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
        
        thread_id = thread.get("id") or thread.get("thread_id")
        thread_type = thread.get("type", "normal")
        thread_name = thread.get("name")
        
        cursor.execute("""
            INSERT OR REPLACE INTO entries (
                entry_id, version, saved_time,
                event_time_raw, event_time_resolved, event_time_confidence,
                thread_id, thread_type, thread_name,
                kind, title, text,
                tags, project,
                links_source, links_refs,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry["entry_id"],
            entry.get("version", "0.1"),
            entry["saved_time"],
            event_time.get("raw"),
            event_time.get("resolved"),
            event_time.get("confidence"),
            thread_id,
            thread_type,
            thread_name,
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
        thread_id: Optional[str] = None,
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
        
        if thread_id:
            conditions.append("thread_id = ?")
            params.append(thread_id)
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
        thread_id: Optional[str] = None,
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
        if thread_id:
            conditions.append("thread_id = ?")
            params.append(thread_id)
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
    
    def get_last_interaction(self, thread_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """最後の対話エントリを取得（thread_type指定なし、thread_id指定可）"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if thread_id:
            cursor.execute("""
                SELECT * FROM entries
                WHERE thread_id = ?
                ORDER BY saved_time DESC
                LIMIT 1
            """, (thread_id,))
        else:
            cursor.execute("""
                SELECT * FROM entries
                ORDER BY saved_time DESC
                LIMIT 1
            """)
        
        row = cursor.fetchone()
        conn.close()
        return self._row_to_entry(row) if row else None
    
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
        
        # thread_idとthread_nameは存在しない場合があるため、try-exceptで処理
        try:
            if row["thread_id"]:
                entry["thread"]["id"] = row["thread_id"]
        except (KeyError, IndexError):
            pass
        try:
            if row["thread_name"]:
                entry["thread"]["name"] = row["thread_name"]
        except (KeyError, IndexError):
            pass
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
    
    def create_thread(self, thread_name: str, thread_type: str = "normal") -> str:
        """新しいスレッドを作成"""
        thread_id = str(uuid.uuid4())
        now = datetime.now(JST).isoformat()
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO threads (thread_id, thread_name, thread_type, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (thread_id, thread_name, thread_type, now, now))
        
        conn.commit()
        conn.close()
        return thread_id
    
    def list_threads(self, thread_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """スレッド一覧を取得"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if thread_type:
            cursor.execute("""
                SELECT t.*, COUNT(e.entry_id) as entry_count
                FROM threads t
                LEFT JOIN entries e ON t.thread_id = e.thread_id
                WHERE t.thread_type = ?
                GROUP BY t.thread_id
                ORDER BY t.updated_at DESC
            """, (thread_type,))
        else:
            cursor.execute("""
                SELECT t.*, COUNT(e.entry_id) as entry_count
                FROM threads t
                LEFT JOIN entries e ON t.thread_id = e.thread_id
                GROUP BY t.thread_id
                ORDER BY t.updated_at DESC
            """)
        
        rows = cursor.fetchall()
        conn.close()
        
        threads = []
        for row in rows:
            threads.append({
                "thread_id": row["thread_id"],
                "thread_name": row["thread_name"],
                "thread_type": row["thread_type"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "entry_count": row["entry_count"] or 0
            })
        
        return threads
    
    def get_thread_info(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """スレッド情報を取得"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT t.*, COUNT(e.entry_id) as entry_count
            FROM threads t
            LEFT JOIN entries e ON t.thread_id = e.thread_id
            WHERE t.thread_id = ?
            GROUP BY t.thread_id
        """, (thread_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "thread_id": row["thread_id"],
                "thread_name": row["thread_name"],
                "thread_type": row["thread_type"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "entry_count": row["entry_count"] or 0
            }
        return None
    
    def update_thread(self, thread_id: str, thread_name: Optional[str] = None) -> bool:
        """スレッド情報を更新"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if thread_name:
            updates.append("thread_name = ?")
            params.append(thread_name)
        
        if not updates:
            conn.close()
            return False
        
        updates.append("updated_at = ?")
        params.append(datetime.now(JST).isoformat())
        params.append(thread_id)
        
        cursor.execute(f"""
            UPDATE threads
            SET {", ".join(updates)}
            WHERE thread_id = ?
        """, params)
        
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()
        return updated
