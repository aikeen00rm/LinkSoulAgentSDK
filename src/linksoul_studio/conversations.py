"""Versioned, mode-isolated text evidence. Bodies never enter diagnostic logging."""
import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone


def utc():
    return datetime.now(timezone.utc).isoformat()


class Conversations:
    def __init__(self, settings):
        self.settings = settings
        self.path = settings.data_dir / 'linksoul.sqlite3'
        self.lock = threading.RLock()
        self.db = None
        self.error = None
        self.pruned = 0

    def open(self):
        try:
            self.db = sqlite3.connect(self.path, check_same_thread=False, timeout=3)
            self.db.row_factory = sqlite3.Row
            self.db.execute('PRAGMA foreign_keys=ON')
            version = self.db.execute('PRAGMA user_version').fetchone()[0]
            if version > 1:
                raise sqlite3.DatabaseError('newer schema')
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('PRAGMA journal_size_limit=1048576')
            self.db.execute('PRAGMA max_page_count=32768')
            if version == 0:
                self.db.executescript('''
                    BEGIN IMMEDIATE;
                    CREATE TABLE sessions(id TEXT PRIMARY KEY, mode TEXT NOT NULL, agent_id TEXT,
                      run_id TEXT NOT NULL, connection_id TEXT NOT NULL, started_at TEXT NOT NULL,
                      ended_at TEXT, boundary TEXT NOT NULL);
                    CREATE TABLE turns(id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                      event_id TEXT, input TEXT NOT NULL, source TEXT NOT NULL, status TEXT NOT NULL,
                      reason TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(session_id,event_id));
                    CREATE TABLE events(id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL DEFAULT 1,
                      session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                      turn_id TEXT REFERENCES turns(id) ON DELETE CASCADE, mode TEXT NOT NULL,
                      run_id TEXT NOT NULL, connection_id TEXT NOT NULL, agent_id TEXT, event_id TEXT,
                      item_id TEXT, kind TEXT NOT NULL, source TEXT NOT NULL, direction TEXT NOT NULL,
                      timestamp TEXT NOT NULL, monotonic REAL, sequence INTEGER NOT NULL,
                      source_timestamp TEXT, body TEXT NOT NULL, dedup_key TEXT UNIQUE);
                    CREATE INDEX event_order ON events(session_id,sequence);
                    CREATE INDEX turn_identity ON turns(event_id);
                    CREATE TABLE checkpoints(session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
                      run_id TEXT NOT NULL, digest TEXT NOT NULL);
                    PRAGMA user_version=1;
                    COMMIT;
                ''')
            with self.db:
                self.db.execute("UPDATE turns SET status='incomplete',reason='Service stopped before response finished.' WHERE status='pending'")
                self.db.execute("UPDATE sessions SET ended_at=?,boundary='Service restart' WHERE ended_at IS NULL", (utc(),))
        except (sqlite3.Error, OSError):
            self.error = 'Conversation storage unavailable or schema unsupported. Check disk/permissions; restore a compatible backup before retrying.'

    def _run(self, operation):
        with self.lock:
            if self.error or self.db is None:
                return None
            try:
                with self.db:
                    return operation(self.db)
            except (sqlite3.Error, OSError):
                self.error = 'Conversation save/read failed. Evidence may be missing. Check disk space and permissions, then restart.'
                return None

    def session(self, mode, agent, run, connection, boundary='Connection opened'):
        sid = uuid.uuid4().hex
        def write(db):
            db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,NULL,?)', (sid,mode,agent,run,connection,utc(),boundary))
            old = db.execute('SELECT id FROM sessions WHERE mode=? ORDER BY rowid DESC LIMIT -1 OFFSET ?',
                             (mode,self.settings.max_sessions)).fetchall()
            for row in old:
                db.execute('DELETE FROM sessions WHERE id=?', (row[0],))
            self.pruned += len(old)
            return sid
        return self._run(write)

    def end(self, sid, reason):
        def write(db):
            db.execute('UPDATE sessions SET ended_at=?,boundary=? WHERE id=?', (utc(),reason,sid))
            db.execute("UPDATE turns SET status='incomplete',reason=? WHERE session_id=? AND status='pending'", (reason,sid))
        self._run(write)

    def turn(self, sid, event, body, source):
        tid = uuid.uuid4().hex
        def write(db):
            existing = db.execute('SELECT id,input FROM turns WHERE session_id=? AND event_id=?',(sid,event)).fetchone() if event else None
            if existing:
                return ('conflict',existing['id']) if existing['input'] != body else None
            if db.execute('SELECT count(*) FROM turns WHERE session_id=?',(sid,)).fetchone()[0] >= self.settings.max_turns:
                raise sqlite3.OperationalError('turn cap')
            clipped = len(body) > self.settings.max_text
            db.execute('INSERT INTO turns VALUES(?,?,?,?,?,?,?,?)',
                       (tid,sid,event,body[:self.settings.max_text],source,'incomplete' if clipped or not event else 'pending',
                        'Input truncated at text limit; no reply sent.' if clipped else 'Missing event identity; reply unassigned.' if not event else '',utc()))
            return tid
        result = self._run(write)
        if isinstance(result, tuple):
            self.event(sid,None,'input_conflict',body[:self.settings.max_text],event=event,source=source,direction='inbound')
            self.status(result[1],'incomplete','Conflicting input shares this event identity; extra evidence left unassigned. No second reply sent.')
            return None
        return result

    def event(self, sid, tid, kind, body='', event=None, item=None, source='Application measured',
              direction='outbound', monotonic=None, source_timestamp=None, dedup=None):
        rid = uuid.uuid4().hex
        def write(db):
            s = db.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone()
            if not s:
                raise sqlite3.OperationalError('missing session')
            if dedup and db.execute('SELECT 1 FROM events WHERE dedup_key=?',(dedup,)).fetchone():
                return None
            seq = db.execute('SELECT coalesce(max(sequence),0)+1 FROM events WHERE session_id=?',(sid,)).fetchone()[0]
            if seq > 4000 or len(body) > self.settings.max_text:
                raise sqlite3.OperationalError('capture limit')
            db.execute('''INSERT INTO events(id,session_id,turn_id,mode,run_id,connection_id,agent_id,event_id,item_id,
              kind,source,direction,timestamp,monotonic,sequence,source_timestamp,body,dedup_key)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
              (rid,sid,tid,s['mode'],s['run_id'],s['connection_id'],s['agent_id'],event,item,kind,source,direction,
               utc(),monotonic,seq,source_timestamp,body,dedup))
            return rid
        return self._run(write)

    def status(self, tid, state, reason=''):
        return self._run(lambda db: db.execute('UPDATE turns SET status=?,reason=? WHERE id=?',(state,reason,tid)).rowcount)

    def history(self, sid, entry):
        # A history event ID is a snapshot identity, never a streaming-chunk identity.
        def write(db):
            s = db.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone()
            event = entry.get('event_id')
            matches = db.execute('''SELECT t.id,t.session_id FROM turns t JOIN sessions s ON s.id=t.session_id
              WHERE s.mode=? AND s.agent_id IS ? AND t.event_id=?''',(s['mode'],s['agent_id'],event)).fetchall() if event else []
            # Reconnect history remains local evidence. Do not attach it to a prior
            # session whose retention/deletion could remove the history record.
            return dict(s), matches[0][0] if len(matches)==1 and matches[0]['session_id']==sid else None
        result = self._run(write)
        if result is None:
            return
        s, tid = result
        body = json.dumps(entry,ensure_ascii=True)
        if len(body) > self.settings.max_text:
            body = json.dumps({'event_id':entry.get('event_id'),'note':'History exceeds text limit; content unavailable.'})
            tid = None
        key = hashlib.sha256(json.dumps([s['mode'],s['agent_id'],entry],sort_keys=True).encode()).hexdigest()
        return self.event(sid,tid,'history',body,event=entry.get('event_id'),source='SDK captured' if s['mode']=='robot' else 'Fixture simulation',
                          direction='inbound',source_timestamp=str(entry.get('timestamp')) if entry.get('timestamp') is not None else None,dedup=key if entry.get('event_id') else None)

    def sessions(self, mode):
        return self._run(lambda db: [dict(r) for r in db.execute('''SELECT s.*,count(t.id) AS turns FROM sessions s
          LEFT JOIN turns t ON t.session_id=s.id WHERE s.mode=? GROUP BY s.id ORDER BY s.rowid DESC''',(mode,))]) or []

    def detail(self, mode, sid):
        def read(db):
            row = db.execute('SELECT * FROM sessions WHERE id=? AND mode=?',(sid,mode)).fetchone()
            if not row:
                return None
            result = dict(row)
            events = [dict(r) for r in db.execute('SELECT * FROM events WHERE session_id=? ORDER BY sequence',(sid,))]
            turns = [dict(r) for r in db.execute('SELECT * FROM turns WHERE session_id=? ORDER BY rowid',(sid,))]
            for turn in turns:
                turn['evidence'] = [e for e in events if e['turn_id']==turn['id']]
                turn['reply'] = ''.join(e['body'] for e in turn['evidence'] if e['kind']=='reply_chunk')
                turn['acceptance'] = 'Unavailable — SDK exposes no acknowledgement for these calls'
                turn['execution'] = 'Unknown — no physical playback evidence'
            result.update(turns=turns,unassigned=[e for e in events if e['turn_id'] is None], events=events)
            return result
        return self._run(read)

    @staticmethod
    def digest(detail):
        # Excludes lifecycle fields changed by restart; includes every captured event and body.
        return hashlib.sha256(json.dumps({'events':detail['events'], 'turns':[
            {k:t[k] for k in ('id','event_id','input','reply','source')} for t in detail['turns']]},sort_keys=True).encode()).hexdigest()

    def checkpoint(self, mode, sid, run):
        detail = self.detail(mode,sid)
        if not detail:
            return False
        digest = self.digest(detail)
        return self._run(lambda db: db.execute('INSERT OR REPLACE INTO checkpoints VALUES(?,?,?)',(sid,run,digest)).rowcount)==1

    def reopened(self, mode, sid, run):
        detail = self.detail(mode,sid)
        row = self._run(lambda db: db.execute('SELECT * FROM checkpoints WHERE session_id=?',(sid,)).fetchone())
        return bool(detail and row and row['run_id'] != run and row['digest']==self.digest(detail))

    def close(self):
        with self.lock:
            if self.db:
                self.db.close()
                self.db = None
