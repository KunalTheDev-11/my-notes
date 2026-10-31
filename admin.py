#!/usr/bin/env python3
"""Manage secret notes. No dependencies beyond Python 3.8+.

Setup: create admin.env next to this file (never commit it!):
    SUPABASE_URL=https://xxxx.supabase.co
    SUPABASE_SERVICE_KEY=your-service_role-key

Usage:
    python admin.py add              # prompts for code, title, note
    python admin.py add --random     # generates a strong code for you
    python admin.py list
    python admin.py delete CODE
"""
import argparse, hashlib, json, os, secrets, sys, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

env_file = Path(__file__).with_name("admin.env")
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"\''))

URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
if not URL or not KEY:
    sys.exit("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY (see admin.env instructions at top of file).")

def code_hash(code): return hashlib.sha256(code.strip().lower().encode()).hexdigest()

def api(method, path, body=None, prefer=None):
    headers = {"apikey": KEY, "Content-Type": "application/json"}
    if not KEY.startswith("sb_"): headers["Authorization"] = f"Bearer {KEY}"  # old-style JWT keys only
    if prefer: headers["Prefer"] = prefer
    req = urllib.request.Request(f"{URL}/rest/v1/{path}", method=method, headers=headers,
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        msg = e.read().decode()
        if e.code == 409: sys.exit("That code is already in use. Pick another.")
        sys.exit(f"Error {e.code}: {msg}")
    except urllib.error.URLError as e:
        sys.exit(f"Network problem: {e.reason}")

def read_body():
    print("Write your note. Finish with a line containing only END:")
    lines = []
    while True:
        try: line = input()
        except EOFError: break
        if line.strip() == "END": break
        lines.append(line)
    return "\n".join(lines).strip()

def cmd_add(a):
    if a.random:
        code = "-".join(secrets.token_hex(2) for _ in range(3))
        print(f"Generated code: {code}")
    else:
        code = input("Secret code: ").strip()
    if len(code) < 4: sys.exit("Use a code of at least 4 characters (8+ is much safer).")
    title = input("Title (optional): ").strip() or None
    body = read_body()
    if not body: sys.exit("The note is empty.")
    days = input("Expires in how many days? (blank = never): ").strip()
    exp = (datetime.now(timezone.utc) + timedelta(days=int(days))).isoformat() if days.isdigit() else None
    api("POST", "notes", {"code_hash": code_hash(code), "title": title, "body": body, "expires_at": exp},
        prefer="return=minimal")
    print(f"\n✓ Saved. Share this code: {code}")

def cmd_list(_):
    rows = api("GET", "notes?select=title,created_at,views,expires_at&order=created_at.desc")
    if not rows: return print("No notes yet.")
    for r in rows:
        print(f"{r['created_at'][:10]}  views={r['views']:<4} expires={(r['expires_at'] or 'never')[:10]:<10}  {r['title'] or '(untitled)'}")

def cmd_delete(a):
    api("DELETE", f"notes?code_hash=eq.{code_hash(a.code)}")
    print("✓ Deleted (if that code existed).")

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
s = p.add_subparsers(dest="cmd", required=True)
x = s.add_parser("add"); x.add_argument("--random", action="store_true"); x.set_defaults(f=cmd_add)
s.add_parser("list").set_defaults(f=cmd_list)
x = s.add_parser("delete"); x.add_argument("code"); x.set_defaults(f=cmd_delete)
a = p.parse_args(); a.f(a)