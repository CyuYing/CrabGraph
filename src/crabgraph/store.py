"""Durable local jobs, replayable events and conversation presentation data."""
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from crabgraph.settings import ROOT


class Store:
    def __init__(self, path: Path = ROOT / "runtime" / "workbench.sqlite"):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,title TEXT,created REAL);
            CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,session_id TEXT,role TEXT,payload TEXT,created REAL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,kind TEXT,session_id TEXT,status TEXT,
                payload TEXT,result TEXT,created REAL,updated REAL);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,job_id TEXT,payload TEXT);
            CREATE INDEX IF NOT EXISTS events_job ON events(job_id,id);
            CREATE TABLE IF NOT EXISTS tool_preferences(tool_id TEXT PRIMARY KEY,enabled INTEGER);
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,title TEXT,created REAL,pinned INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS session_preferences(session_id TEXT PRIMARY KEY,project_id TEXT,pinned INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS workspace_preferences(key TEXT PRIMARY KEY,value TEXT);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def session(self, title="新建知识问答"):
        sid = str(uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO sessions VALUES(?,?,?)", (sid, title, time.time()))
        return sid

    def sessions(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT s.*,p.project_id,COALESCE(p.pinned,0) AS pinned FROM sessions s LEFT JOIN session_preferences p ON p.session_id=s.id ORDER BY s.created DESC")]

    def tool_preferences(self):
        with self.connect() as db:
            return {r[0]: bool(r[1]) for r in db.execute("SELECT tool_id,enabled FROM tool_preferences")}

    def set_tool(self, tool_id, enabled):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO tool_preferences VALUES(?,?)", (tool_id, int(enabled)))

    def graph_enabled(self):
        with self.connect() as db:
            row = db.execute("SELECT value FROM workspace_preferences WHERE key='knowledge_graph_enabled'").fetchone()
            return json.loads(row[0]) if row else True

    def set_graph_enabled(self, enabled):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO workspace_preferences VALUES(?,?)",
                       ("knowledge_graph_enabled", json.dumps(bool(enabled))))

    def projects(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM projects ORDER BY created DESC")]

    def project(self, title):
        pid = str(uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO projects VALUES(?,?,?,0)", (pid, title, time.time()))
        return pid

    def session_preference(self, sid, project_id=None, pinned=False):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO session_preferences VALUES(?,?,?)", (sid, project_id, int(pinned)))

    def pin_project(self, pid, pinned):
        with self.connect() as db:
            db.execute("UPDATE projects SET pinned=? WHERE id=?", (int(pinned), pid))

    def messages(self, sid):
        with self.connect() as db:
            return [dict(r) | {"payload": json.loads(r["payload"])} for r in db.execute(
                "SELECT * FROM messages WHERE session_id=? ORDER BY created", (sid,))]

    def message(self, sid, role, payload):
        with self.connect() as db:
            db.execute("INSERT INTO messages VALUES(?,?,?,?,?)",
                       (str(uuid4()), sid, role, json.dumps(payload, ensure_ascii=False), time.time()))
            if role == "user":
                db.execute("UPDATE sessions SET title=? WHERE id=? AND title='新建知识问答'",
                           (payload["text"][:28], sid))

    def job(self, kind, payload, sid=None):
        jid, now = str(uuid4()), time.time()
        with self.connect() as db:
            # Serialize turns in a thread to protect checkpoint consistency.
            db.execute("BEGIN IMMEDIATE")
            if sid and db.execute("SELECT 1 FROM jobs WHERE session_id=? AND status IN ('queued','running')",
                                  (sid,)).fetchone():
                raise ValueError("当前会话还有任务正在运行")
            db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)",
                       (jid, kind, sid, "queued", json.dumps(payload, ensure_ascii=False), None, now, now))
        return jid

    def get_job(self, jid):
        with self.connect() as db:
            r = db.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
        if not r:
            return None
        return dict(r) | {"payload": json.loads(r["payload"]), "result": json.loads(r["result"]) if r["result"] else None}

    def jobs(self):
        with self.connect() as db:
            ids = [r[0] for r in db.execute("SELECT id FROM jobs ORDER BY created DESC LIMIT 100")]
        return [self.get_job(jid) for jid in ids]

    def update(self, jid, status, result=None):
        with self.connect() as db:
            db.execute("UPDATE jobs SET status=?,result=COALESCE(?,result),updated=? WHERE id=?",
                       (status, json.dumps(result, ensure_ascii=False) if result is not None else None, time.time(), jid))

    def emit(self, jid, data):
        with self.connect() as db:
            cursor = db.execute("INSERT INTO events(job_id,payload) VALUES(?,?)",
                                (jid, json.dumps(data, ensure_ascii=False)))
            return cursor.lastrowid

    def finish(self, jid, result):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status FROM jobs WHERE id=?", (jid,)).fetchone()
            if not row or row[0] == "cancelled":
                return False
            db.execute("UPDATE jobs SET status='completed',result=?,updated=? WHERE id=?",
                       (json.dumps(result, ensure_ascii=False), time.time(), jid))
            db.execute("INSERT INTO events(job_id,payload) VALUES(?,?)",
                       (jid, json.dumps({"type": "result", **result}, ensure_ascii=False)))
            return True

    def events(self, jid, after=0):
        with self.connect() as db:
            return [{"id": r["id"], **json.loads(r["payload"])} for r in db.execute(
                "SELECT * FROM events WHERE job_id=? AND id>? ORDER BY id LIMIT 500", (jid, after))]

    def recover(self):
        with self.connect() as db:
            ids = [r[0] for r in db.execute("SELECT id FROM jobs WHERE status IN ('running','queued')")]
        for jid in ids:
            self.update(jid, "failed")
            self.emit(jid, {"type": "error", "text": "服务重启中断了执行，请重新提交。已保存的计划仍可审批。"})
