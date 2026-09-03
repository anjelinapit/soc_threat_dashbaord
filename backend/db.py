import os
import sqlite3
import threading
import hashlib
import json
from datetime import datetime, timezone, timedelta

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
DB_PATH = os.path.join(DB_DIR, "dashboard.db")
_local = threading.local()


def get_conn():
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, timeout=10)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA synchronous=NORMAL")
        _local.conn.execute("PRAGMA cache_size=-8000")
    return _local.conn


def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            link TEXT,
            source TEXT,
            source_badge TEXT,
            published TEXT,
            pub_date TEXT,
            description TEXT,
            is_regional INTEGER DEFAULT 0,
            title_hash TEXT UNIQUE,
            fetched_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS news_vectors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            news_id INTEGER NOT NULL,
            vector TEXT NOT NULL,
            FOREIGN KEY (news_id) REFERENCES news(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS news_regional_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            news_id INTEGER NOT NULL,
            keyword TEXT NOT NULL,
            FOREIGN KEY (news_id) REFERENCES news(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS word_cloud_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            weight INTEGER,
            normalized REAL,
            snapshot_date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS attack_vector_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vector TEXT NOT NULL,
            percentage REAL,
            snapshot_date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS phishing_domains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            hits INTEGER DEFAULT 1,
            country TEXT,
            sample_url TEXT,
            first_seen TEXT,
            last_seen TEXT,
            fetched_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS source_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_badge TEXT NOT NULL,
            article_count INTEGER,
            snapshot_date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS otx_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pulse_name TEXT NOT NULL,
            tags TEXT,
            tlp TEXT,
            category TEXT,
            snapshot_date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS vulnerability_posture_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            critical_count INTEGER NOT NULL,
            high_count INTEGER NOT NULL,
            medium_count INTEGER NOT NULL,
            low_count INTEGER NOT NULL,
            overdue_count INTEGER NOT NULL,
            due_7d_count INTEGER NOT NULL,
            snapshot_date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS feed_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            record_count INTEGER DEFAULT 0,
            latency_ms INTEGER,
            error TEXT,
            recorded_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ioc_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ioc_type TEXT NOT NULL,
            value TEXT NOT NULL,
            source TEXT,
            country TEXT,
            first_seen TEXT,
            last_seen TEXT NOT NULL,
            seen_count INTEGER DEFAULT 1,
            UNIQUE(ioc_type, value)
        );

        CREATE INDEX IF NOT EXISTS idx_news_fetched ON news(fetched_at);
        CREATE INDEX IF NOT EXISTS idx_news_hash ON news(title_hash);
        CREATE INDEX IF NOT EXISTS idx_news_vectors_vec ON news_vectors(vector);
        CREATE INDEX IF NOT EXISTS idx_wc_snap_date ON word_cloud_snapshots(snapshot_date);
        CREATE INDEX IF NOT EXISTS idx_av_snap_date ON attack_vector_snapshots(snapshot_date);
        CREATE INDEX IF NOT EXISTS idx_phish_domain ON phishing_domains(domain);
        CREATE INDEX IF NOT EXISTS idx_source_snap_date ON source_snapshots(snapshot_date);
        CREATE INDEX IF NOT EXISTS idx_feed_runs_source ON feed_runs(source, recorded_at);
        CREATE INDEX IF NOT EXISTS idx_ioc_value ON ioc_observations(value);

        CREATE TABLE IF NOT EXISTS stop_words (
            word TEXT PRIMARY KEY,
            added_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS vector_keywords (
            vector TEXT PRIMARY KEY,
            keywords TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS kev_vulnerabilities (
            cve_id TEXT PRIMARY KEY,
            vendor TEXT,
            product TEXT,
            vulnerability TEXT,
            date_added TEXT,
            due_date TEXT,
            cvss REAL,
            severity TEXT,
            saved_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS cvss_cache (
            cve_id TEXT PRIMARY KEY,
            cvss REAL,
            severity TEXT,
            fetched_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS regional_exposure_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            regional_news INTEGER,
            regional_headlines TEXT,
            hosting_countries TEXT,
            snapshot_date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS source_status_cache (
            source_key TEXT PRIMARY KEY,
            online INTEGER,
            status TEXT,
            count INTEGER,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ransomware_victims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT,
            victim_name TEXT,
            website TEXT,
            country TEXT,
            sector TEXT,
            discovered_at TEXT,
            victim_hash TEXT UNIQUE,
            fetched_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS threatfox_iocs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ioc_type TEXT,
            ioc_value TEXT,
            threat_type TEXT,
            malware_family TEXT,
            confidence_level INTEGER,
            reporter TEXT,
            first_seen TEXT,
            ioc_hash TEXT UNIQUE
        );

        CREATE TABLE IF NOT EXISTS epss_cache (
            cve_id TEXT PRIMARY KEY,
            epss_score REAL,
            percentile REAL,
            fetched_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    _local.conn = None


def _title_hash(title):
    norm = title.lower().strip()[:80]
    return hashlib.md5(norm.encode()).hexdigest()


def insert_news_batch(items):
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    for item in items:
        th = _title_hash(item.get("title", ""))
        try:
            cur = conn.execute(
                """INSERT INTO news
                   (title, link, source, source_badge, published, pub_date,
                    description, is_regional, title_hash, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item.get("title"), item.get("link"), item.get("source"),
                 item.get("sourceBadge"), item.get("published"),
                 item.get("pubDate"), item.get("description"),
                 1 if item.get("is_regional") else 0, th, now)
            )
            if cur.rowcount > 0:
                news_id = cur.lastrowid
                inserted += 1
                for vec in (item.get("attack_vectors") or []):
                    conn.execute(
                        "INSERT INTO news_vectors (news_id, vector) VALUES (?, ?)",
                        (news_id, vec)
                    )
                for kw in (item.get("matched_keywords") or []):
                    conn.execute(
                        "INSERT INTO news_regional_keywords (news_id, keyword) VALUES (?, ?)",
                        (news_id, kw)
                    )
        except sqlite3.IntegrityError:
            # A title already in the database is still an article seen in this
            # collection.  Preserve the original fetched_at so the word cloud
            # reflects when articles were first observed, not when they were
            # re-scraped.  Update content fields and re-tag attack vectors
            # so renamed/updated vectors are reflected immediately.
            conn.execute(
                """UPDATE news SET link=?, source=?, source_badge=?, published=?,
                   pub_date=?, description=?, is_regional=?
                   WHERE title_hash=?""",
                (item.get("link"), item.get("source"), item.get("sourceBadge"),
                 item.get("published"), item.get("pubDate"), item.get("description"),
                 1 if item.get("is_regional") else 0, th)
            )
            # Re-tag attack vectors so articles pick up renamed or new vectors.
            existing = conn.execute(
                "SELECT id FROM news WHERE title_hash=?", (th,)
            ).fetchone()
            if existing:
                news_id = existing["id"]
                conn.execute("DELETE FROM news_vectors WHERE news_id=?", (news_id,))
                for vec in (item.get("attack_vectors") or []):
                    conn.execute(
                        "INSERT INTO news_vectors (news_id, vector) VALUES (?, ?)",
                        (news_id, vec)
                    )
    conn.commit()
    return inserted


def snapshot_attack_vectors(vector_pcts):
    conn = get_conn()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    for vector, pct in vector_pcts.items():
        conn.execute(
            "INSERT INTO attack_vector_snapshots (vector, percentage, snapshot_date) VALUES (?, ?, ?)",
            (vector, pct, now)
        )
    conn.commit()


def snapshot_word_cloud(words):
    conn = get_conn()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    for w in words:
        conn.execute(
            "INSERT INTO word_cloud_snapshots (word, weight, normalized, snapshot_date) VALUES (?, ?, ?, ?)",
            (w.get("text"), w.get("weight"), w.get("normalized"), now)
        )
    conn.commit()


def snapshot_source_counts(source_badges):
    conn = get_conn()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    for badge, count in source_badges.items():
        conn.execute(
            "INSERT INTO source_snapshots (source_badge, article_count, snapshot_date) VALUES (?, ?, ?)",
            (badge, count, now)
        )
    conn.commit()


def snapshot_otx_pulses(pulses, categorized):
    conn = get_conn()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    for cat, items in categorized.items():
        for p in items:
            conn.execute(
                "INSERT INTO otx_snapshots (pulse_name, tags, tlp, category, snapshot_date) VALUES (?, ?, ?, ?, ?)",
                (p.get("name"), p.get("tags"), p.get("tlp"), cat, now)
            )
    conn.commit()


def snapshot_vulnerability_posture(posture):
    severity = posture.get("severity", {})
    conn = get_conn()
    conn.execute(
        """INSERT INTO vulnerability_posture_snapshots
           (critical_count, high_count, medium_count, low_count, overdue_count, due_7d_count, snapshot_date)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (severity.get("critical", 0), severity.get("high", 0), severity.get("medium", 0),
         severity.get("low", 0), posture.get("overdue", 0), posture.get("due_7d", 0),
         datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"))
    )
    conn.commit()


def snapshot_feed_runs(feed_health):
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()
    for source, state in feed_health.items():
        conn.execute(
            """INSERT INTO feed_runs (source, status, record_count, latency_ms, error, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source, state.get("status", "UNKNOWN"), state.get("count", 0),
             state.get("latency_ms"), state.get("error", ""), now)
        )
    conn.commit()


def upsert_ioc_observations(iocs):
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()
    for ioc in iocs:
        conn.execute(
            """INSERT INTO ioc_observations (ioc_type, value, source, country, first_seen, last_seen, seen_count)
               VALUES (?, ?, ?, ?, ?, ?, 1)
               ON CONFLICT(ioc_type, value) DO UPDATE SET
                 last_seen = excluded.last_seen, seen_count = seen_count + 1,
                 country = COALESCE(excluded.country, country)""",
            (ioc.get("type"), ioc.get("value"), ioc.get("source"), ioc.get("country"),
             ioc.get("first_seen"), now)
        )
    conn.commit()


def upsert_phishing_domains(domains):
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()
    for d in domains:
        existing = conn.execute(
            "SELECT id, hits FROM phishing_domains WHERE domain = ?",
            (d.get("domain"),)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE phishing_domains SET hits = ?, last_seen = ?, fetched_at = ? WHERE id = ?",
                (d.get("hits", 0), now, now, existing["id"])
            )
        else:
            conn.execute(
                """INSERT INTO phishing_domains (domain, hits, country, sample_url, first_seen, last_seen, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (d.get("domain"), d.get("hits", 0), d.get("country"),
                 d.get("sample_url", ""), now, now, now)
            )
    conn.commit()


def get_news_history(days=7):
    conn = get_conn()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT * FROM news WHERE fetched_at >= ? ORDER BY fetched_at DESC", (since,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_todays_news():
    """Return articles observed during the current UTC day.

    ``fetched_at`` represents when an item was collected, rather than an RSS
    publisher's often missing or inconsistent date.  This makes the cloud a
    reliable view of today's database-backed collection.
    """
    conn = get_conn()
    start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    end = (datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    ).isoformat()
    rows = conn.execute(
        """SELECT * FROM news WHERE fetched_at >= ? AND fetched_at < ?
           ORDER BY COALESCE(pub_date, fetched_at) DESC""",
        (start, end),
    ).fetchall()
    return [dict(r) for r in rows]


def get_vector_trend(days=7):
    conn = get_conn()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
    rows = conn.execute(
        """SELECT snapshot_date, vector, percentage
           FROM attack_vector_snapshots
           WHERE snapshot_date >= ?
           ORDER BY snapshot_date ASC""",
        (since,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_word_cloud_trend(days=7):
    conn = get_conn()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
    rows = conn.execute(
        """SELECT snapshot_date, word, weight
           FROM word_cloud_snapshots
           WHERE snapshot_date >= ?
           ORDER BY snapshot_date ASC""",
        (since,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_source_trend(days=7):
    conn = get_conn()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
    rows = conn.execute(
        """SELECT snapshot_date, source_badge, article_count
           FROM source_snapshots
           WHERE snapshot_date >= ?
           ORDER BY snapshot_date ASC""",
        (since,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_phishing_history(days=30):
    conn = get_conn()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """SELECT domain, hits, country, first_seen, last_seen
           FROM phishing_domains
           WHERE last_seen >= ?
           ORDER BY hits DESC LIMIT 20""",
        (since,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_otx_history(days=7):
    conn = get_conn()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
    rows = conn.execute(
        """SELECT snapshot_date, pulse_name, tags, tlp, category
           FROM otx_snapshots
           WHERE snapshot_date >= ?
           ORDER BY snapshot_date ASC""",
        (since,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_total_news_count():
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) as cnt FROM news").fetchone()
    return row["cnt"] if row else 0


def get_top_keywords(days=7, limit=20):
    conn = get_conn()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
    rows = conn.execute(
        """SELECT word, SUM(weight) as total_weight, COUNT(*) as appearances
           FROM word_cloud_snapshots
           WHERE snapshot_date >= ?
           GROUP BY word
           ORDER BY total_weight DESC
           LIMIT ?""",
        (since, limit)
    ).fetchall()
    return [dict(r) for r in rows]


def get_vector_distribution_by_source(days=7):
    conn = get_conn()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """SELECT n.source_badge, nv.vector, COUNT(*) as cnt
           FROM news n
           JOIN news_vectors nv ON nv.news_id = n.id
           WHERE n.fetched_at >= ?
           GROUP BY n.source_badge, nv.vector
           ORDER BY n.source_badge, cnt DESC""",
        (since,)
    ).fetchall()
    result = {}
    for r in rows:
        src = r["source_badge"]
        if src not in result:
            result[src] = []
        result[src].append({"vector": r["vector"], "count": r["cnt"]})
    return result


def get_vector_percentages_from_db(days=7):
    conn = get_conn()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """SELECT nv.vector, COUNT(*) as cnt
           FROM news_vectors nv
           JOIN news n ON n.id = nv.news_id
           WHERE n.fetched_at >= ?
           GROUP BY nv.vector""",
        (since,)
    ).fetchall()
    counts = {r["vector"]: r["cnt"] for r in rows}
    total = sum(counts.values()) or 1
    all_vectors = get_all_vector_keywords()
    return {v: round((counts.get(v, 0) / total) * 100, 1) for v in all_vectors}


def cleanup_old_data(keep_days=90):
    conn = get_conn()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).isoformat()
    cutoff_snap = (datetime.now(timezone.utc) - timedelta(days=keep_days)).strftime("%Y-%m-%d %H:%M")
    conn.execute("DELETE FROM news WHERE fetched_at < ?", (cutoff,))
    conn.execute("DELETE FROM word_cloud_snapshots WHERE snapshot_date < ?", (cutoff_snap,))
    conn.execute("DELETE FROM attack_vector_snapshots WHERE snapshot_date < ?", (cutoff_snap,))
    conn.execute("DELETE FROM source_snapshots WHERE snapshot_date < ?", (cutoff_snap,))
    conn.execute("DELETE FROM otx_snapshots WHERE snapshot_date < ?", (cutoff_snap,))
    conn.execute("DELETE FROM phishing_domains WHERE last_seen < ?", (cutoff,))
    conn.execute("DELETE FROM ioc_observations WHERE last_seen < ?", (cutoff,))
    conn.execute("DELETE FROM feed_runs WHERE recorded_at < ?", (cutoff,))
    conn.execute("DELETE FROM vulnerability_posture_snapshots WHERE snapshot_date < ?", (cutoff_snap,))
    conn.commit()


def get_articles_paginated(search="", source="", vector="", page=1, per_page=20):
    conn = get_conn()
    where_clauses = []
    params = []

    if search:
        where_clauses.append("(n.title LIKE ? OR n.description LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if source:
        where_clauses.append("n.source_badge = ?")
        params.append(source)
    if vector:
        where_clauses.append("EXISTS (SELECT 1 FROM news_vectors nv WHERE nv.news_id = n.id AND nv.vector = ?)")
        params.append(vector)

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    count_row = conn.execute(
        f"SELECT COUNT(*) as cnt FROM news n{where_sql}", params
    ).fetchone()
    total = count_row["cnt"] if count_row else 0
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, pages))
    offset = (page - 1) * per_page

    rows = conn.execute(
        f"""SELECT n.* FROM news n{where_sql}
            ORDER BY n.fetched_at DESC LIMIT ? OFFSET ?""",
        params + [per_page, offset]
    ).fetchall()

    articles = []
    for r in rows:
        article = dict(r)
        vec_rows = conn.execute(
            "SELECT vector FROM news_vectors WHERE news_id = ?", (r["id"],)
        ).fetchall()
        article["attack_vectors"] = [vr["vector"] for vr in vec_rows]
        articles.append(article)

    return {
        "articles": articles,
        "total": total,
        "page": page,
        "pages": pages,
        "per_page": per_page,
    }


def update_article_vectors(news_id, vectors):
    conn = get_conn()
    conn.execute("DELETE FROM news_vectors WHERE news_id = ?", (news_id,))
    for vec in vectors:
        conn.execute(
            "INSERT INTO news_vectors (news_id, vector) VALUES (?, ?)",
            (news_id, vec)
        )
    conn.commit()


def get_article_vectors(news_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT vector FROM news_vectors WHERE news_id = ?", (news_id,)
    ).fetchall()
    return [r["vector"] for r in rows]


def get_stop_words():
    conn = get_conn()
    rows = conn.execute("SELECT word FROM stop_words ORDER BY word").fetchall()
    return [r["word"] for r in rows]


def add_stop_word(word):
    conn = get_conn()
    word = word.strip().lower()
    if not word:
        return False
    try:
        conn.execute("INSERT OR IGNORE INTO stop_words (word) VALUES (?)", (word,))
        conn.commit()
        return True
    except Exception:
        return False


def remove_stop_word(word):
    conn = get_conn()
    conn.execute("DELETE FROM stop_words WHERE word = ?", (word.strip().lower(),))
    conn.commit()
    return True


def get_all_vector_keywords():
    conn = get_conn()
    rows = conn.execute("SELECT vector, keywords FROM vector_keywords ORDER BY vector").fetchall()
    result = {}
    for r in rows:
        try:
            result[r["vector"]] = json.loads(r["keywords"])
        except Exception:
            result[r["vector"]] = []
    return result


def update_vector_keywords(vector, keywords):
    conn = get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO vector_keywords (vector, keywords, updated_at)
           VALUES (?, ?, ?)""",
        (vector, json.dumps(keywords), datetime.now(timezone.utc).isoformat())
    )
    conn.commit()


def retag_all_articles(vector_keywords):
    """Re-tag every article in news_vectors using the current keyword definitions.

    This fixes orphaned tags when vectors are renamed (e.g. IoT/OT -> OT/ICS)
    and ensures newly added keywords are reflected immediately.
    """
    conn = get_conn()
    import re as _re

    def _count(text, patterns):
        count = 0
        for p in patterns:
            if " " in p:
                count += len(_re.findall(_re.escape(p), text))
            else:
                count += len(_re.findall(r"\b" + _re.escape(p) + r"\b", text))
        return count

    rows = conn.execute("SELECT id, title, description FROM news").fetchall()
    conn.execute("DELETE FROM news_vectors")
    inserted = 0
    for r in rows:
        text = f"{r['title'] or ''} {r['description'] or ''}".lower()
        for vector, patterns in vector_keywords.items():
            if _count(text, patterns) > 0:
                conn.execute(
                    "INSERT INTO news_vectors (news_id, vector) VALUES (?, ?)",
                    (r["id"], vector)
                )
                inserted += 1
    conn.commit()
    return inserted


def get_all_news_sources():
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT source_badge FROM news ORDER BY source_badge"
    ).fetchall()
    return [r["source_badge"] for r in rows]


def seed_stop_words(words):
    conn = get_conn()
    for w in words:
        try:
            conn.execute("INSERT OR IGNORE INTO stop_words (word) VALUES (?)", (w.lower().strip(),))
        except Exception:
            pass
    conn.commit()


def seed_vector_keywords(keyword_map):
    """Sync vector_keywords table with the hardcoded source-of-truth dict.

    - Updates existing vectors with the latest keywords from code.
    - Inserts new vectors not yet in the DB.
    - Removes stale vectors from DB that no longer exist in code.
    - Always re-tags all articles on startup so renamed vectors or
      updated keyword lists are reflected immediately.
    """
    conn = get_conn()
    existing_rows = conn.execute("SELECT vector FROM vector_keywords").fetchall()
    existing_names = {r["vector"] for r in existing_rows}
    code_names = set(keyword_map.keys())

    for vector, keywords in keyword_map.items():
        conn.execute(
            """INSERT OR REPLACE INTO vector_keywords (vector, keywords, updated_at)
               VALUES (?, ?, ?)""",
            (vector, json.dumps(keywords), datetime.now(timezone.utc).isoformat())
        )

    for stale in existing_names - code_names:
        conn.execute("DELETE FROM news_vectors WHERE vector = ?", (stale,))
        conn.execute("DELETE FROM vector_keywords WHERE vector = ?", (stale,))

    conn.commit()
    # Always re-tag so keyword additions/removals within existing vectors
    # and any orphaned tags from renames are corrected immediately.
    retag_all_articles(keyword_map)


def load_dashboard_from_db():
    conn = get_conn()
    result = {}

    since_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    since_30d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    since_7d_snap = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d %H:%M")

    rows = conn.execute(
        "SELECT * FROM news WHERE fetched_at >= ? ORDER BY fetched_at DESC LIMIT 30",
        (since_7d,)
    ).fetchall()
    news = []
    for r in rows:
        article = dict(r)
        vec_rows = conn.execute(
            "SELECT vector FROM news_vectors WHERE news_id = ?", (r["id"],)
        ).fetchall()
        article["attack_vectors"] = [vr["vector"] for vr in vec_rows]
        news.append(article)
    result["news"] = news

    result["total_news_stored"] = get_total_news_count()

    phish = conn.execute(
        "SELECT domain, hits, country, sample_url FROM phishing_domains WHERE last_seen >= ? ORDER BY hits DESC LIMIT 15",
        (since_30d,)
    ).fetchall()
    result["phishing_domains"] = [dict(p) for p in phish]

    otx = conn.execute(
        "SELECT pulse_name, tags, tlp, category FROM otx_snapshots WHERE snapshot_date >= ? GROUP BY pulse_name",
        (since_7d_snap,)
    ).fetchall()
    otx_list = []
    otx_categorized = {}
    for r in otx:
        pulse = {"name": r["pulse_name"], "tags": r["tags"] or "", "tlp": r["tlp"] or "WHITE", "date": ""}
        otx_list.append(pulse)
        cat = r["category"] or "Other"
        if cat not in otx_categorized:
            otx_categorized[cat] = []
        otx_categorized[cat].append(pulse)
    result["malware"] = otx_list
    result["malware_categorized"] = otx_categorized

    sources = conn.execute(
        "SELECT DISTINCT source_badge FROM news ORDER BY source_badge"
    ).fetchall()
    result["sources"] = [s["source_badge"] for s in sources]

    return result


def save_kev(kev_items):
    """Persist enriched KEV records to the database."""
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()
    for item in kev_items:
        conn.execute(
            """INSERT OR REPLACE INTO kev_vulnerabilities
               (cve_id, vendor, product, vulnerability, date_added, due_date, cvss, severity, saved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item.get("cve_id", ""),
                item.get("vendor", ""),
                item.get("product", ""),
                item.get("vulnerability", ""),
                item.get("date_added", ""),
                item.get("due_date", ""),
                item.get("cvss"),
                item.get("severity", "UNKNOWN"),
                now,
            )
        )
    conn.commit()


def load_kev():
    """Load persisted KEV records from the database."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT cve_id, vendor, product, vulnerability, date_added, due_date, cvss, severity FROM kev_vulnerabilities ORDER BY date_added DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def save_cvss_cache(items):
    """Persist CVSS cache entries to avoid re-fetching from NVD on restart."""
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()
    for item in items:
        conn.execute(
            """INSERT OR REPLACE INTO cvss_cache (cve_id, cvss, severity, fetched_at)
               VALUES (?, ?, ?, ?)""",
            (item["cve_id"], item.get("cvss"), item.get("severity"), now)
        )
    conn.commit()


def load_cvss_cache():
    """Load CVSS cache from DB. Returns dict keyed by CVE ID."""
    conn = get_conn()
    rows = conn.execute("SELECT cve_id, cvss, severity FROM cvss_cache").fetchall()
    return {r["cve_id"]: {"cvss": r["cvss"], "severity": r["severity"]} for r in rows}


def save_regional_exposure(exposure):
    """Persist regional exposure snapshot."""
    conn = get_conn()
    conn.execute(
        """INSERT INTO regional_exposure_snapshots
           (regional_news, regional_headlines, hosting_countries, snapshot_date)
           VALUES (?, ?, ?, ?)""",
        (
            exposure.get("regional_news", 0),
            json.dumps(exposure.get("regional_headlines", [])),
            json.dumps(exposure.get("hosting_countries", [])),
            datetime.now(timezone.utc).isoformat(),
        )
    )
    conn.commit()


def load_regional_exposure():
    """Load most recent regional exposure snapshot."""
    conn = get_conn()
    row = conn.execute(
        "SELECT regional_news, regional_headlines, hosting_countries FROM regional_exposure_snapshots ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not row:
        return {}
    return {
        "regional_news": row["regional_news"],
        "regional_headlines": json.loads(row["regional_headlines"] or "[]"),
        "hosting_countries": json.loads(row["hosting_countries"] or "[]"),
    }


def save_source_status(status_dict):
    """Persist source status so it survives restarts."""
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()
    for key, info in status_dict.items():
        conn.execute(
            """INSERT OR REPLACE INTO source_status_cache
               (source_key, online, status, count, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (key, 1 if info.get("online") else 0, info.get("status", ""), info.get("count", 0), now)
        )
    conn.commit()


def load_source_status():
    """Load last-known source status from DB."""
    conn = get_conn()
    rows = conn.execute("SELECT source_key, online, status, count FROM source_status_cache").fetchall()
    return {r["source_key"]: {"online": bool(r["online"]), "status": r["status"], "count": r["count"]} for r in rows}


def load_feed_health():
    """Load most recent feed health from feed_runs table."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT source, status, record_count, latency_ms, recorded_at
           FROM feed_runs WHERE id IN (
               SELECT MAX(id) FROM feed_runs GROUP BY source
           )"""
    ).fetchall()
    result = {}
    for r in rows:
        result[r["source"]] = {
            "status": r["status"],
            "count": r["record_count"],
            "latency_ms": r["latency_ms"],
            "last_success": r["recorded_at"],
        }
    return result


def load_ioc_queue():
    """Load recent IOCs from ioc_observations table."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT ioc_type, value, source, country, seen_count
           FROM ioc_observations ORDER BY last_seen DESC LIMIT 50"""
    ).fetchall()
    return [{"type": r["ioc_type"], "value": r["value"], "source": r["source"],
             "country": r["country"], "seen_count": r["seen_count"]} for r in rows]


def upsert_ransomware_victims(victims):
    """Upsert ransomware victim records into DB."""
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()
    for v in victims:
        v_hash = hashlib.md5(f"{v.get('group_name')}:{v.get('victim_name')}:{v.get('discovered_at')}".encode()).hexdigest()
        conn.execute(
            """INSERT OR IGNORE INTO ransomware_victims
               (group_name, victim_name, website, country, sector, discovered_at, victim_hash, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (v.get("group_name"), v.get("victim_name"), v.get("website", ""),
             v.get("country", ""), v.get("sector", ""), v.get("discovered_at", ""), v_hash, now)
        )
    conn.commit()


def load_ransomware_victims(limit=50):
    """Load recent ransomware victims from DB."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT group_name, victim_name, website, country, sector, discovered_at
           FROM ransomware_victims ORDER BY discovered_at DESC, id DESC LIMIT ?""",
        (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_threatfox_iocs(iocs):
    """Upsert ThreatFox IOC records into DB."""
    conn = get_conn()
    for ioc in iocs:
        ioc_hash = hashlib.md5(f"{ioc.get('ioc_type')}:{ioc.get('ioc_value')}".encode()).hexdigest()
        conn.execute(
            """INSERT OR IGNORE INTO threatfox_iocs
               (ioc_type, ioc_value, threat_type, malware_family, confidence_level, reporter, first_seen, ioc_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (ioc.get("ioc_type"), ioc.get("ioc_value"), ioc.get("threat_type", ""),
             ioc.get("malware_family", ""), ioc.get("confidence_level", 100),
             ioc.get("reporter", ""), ioc.get("first_seen", ""), ioc_hash)
        )
    conn.commit()


def load_threatfox_iocs(limit=50):
    """Load recent ThreatFox IOCs from DB."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT ioc_type, ioc_value, threat_type, malware_family, confidence_level, reporter, first_seen
           FROM threatfox_iocs ORDER BY id DESC LIMIT ?""",
        (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def save_epss_cache(items):
    """Save EPSS scores for CVEs."""
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()
    for cve_id, score_data in items.items():
        conn.execute(
            """INSERT OR REPLACE INTO epss_cache (cve_id, epss_score, percentile, fetched_at)
               VALUES (?, ?, ?, ?)""",
            (cve_id, score_data.get("epss"), score_data.get("percentile"), now)
        )
    conn.commit()


def load_epss_cache():
    """Load EPSS score cache from DB."""
    conn = get_conn()
    rows = conn.execute("SELECT cve_id, epss_score, percentile FROM epss_cache").fetchall()
    return {r["cve_id"]: {"epss": r["epss_score"], "percentile": r["percentile"]} for r in rows}

