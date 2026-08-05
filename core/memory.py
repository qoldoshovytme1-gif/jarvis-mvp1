"""
JARVIS Memory Module
---------------------
Simple but expandable memory system using SQLite.
Stores: conversation history + long-term "facts" (preferences, notes).

Expandable later: swap SQLite -> Postgres+pgvector without touching
the rest of the app, because everything talks to Memory through this
class's public methods only.
"""

import sqlite3
import json
import os
import time
from typing import List, Dict, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "jarvis_memory.db")


class Memory:
    def __init__(self, db_path: str = DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,           -- 'user' or 'jarvis'
                content TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        # Contacts cache: lets the user say "call mom" / "text Asad" using a
        # nickname JARVIS has learned, instead of always matching against the
        # full Android contacts book. Populated either by explicit teaching
        # ("remember that mom's number is ...") or by a one-time import from
        # the Android ContactsContract (android_layer/actions.py).
        cur.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,       -- lowercased lookup key ("mom")
                display_name TEXT NOT NULL,      -- original casing ("Mom")
                phone TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        # Command history: distinct from raw conversation log — keeps only
        # executed device actions (action_type + params + outcome) so the
        # Planner/LLM context can include "what did I just do" without
        # dragging in unrelated chat turns.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS command_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                params TEXT NOT NULL,
                result TEXT NOT NULL,
                success INTEGER NOT NULL,
                timestamp REAL NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    # ---------- Conversation (episodic) memory ----------

    def add_message(self, role: str, content: str):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO conversations (role, content, timestamp) VALUES (?, ?, ?)",
            (role, content, time.time()),
        )
        conn.commit()
        conn.close()

    def get_recent_history(self, limit: int = 10) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT role, content FROM conversations ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        conn.close()
        rows.reverse()
        return [{"role": r, "content": c} for r, c in rows]

    # ---------- Long-term facts (semantic) memory ----------

    def set_fact(self, key: str, value: str):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO facts (key, value, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (key, value, time.time()),
        )
        conn.commit()
        conn.close()

    def get_fact(self, key: str) -> Optional[str]:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT value FROM facts WHERE key = ?", (key,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None

    def get_all_facts(self) -> Dict[str, str]:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM facts")
        rows = cur.fetchall()
        conn.close()
        return {k: v for k, v in rows}

    # ---------- Contacts ----------

    def set_contact(self, name: str, phone: str) -> None:
        """Teaches JARVIS a name -> phone number mapping. `name` is matched
        case-insensitively at lookup time (see `get_contact`)."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO contacts (name, display_name, phone, updated_at) VALUES (?, ?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET display_name=excluded.display_name,
                                                phone=excluded.phone,
                                                updated_at=excluded.updated_at""",
            (name.strip().lower(), name.strip(), phone.strip(), time.time()),
        )
        conn.commit()
        conn.close()

    def get_contact(self, name: str) -> Optional[Dict[str, str]]:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT display_name, phone FROM contacts WHERE name = ?",
            (name.strip().lower(),),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return {"display_name": row[0], "phone": row[1]}

    def get_all_contacts(self) -> List[Dict[str, str]]:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT display_name, phone FROM contacts ORDER BY display_name")
        rows = cur.fetchall()
        conn.close()
        return [{"display_name": r[0], "phone": r[1]} for r in rows]

    def bulk_import_contacts(self, contacts: List[Dict[str, str]]) -> int:
        """Used by android_layer.actions to cache the phone's contact book
        into JARVIS memory once, so lookups don't re-query
        ContactsContract on every single voice command. Existing entries
        (by name) are left untouched -- this never overwrites a contact the
        user explicitly taught JARVIS via `set_contact`."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        inserted = 0
        for c in contacts:
            name_key = c["display_name"].strip().lower()
            cur.execute("SELECT 1 FROM contacts WHERE name = ?", (name_key,))
            if cur.fetchone():
                continue
            cur.execute(
                "INSERT INTO contacts (name, display_name, phone, updated_at) VALUES (?, ?, ?, ?)",
                (name_key, c["display_name"].strip(), c["phone"].strip(), time.time()),
            )
            inserted += 1
        conn.commit()
        conn.close()
        return inserted

    # ---------- Command history ----------

    def add_command(self, action_type: str, params: dict, result: str, success: bool) -> None:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO command_history (action_type, params, result, success, timestamp) VALUES (?, ?, ?, ?, ?)",
            (action_type, json.dumps(params), result, 1 if success else 0, time.time()),
        )
        conn.commit()
        conn.close()

    def get_recent_commands(self, limit: int = 5) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT action_type, params, result, success FROM command_history ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        conn.close()
        rows.reverse()
        return [
            {"action_type": a, "params": json.loads(p), "result": r, "success": bool(s)}
            for a, p, r, s in rows
        ]

    def build_context_string(self, history_limit: int = 6) -> str:
        """Builds a compact context block to inject into the LLM prompt."""
        facts = self.get_all_facts()
        history = self.get_recent_history(history_limit)
        contacts = self.get_all_contacts()
        recent_commands = self.get_recent_commands(3)

        parts = []
        if facts:
            fact_lines = "\n".join(f"- {k}: {v}" for k, v in facts.items())
            parts.append(f"Known facts about the user:\n{fact_lines}")

        if contacts:
            # Keep this short -- only names, never dump raw phone numbers
            # into the LLM context unless a specific contact is asked about.
            names = ", ".join(c["display_name"] for c in contacts[:30])
            parts.append(f"Known contacts (name only): {names}")

        if recent_commands:
            cmd_lines = "\n".join(
                f"- {c['action_type']}({c['params']}) -> {'ok' if c['success'] else 'failed'}: {c['result']}"
                for c in recent_commands
            )
            parts.append(f"Recently executed device actions:\n{cmd_lines}")

        if history:
            hist_lines = "\n".join(f"{h['role']}: {h['content']}" for h in history)
            parts.append(f"Recent conversation:\n{hist_lines}")

        return "\n\n".join(parts)
