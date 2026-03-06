# Replit Deployment Guide for CHIT-CHAT

## Overview
- Local machine → MySQL (`app.py` unchanged)
- Replit → PostgreSQL (follow steps below)

---

## Step 1: Set Up the Database on Replit

1. In your Replit project, go to **Tools → PostgreSQL** (or create a Neon DB from the Replit sidebar).
2. Replit will give you a `DATABASE_URL` environment variable automatically.
3. Open the **PostgreSQL shell** (or use the SQL editor) and paste the entire contents of `database.postgres.sql` to create all tables.

---

## Step 2: Set Environment Variables in Replit Secrets

Go to **Tools → Secrets** and add:

```
DATABASE_URL        = (auto-set by Replit PostgreSQL)
MAIL_USERNAME       = no.auth.verify@gmail.com
MAIL_PASSWORD       = ayil vzbh gdek cxyv
SECRET_KEY          = 6X)jkvpyyM0(jKvgR^}=]{q=VN#34k0;
OPENROUTER_API_KEY  = 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
SURF_API_KEY        = JNi_uD1pzcArRY_qFxmG90P01VQR5odrorjzRD31HLE
CORS_ORIGINS        = *
```

Do NOT add DB_HOST / DB_USER / DB_PASSWORD / DB_NAME — those are MySQL only.

---

## Step 3: Install psycopg2

Add to `requirements.txt`:
```
psycopg2-binary
```
Remove (or keep — it won't be used):
```
mysql-connector-python
```

---

## Step 4: Code Changes in app.py

Make ONLY these changes. Everything else (queries, routes, socket handlers) stays the same.

### 4a. Replace the import at the top

**Find:**
```python
import mysql.connector
```
**Replace with:**
```python
import psycopg2
import psycopg2.extras
```

### 4b. Replace get_db()

**Find:**
```python
def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        autocommit=True
    )
```
**Replace with:**
```python
def get_db():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    conn.autocommit = True
    return conn
```

### 4c. Replace all `cursor(dictionary=True)` calls

Every time the code does:
```python
cursor = db.cursor(dictionary=True)
```
Change it to:
```python
cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
```

Every time the code does just:
```python
cursor = db.cursor()
```
Leave it as-is (plain cursor is fine for INSERT/UPDATE/DELETE).

### 4d. Fix lastrowid → RETURNING id

MySQL uses `cursor.lastrowid` after an INSERT.
PostgreSQL needs `RETURNING id` in the query and `cursor.fetchone()[0]`.

Search the file for every occurrence of `cursor.lastrowid` and change like this:

**MySQL pattern:**
```python
cursor.execute("INSERT INTO messages (...) VALUES (...)", (...))
msg_id = cursor.lastrowid
```
**PostgreSQL pattern:**
```python
cursor.execute("INSERT INTO messages (...) VALUES (...) RETURNING id", (...))
msg_id = cursor.fetchone()[0]
```

The same applies to all other tables (users, reels, statuses, posts, songs, etc.)

### 4e. Fix IF() → CASE WHEN in SQL queries

MySQL `IF(condition, a, b)` is not valid in PostgreSQL.

**Find (in recent_chats and any other query):**
```sql
IF(m.sender_id=%s, m.receiver_id, m.sender_id)
```
**Replace with:**
```sql
CASE WHEN m.sender_id=%s THEN m.receiver_id ELSE m.sender_id END
```

### 4f. Fix init_db() for PostgreSQL

The `init_db()` function uses MySQL-specific `INFORMATION_SCHEMA` queries with `TABLE_SCHEMA=%s`.
In PostgreSQL replace them with:
```python
# Check if column exists (PostgreSQL)
cursor.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name='messages' AND column_name='deleted_for_everyone'
""")
```
(Remove the `TABLE_SCHEMA=%s` parameter — PostgreSQL uses the connected database automatically.)

Also replace all MySQL DDL in init_db:
- `INT AUTO_INCREMENT PRIMARY KEY` → `SERIAL PRIMARY KEY`
- `TINYINT DEFAULT 0` → `SMALLINT DEFAULT 0`
- `UNIQUE KEY name (cols)` → `UNIQUE (cols)` or add separately
- `INDEX idx_name (col)` → `CREATE INDEX IF NOT EXISTS idx_name ON table(col)`
- Remove `ENGINE=InnoDB` and `DEFAULT CHARSET=...` lines

**Tip:** The easiest approach is to DELETE the entire body of `init_db()` on Replit and replace with:
```python
def init_db():
    pass  # Tables already created via database.postgres.sql
```
Since you already ran `database.postgres.sql` in Step 1, all tables exist.

---

## Step 5: File Uploads (Videos, Images, Profile Pics, etc.)

Replit's filesystem is **persistent** — files in `static/uploads/` survive restarts and redeploys as long as you don't delete the Repl.

**No changes needed** for file storage if you are on a paid Replit plan or a Repl that is not reset.

If you want extra safety (e.g. free tier Repl that might reset), you can use **Cloudinary** or **Backblaze B2** for file storage — but that requires rewriting the upload routes.

For now: files in `static/uploads/` will persist normally on Replit.

---

## Step 6: Add .replit config

Create a file called `.replit` in the project root:
```
run = "python app.py"
```

And `replit.nix` (if needed):
```nix
{ pkgs }: {
  deps = [
    pkgs.python311
  ];
}
```

---

## Summary of files to change on Replit

| File | Change |
|------|--------|
| `requirements.txt` | Add `psycopg2-binary`, optionally remove `mysql-connector-python` |
| `app.py` | 5 targeted changes (import, get_db, cursor factory, lastrowid, IF→CASE) |
| `.replit` | Add run command |

**DO NOT touch:** `database.postgres.sql` — already done. `templates/`, `static/` — no changes needed.
