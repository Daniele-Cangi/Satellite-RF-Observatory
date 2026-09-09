"""Durable single-host pilot queue, independent of HTTP and hosting adapters.

Only a trusted server supplies owner identity and only a trusted worker receives
claim tokens. Expired claims are quarantined, never automatically retried.
This store records operational state; the scientific runner validates evidence.
"""
from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import secrets
import sqlite3
import time
import uuid

from positioning.plans import validate_plan


class Conflict(ValueError):
    """Request conflicts with its immutable declaration or current state."""


class QueueFull(ValueError):
    """The bounded pilot cannot accept another active request."""


class RequestStore:
    def __init__(self, path, *, capacity=20, per_owner=2, clock=time.time):
        if capacity < 1 or per_owner < 1:
            raise ValueError('positive queue limits required')
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.capacity, self.per_owner, self.clock = capacity, per_owner, clock
        with self._transaction() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS requests (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, idempotency_key TEXT NOT NULL,
                    declaration TEXT NOT NULL, declaration_hash TEXT NOT NULL,
                    state TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL,
                    lease_hash TEXT, lease_until REAL, result_hash TEXT,
                    UNIQUE(owner, idempotency_key)
                );
                CREATE INDEX IF NOT EXISTS requests_queue ON requests(state, created_at);
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL REFERENCES requests(id),
                    state TEXT NOT NULL, recorded_at REAL NOT NULL
                );
            ''')

    @contextmanager
    def _transaction(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('BEGIN IMMEDIATE')
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _identity(value):
        if not isinstance(value, str) or not 1 <= len(value) <= 128 or any(ord(c) < 32 for c in value):
            raise ValueError('identity/key must be a nonempty bounded string')

    @staticmethod
    def _hash(value):
        return hashlib.sha256(value.encode('utf-8')).hexdigest()

    @staticmethod
    def _view(row):
        return {key: row[key] for key in ('id', 'state', 'created_at', 'updated_at', 'declaration_hash', 'result_hash')}

    def _record(self, db, request_id, state):
        db.execute('INSERT INTO events(request_id,state,recorded_at) VALUES(?,?,?)',
                   (request_id, state, self.clock()))

    def submit(self, owner, key, plan, *, implementation, purpose):
        self._identity(owner); self._identity(key)
        if not re.fullmatch(r'[0-9a-f]{40}', implementation):
            raise ValueError('pin the full implementation commit')
        if purpose not in ('availability', 'historical_replay', 'prospective_attempt'):
            raise ValueError('explicit request purpose required')
        validate_plan(plan)
        if date.fromisoformat(plan['date_gpst']) >= datetime.now(timezone.utc).date():
            raise ValueError('choose a completed historical day')
        declaration = json.dumps({'schema': 'satellite-rf-request-v1', 'plan': plan,
                                  'implementation': implementation, 'purpose': purpose},
                                 sort_keys=True, separators=(',', ':'), allow_nan=False)
        digest = self._hash(declaration)
        with self._transaction() as db:
            existing = db.execute('SELECT * FROM requests WHERE owner=? AND idempotency_key=?', (owner, key)).fetchone()
            if existing:
                if existing['declaration_hash'] != digest:
                    raise Conflict('idempotency key already binds a different declaration')
                return self._view(existing)
            active = "state IN ('QUEUED','RUNNING','NEEDS_REVIEW')"
            if db.execute('SELECT count(*) FROM requests WHERE '+active).fetchone()[0] >= self.capacity:
                raise QueueFull('pilot queue limit reached')
            if db.execute('SELECT count(*) FROM requests WHERE owner=? AND '+active, (owner,)).fetchone()[0] >= self.per_owner:
                raise QueueFull('owner active-request limit reached')
            request_id, now = str(uuid.uuid4()), self.clock()
            db.execute('INSERT INTO requests(id,owner,idempotency_key,declaration,declaration_hash,state,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',
                       (request_id, owner, key, declaration, digest, 'QUEUED', now, now))
            self._record(db, request_id, 'QUEUED')
            return self._view(db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone())

    def get(self, owner, request_id):
        self._identity(owner)
        with self._transaction() as db:
            row = db.execute('SELECT * FROM requests WHERE id=? AND owner=?', (request_id, owner)).fetchone()
            if row is None:
                raise KeyError('request not found')
            result = self._view(row)
            result['declaration'] = json.loads(row['declaration'])
            result['events'] = [dict(event) for event in db.execute(
                'SELECT sequence,state,recorded_at FROM events WHERE request_id=? ORDER BY sequence', (request_id,))]
            return result

    def cancel(self, owner, request_id):
        with self._transaction() as db:
            row = db.execute('SELECT * FROM requests WHERE id=? AND owner=?', (request_id, owner)).fetchone()
            if row is None:
                raise KeyError('request not found')
            if row['state'] == 'CANCELLED':
                return
            if row['state'] != 'QUEUED':
                raise Conflict('only queued work can be cancelled; running work needs controlled shutdown')
            db.execute("UPDATE requests SET state='CANCELLED',updated_at=? WHERE id=?", (self.clock(), request_id))
            self._record(db, request_id, 'CANCELLED')

    @staticmethod
    def _lease_seconds(seconds):
        if not isinstance(seconds, int) or not 1 <= seconds <= 600:
            raise ValueError('lease must be 1..600 seconds')

    def claim(self, *, lease_seconds=60):
        self._lease_seconds(lease_seconds)
        with self._transaction() as db:
            now = self.clock()
            expired = db.execute("SELECT id FROM requests WHERE state='RUNNING' AND lease_until<=?", (now,)).fetchall()
            for row in expired:
                db.execute("UPDATE requests SET state='NEEDS_REVIEW',updated_at=?,lease_hash=NULL,lease_until=NULL WHERE id=?", (now, row['id']))
                self._record(db, row['id'], 'NEEDS_REVIEW')
            # An expired worker may still be alive. Stop dispatch until an
            # operator has inspected and stopped it; no concurrent replacement.
            if db.execute("SELECT 1 FROM requests WHERE state IN ('RUNNING','NEEDS_REVIEW') LIMIT 1").fetchone():
                return None
            row = db.execute("SELECT * FROM requests WHERE state='QUEUED' ORDER BY created_at,id LIMIT 1").fetchone()
            if row is None:
                return None
            token = secrets.token_urlsafe(32)
            db.execute("UPDATE requests SET state='RUNNING',updated_at=?,lease_hash=?,lease_until=? WHERE id=?",
                       (now, self._hash(token), now+lease_seconds, row['id']))
            self._record(db, row['id'], 'RUNNING')
            return {'id': row['id'], 'declaration': json.loads(row['declaration']),
                    'declaration_hash': row['declaration_hash'], 'lease_token': token}

    def _owned_claim(self, db, request_id, token):
        row = db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone()
        if (row is None or row['state'] != 'RUNNING' or row['lease_until'] <= self.clock()
                or not secrets.compare_digest(row['lease_hash'], self._hash(token))):
            raise Conflict('claim missing, expired or superseded; no automatic replay')
        return row

    def heartbeat(self, request_id, token, *, lease_seconds=60):
        self._lease_seconds(lease_seconds)
        with self._transaction() as db:
            self._owned_claim(db, request_id, token)
            db.execute('UPDATE requests SET lease_until=?,updated_at=? WHERE id=?',
                       (self.clock()+lease_seconds, self.clock(), request_id))

    def finish(self, request_id, token, *, state, result_hash):
        if state not in ('COMPLETED', 'FAILED') or not re.fullmatch(r'[0-9a-f]{64}', result_hash):
            raise ValueError('terminal state and sealed result digest required')
        with self._transaction() as db:
            self._owned_claim(db, request_id, token)
            db.execute('UPDATE requests SET state=?,result_hash=?,updated_at=?,lease_hash=NULL,lease_until=NULL WHERE id=?',
                       (state, result_hash, self.clock(), request_id))
            self._record(db, request_id, state)
