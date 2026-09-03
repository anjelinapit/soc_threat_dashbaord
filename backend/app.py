import os
import sys
import platform
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import re
import json
import time
import string
import threading
import logging
import urllib.parse
import resource
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests
import feedparser
from bs4 import BeautifulSoup
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")
CACHE_DIR = os.path.join(BASE_DIR, "cache")

app = Flask(__name__, static_folder=None)
CORS(app)

GCC_REGIONAL_KEYWORDS = [
    "UAE", "United Arab Emirates", "Dubai", "Abu Dhabi",
    "GCC", "Middle East", "Saudi Arabia", "Qatar",
    "Bahrain", "Kuwait", "Oman", "Sharjah",
]

STOP_WORDS = {
    "the", "and", "is", "for", "with", "that", "from", "this", "are",
    "was", "has", "have", "not", "but", "can", "will", "its", "you",
    "all", "had", "her", "his", "how", "may", "now", "old", "our",
    "out", "own", "say", "she", "too", "use", "been", "does", "did",
    "get", "got", "let", "say", "set", "two", "run", "new", "one",
    "also", "into", "just", "than", "them", "then", "these", "they",
    "were", "what", "when", "your", "about", "after", "being", "each",
    "find", "more", "most", "over", "some", "such", "take", "very",
    "well", "were", "only", "other", "which", "their", "there", "would",
    "could", "should", "under", "while",
    "report", "says", "uses", "used", "via",
    "billion", "million", "first", "last", "year", "years",
    "top", "new", "big", "tech", "file", "case", "part", "made",
    "like", "many", "much", "need", "know", "make", "look", "come",
    "still", "even", "though", "because", "through", "before",
    "between", "same", "those", "both", "every", "any", "during",
    "has", "its", "may", "use", "per", "yet", "two", "see", "way",
    "put", "end", "big", "off", "try", "ask", "let", "cut", "red",
    "hot", "bit", "lot", "job", "few", "long", "high", "held",
    "down", "life", "left", "live", "keep", "made", "best", "deal",
}

NEWS_TITLE_EXCLUSIONS = [
    "virtual event",
    "webinar",
    "conference",
    "summit",
    "workshop",
    "podcast",
    "stormcast",
    "newsletter",
    "roundup",
    "weekly recap",
    "monthly recap",
    "daily recap",
    "year in review",
    "best of",
    "top 10",
    "top 5",
    "interview with",
    "q&a with",
    "ama with",
    "ask me anything",
    "book review",
    "product review",
    "vendor spotlight",
    "partner spotlight",
    "sponsored",
    "advertisement",
    "press release",
    "announcement",
    "join us",
    "register now",
    "don't miss",
    "early bird",
    "free ticket",
    "discount code",
    "promo code",
    "coupon",
    "giveaway",
    "contest",
    "winner",
    "congratulations",
    "happy birthday",
    "holiday",
    "merry christmas",
    "happy new year",
    "valentine",
    "easter",
    "halloween",
    "thanksgiving",
    "black friday",
    "cyber monday",
    "deal of the day",
    "sale",
    "discount",
    "offer",
    "limited time",
    "act now",
    "subscribe",
    "unsubscribe",
    "manage preferences",
    "update profile",
    "view in browser",
    "email preferences",
    "privacy policy",
    "terms of service",
    "cookie policy",
    "legal",
    "imprint",
    "contact us",
    "about us",
    "our team",
    "careers",
    "jobs",
    "hiring",
    "we're hiring",
    "join our team",
    "open positions",
    "apply now",
    "submit resume",
    "interview tips",
    "resume tips",
    "career advice",
    "salary survey",
    "compensation report",
    "market report",
    "industry report",
    "forecast",
    "prediction",
    "trend report",
    "state of",
    "report card",
    "scorecard",
    "benchmark",
    "maturity model",
    "framework",
    "best practices",
    "whitepaper",
    "ebook",
    "infographic",
    "case study",
    "customer story",
    "success story",
    "testimonial",
    "review",
    "analysis",
    "opinion",
    "editorial",
    "commentary",
    "perspective",
    "thought leadership",
    "guest post",
    "contributor",
    "sponsored content",
    "native advertising",
    "brand content",
    "partner content",
    "advertorial",
    "promotional",
    "marketing",
    "pr",
    "public relations",
    "media kit",
    "advertising",
    "sponsorship",
    "partnership",
    "collaboration",
    "integration",
    "ecosystem",
    "marketplace",
    "store",
    "shop",
    "buy now",
    "purchase",
    "pricing",
    "subscription",
    "plan",
    "tier",
    "enterprise",
    "professional",
    "personal",
    "free trial",
    "demo",
    "request demo",
    "schedule demo",
    "book demo",
    "contact sales",
    "talk to sales",
    "get started",
    "sign up",
    "login",
    "log in",
    "sign in",
    "create account",
    "forgot password",
    "reset password",
    "help center",
    "support",
    "documentation",
    "docs",
    "api reference",
    "sdk",
    "library",
    "framework",
    "toolkit",
    "platform",
    "solution",
    "product",
    "service",
    "offering",
    "portfolio",
    "suite",
    "bundle",
    "package",
    "bundle",
    "kit",
    "starter",
    "pro",
    "enterprise",
    "advanced",
    "premium",
    "ultimate",
    "standard",
    "basic",
    "lite",
    "mini",
    "micro",
    "nano",
    "ultra",
    "max",
    "plus",
    "extra",
    "select",
    "choice",
    "preferred",
    "recommended",
    "featured",
    "popular",
    "trending",
    "hot",
    "new",
    "latest",
    "recent",
    "updated",
    "refreshed",
    "improved",
    "enhanced",
    "upgraded",
    "released",
    "launched",
    "deployed",
    "rolled out",
    "gone live",
    "available now",
    "coming soon",
    "coming early",
    "coming late",
    "coming Q",
    "coming 20",
    "coming 19",
]

NEWS_TITLE_REQUIRED_KEYWORDS = [
    "vulnerability", "vulnerabilities", "exploit", "exploited", "cve",
    "malware", "ransomware", "backdoor", "trojan", "worm", "virus",
    "phishing", "credential", "stealer", "infostealer",
    "breach", "leak", "exposed", "compromised",
    "attack", "campaign", "threat", "apt", "actor",
    "zero-day", "zero day", "0-day",
    "patch", "patched", "hotfix", "update",
    "advisory", "alert", "warning", "notification",
    "kev", "cisa",
    "hack", "hacked", "hijack", "hijacked",
    "encryption", "decrypt", "decryptor",
    "botnet", "c2", "command and control",
    "spy", "spying", "surveillance", "monitor",
    "data breach", "data leak", "data theft",
    "sql injection", "xss", "rce", "remote code",
    "privilege escalation", "elevation",
    "authentication", "authorization", "mfa", "bypass",
    "firewall", "ids", "ips", "siem", "edr", "xdr",
    "incident", "response", "forensic", "investigation",
    "ioc", "indicators of compromise", "ttp",
    "mitre", "att&ck",
    "ddos", "denial of service",
    "supply chain", "dependency", "typosquatting",
    "social engineering", "pretexting", "baiting",
    "insider threat", "insider risk",
    "cloud security", "container security", "kubernetes",
    "api security", "microservice",
    "iot", "industrial control", "scada", "ot security", "ot", "ics security",
    "plc", "dcs", "hmi", "rtu", "modbus", "dnp3", "operational technology",
    "control system", "siemens", "schneider", "rockwell", "honeywell",
    "factory automation", "water treatment", "power grid", "pipeline",
    "dragos", "claroty", "nozomi", "ics advisory", "substation",
    "mobile security", "android", "ios",
    "endpoint", "device",
    "network security", "perimeter",
    "identity", "access management", "iam",
    "encryption", "certificate", "tls", "ssl",
    "logging", "monitoring", "detection",
    "compliance", "regulation", "gdpr", "hipaa", "pci",
]

CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
PHISHSTATS_URL = "https://api.phishstats.info/api/phishing"
OPENPHISH_URL = "https://openphish.com/feed.txt"
OTX_URL = "https://otx.alienvault.com/otxapi/pulses"
CVE_CIRCL_URL = "https://cve.circl.lu/api/cve"

KEV_CACHE_FILE = os.path.join(CACHE_DIR, "kev_catalog.json")
KEV_CACHE_TTL = 1800
kev_cache = {"data": [], "ts": 0}

CVSS_CACHE_TTL = 3600
cvss_cache = {}
cvss_cache_lock = threading.Lock()

RANSOMWARE_LIVE_URL = "https://api.ransomware.live/v2/recentvictims"
URLHAUS_URL = "https://urlhaus-api.abuse.ch/v1/urls/recent/"
THREATFOX_URL = "https://threatfox-api.abuse.ch/api/v1/"
EPSS_API_URL = "https://api.first.org/data/v1/epss"

source_status = {
    "cisa_kev": {"online": False, "status": "PENDING", "count": 0},
    "phishing": {"online": False, "status": "PENDING", "count": 0},
    "otx": {"online": False, "status": "PENDING", "count": 0},
    "ransomware_live": {"online": False, "status": "PENDING", "count": 0},
    "threatfox": {"online": False, "status": "PENDING", "count": 0},
    "rss_thn": {"online": False, "status": "PENDING", "count": 0},
    "rss_bleeping": {"online": False, "status": "PENDING", "count": 0},
    "rss_darkreading": {"online": False, "status": "PENDING", "count": 0},
    "rss_securityweek": {"online": False, "status": "PENDING", "count": 0},
    "rss_cisa": {"online": False, "status": "PENDING", "count": 0},
    "rss_sans": {"online": False, "status": "PENDING", "count": 0},
    "rss_cisa_ics": {"online": False, "status": "PENDING", "count": 0},
    "rss_securityweek_ics": {"online": False, "status": "PENDING", "count": 0},
}

COLLECTOR_INTERVALS = {
    "kev": 30 * 60,
    "phishing": 30 * 60,
    "otx": 5 * 60,
    "news": 10 * 60,
    "ransomware": 15 * 60,
    "threatfox": 15 * 60,
}
collector_state = {
    name: {"last_run": 0, "last_success": None, "latency_ms": None,
           "status": "PENDING", "error": "", "count": 0}
    for name in COLLECTOR_INTERVALS
}
collector_results = {"kev": [], "phishing": [], "otx": [], "news": [], "ransomware": [], "threatfox": []}
kev_display_cache = []

APT_GROUPS = [
    {
        "name": "Lazarus Group",
        "aliases": ["APT38", "Hidden Cobra", "BlueNoroff", "Andariel"],
        "origin": "North Korea",
        "flag": "🇰🇵",
        "target_sectors": ["Finance", "Cryptocurrency", "Defense", "Government"],
        "target_regions": ["Global", "US", "Asia", "Middle East"],
        "description": "Sophisticated nation-state threat group known for financial theft, crypto heists, and destructive cyber attacks."
    },
    {
        "name": "APT28 (Fancy Bear)",
        "aliases": ["Fancy Bear", "Pawn Storm", "Strontium", "TA422"],
        "origin": "Russia",
        "flag": "🇷🇺",
        "target_sectors": ["Government", "Defense", "NATO", "Energy", "Media"],
        "target_regions": ["Europe", "US", "Middle East"],
        "description": "GRU-affiliated cyber espionage group targeting government entities, defense contractors, and critical infrastructure."
    },
    {
        "name": "APT29 (Cozy Bear)",
        "aliases": ["Cozy Bear", "NOBELIUM", "Midnight Blizzard", "Cloaked Ursa"],
        "origin": "Russia",
        "flag": "🇷🇺",
        "target_sectors": ["Government", "Diplomatic", "Think Tanks", "Cloud IT"],
        "target_regions": ["US", "Europe", "Global"],
        "description": "SVR-backed stealthy cyber espionage unit notorious for supply chain compromises and cloud credential attacks."
    },
    {
        "name": "Volt Typhoon",
        "aliases": ["BRONZE SILHOUETTE", "Vanguard Panda"],
        "origin": "China",
        "flag": "🇨🇳",
        "target_sectors": ["Critical Infrastructure", "Telecom", "Energy", "Ports", "Water"],
        "target_regions": ["US", "Guam", "GCC", "Global"],
        "description": "State-sponsored actor focused on pre-positioning and persistence inside critical infrastructure networks using living-off-the-land techniques."
    },
    {
        "name": "MuddyWater",
        "aliases": ["Static Kitten", "Mercury", "Seedworm"],
        "origin": "Iran",
        "flag": "🇮🇷",
        "target_sectors": ["Government", "Telecom", "Oil & Gas", "Defense"],
        "target_regions": ["Middle East", "GCC", "North Africa", "South Asia"],
        "description": "MOIS-linked threat actor conducting persistent cyber espionage, phishing campaigns, and credential harvesting across the Middle East."
    },
    {
        "name": "APT33 (Elfin)",
        "aliases": ["Holmium", "Refined Kitten", "MAGALLAN"],
        "origin": "Iran",
        "flag": "🇮🇷",
        "target_sectors": ["Aviation", "Energy", "Petrochemical", "Defense"],
        "target_regions": ["Middle East", "GCC", "US"],
        "description": "Espionage group targeting aerospace, energy, and petrochemical organizations across the Middle East and Gulf region."
    },
    {
        "name": "LockBit Group",
        "aliases": ["LockBit 3.0", "LockBit Black"],
        "origin": "Cybercrime Syndicate",
        "flag": "🏴‍☠️",
        "target_sectors": ["Healthcare", "Manufacturing", "Finance", "Government"],
        "target_regions": ["Global", "GCC", "US", "Europe"],
        "description": "Prolific Ransomware-as-a-Service (RaaS) operation engaging in double extortion and high-volume victim targeting."
    },
    {
        "name": "RansomHub",
        "aliases": ["Cyclops", "Knight RaaS"],
        "origin": "Cybercrime Syndicate",
        "flag": "🏴‍☠️",
        "target_sectors": ["Healthcare", "Critical Infrastructure", "Enterprise"],
        "target_regions": ["Global", "US", "Europe", "Middle East"],
        "description": "Fast-growing ransomware cartel targeting major enterprise and critical infrastructure organizations worldwide."
    }
]

dashboard_cache = {
    "kev": [], "phishing_domains": [],
    "malware": [], "malware_categorized": {}, "news": [],
    "word_cloud": [], "attack_vectors": {},
    "regional_mention_count": 0, "last_updated": None,
    "source_status": source_status, "open_alerts": 0,
    "total_news_stored": 0,
    "posture": {}, "regional_exposure": {}, "ioc_queue": [],
    "attack_coverage": [], "feed_health": {},
    "ransomware_victims": [], "threatfox_iocs": [],
    "threat_actors": [], "geo_events": [],
}
cache_lock = threading.Lock()

APP_START_TIME = time.time()


BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Mobile Safari/537.36"
)


def _safe_get(url, params=None, timeout=15, retries=1):
    for attempt in range(retries + 1):
        try:
            resp = requests.get(
                url, params=params, timeout=timeout,
                headers={"User-Agent": BROWSER_UA}
            )
            resp.raise_for_status()
            return resp
        except Exception:
            if attempt < retries:
                time.sleep(1)
                continue
            return None
    return None


def _test_endpoint(name, url, method="GET", timeout=3):
    try:
        start = time.time()
        if method == "GET":
            resp = requests.get(url, timeout=timeout, headers={"User-Agent": BROWSER_UA})
            if resp.status_code == 403:
                resp = requests.get(url, timeout=timeout, headers={"User-Agent": MOBILE_UA})
        else:
            resp = requests.post(url, timeout=timeout, headers={"User-Agent": BROWSER_UA})
        elapsed = round(time.time() - start, 2)
        resp.raise_for_status()
        return True, f"ONLINE ({resp.status_code} OK, {elapsed}s)"
    except requests.exceptions.Timeout:
        return False, "TIMEOUT"
    except requests.exceptions.ConnectionError:
        return False, "CONN_ERROR"
    except requests.exceptions.HTTPError as e:
        return False, f"HTTP_{e.response.status_code}"
    except Exception as e:
        return False, f"ERROR: {str(e)[:40]}"


def verify_and_test_scrapers():
    logger.info("=" * 60)
    logger.info("  SOC THREAT DASHBOARD - STARTUP VERIFICATION")
    logger.info("=" * 60)

    tests = [
        ("cisa_kev", "CISA KEV", CISA_KEV_URL),
        ("phishing", "PhishStats", PHISHSTATS_URL),
        ("otx", "AlienVault OTX", f"{OTX_URL}?limit=1"),
        ("ransomware_live", "Ransomware.live", RANSOMWARE_LIVE_URL),
        ("threatfox", "URLhaus (abuse.ch)", URLHAUS_URL),
        ("rss_thn", "RSS: The Hacker News", "https://feeds.feedburner.com/TheHackersNews"),
        ("rss_bleeping", "RSS: BleepingComputer", "https://www.bleepingcomputer.com/feed/"),
        ("rss_darkreading", "RSS: Dark Reading", "https://www.darkreading.com/rss.xml"),
        ("rss_securityweek", "RSS: SecurityWeek", "https://www.securityweek.com/feed/"),
        ("rss_cisa", "RSS: CISA Advisories", "https://www.cisa.gov/cybersecurity-advisories/all.xml"),
        ("rss_sans", "RSS: SANS ISC", "https://isc.sans.edu/rssfeed_full.xml"),
        ("rss_cisa_ics", "RSS: CISA ICS", "https://www.cisa.gov/cybersecurity-advisories/ics-advisories.xml"),
        ("rss_securityweek_ics", "RSS: SecurityWeek ICS/OT", "https://www.securityweek.com/category/ics-ot/feed/"),
    ]

    for key, name, url in tests:
        ok, msg = _test_endpoint(name, url)
        icon = "\u2713" if ok else "\u2717"
        logger.info("  [%s] %s: %s", icon, name, msg)
        with cache_lock:
            source_status.setdefault(key, {})["online"] = ok
            source_status[key]["status"] = msg

    logger.info("=" * 60)


def fetch_kev():
    now = time.time()
    if kev_cache["data"] and (now - kev_cache["ts"]) < KEV_CACHE_TTL:
        return kev_cache["data"]

    if os.path.exists(KEV_CACHE_FILE):
        try:
            age = now - os.path.getmtime(KEV_CACHE_FILE)
            if age < KEV_CACHE_TTL:
                with open(KEV_CACHE_FILE, "r") as f:
                    data = json.load(f)
                kev_cache["data"] = data
                kev_cache["ts"] = now
                return data
        except Exception:
            pass

    try:
        resp = requests.get(CISA_KEV_URL, timeout=20, headers={"User-Agent": BROWSER_UA})
        resp.raise_for_status()
        catalog = resp.json()
        vulns = list(catalog.get("vulnerabilities") or [])
        vulns.sort(key=lambda item: item.get("dateAdded") or "", reverse=True)
        # Keep the actionable newest records in memory while retaining a
        # predictable response size for the wall-board.
        vulns = vulns[:50]

        if vulns:
            with cache_lock:
                source_status["cisa_kev"].update({"online": True, "count": len(vulns), "status": f"ONLINE ({len(vulns)} KEVs)"})
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(KEV_CACHE_FILE, "w") as f:
                json.dump(vulns, f)
            kev_cache["data"] = vulns
            kev_cache["ts"] = now
        return vulns
    except Exception:
        with cache_lock:
            source_status["cisa_kev"].update({"online": False, "status": "OFFLINE"})
        if os.path.exists(KEV_CACHE_FILE):
            try:
                with open(KEV_CACHE_FILE, "r") as f:
                    data = json.load(f)
                kev_cache["data"] = data
                kev_cache["ts"] = now
                return data
            except Exception:
                pass
        return kev_cache.get("data", [])


def fetch_cvss_for_cve(cve_id):
    now = time.time()
    with cvss_cache_lock:
        if cve_id in cvss_cache:
            entry = cvss_cache[cve_id]
            if (now - entry.get("ts", 0)) < CVSS_CACHE_TTL:
                return entry["cvss"], entry["severity"]

    try:
        resp = _safe_get(f"{CVE_CIRCL_URL}/{cve_id}", timeout=12)
        if resp is None:
            return None, None
        data = resp.json()

        score = None
        severity = None

        metrics_list = (data.get("containers") or {}).get("cna", {}).get("metrics", [])
        for m in metrics_list:
            for key in ["cvssV3_1", "cvssV3_0", "cvssV2"]:
                cvss_obj = m.get(key)
                if cvss_obj and "baseScore" in cvss_obj:
                    score = cvss_obj["baseScore"]
                    severity = cvss_obj.get("baseSeverity", "")
                    break
            if score is not None:
                break

        with cvss_cache_lock:
            cvss_cache[cve_id] = {"cvss": score, "severity": severity, "ts": now}

        return score, severity
    except Exception:
        return None, None


def _save_cvss_batch_to_db():
    """Persist the in-memory CVSS cache to DB (called after enrichment)."""
    try:
        with cvss_cache_lock:
            items = [{"cve_id": k, "cvss": v.get("cvss"), "severity": v.get("severity")}
                     for k, v in cvss_cache.items()]
        if items:
            db.save_cvss_cache(items)
    except Exception:
        pass


def fetch_cves_from_kev(kev_items):
    def _lookup(item):
        cve_id = item.get("cveID") or ""
        cvss_score, severity = fetch_cvss_for_cve(cve_id)
        return {
            "cve_id": cve_id,
            "vendor": item.get("vendorProject") or "",
            "product": item.get("product") or "",
            "vulnerability": item.get("vulnerabilityName") or "",
            "date_added": item.get("dateAdded") or "",
            "due_date": item.get("dueDate") or "",
            "cvss": round(float(cvss_score), 1) if cvss_score is not None else None,
            "severity": (severity or "UNKNOWN").upper(),
        }

    results = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_lookup, item): item for item in kev_items}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception:
                item = futures[future]
                results.append({
                    "cve_id": item.get("cveID") or "",
                    "vendor": item.get("vendorProject") or "",
                    "product": item.get("product") or "",
                    "vulnerability": item.get("vulnerabilityName") or "",
                    "date_added": item.get("dateAdded") or "",
                    "due_date": item.get("dueDate") or "",
                    "cvss": None,
                    "severity": "UNKNOWN",
                })
    results.sort(key=lambda x: x.get("date_added") or "", reverse=True)
    return results


def fetch_phishing():
    try:
        resp = _safe_get(PHISHSTATS_URL, timeout=12)
        if resp is not None and resp.status_code == 200:
            data = resp.json()
            records = data if isinstance(data, list) else (data.get("data", []) or [])
            results = []
            for item in records:
                if not isinstance(item, dict):
                    continue
                results.append({
                    "url": (item.get("url") or "")[:120],
                    "ip": item.get("ip") or "",
                    "country": item.get("countryname") or item.get("countrycode") or "",
                    "first_seen": item.get("date") or "",
                    "target": item.get("title") or "",
                })
            if results:
                with cache_lock:
                    source_status["phishing"]["online"] = True
                    source_status["phishing"]["count"] = len(results)
                    source_status["phishing"]["status"] = f"ONLINE (PhishStats: {len(results)}"
                return results
    except Exception:
        pass

    try:
        resp = _safe_get(OPENPHISH_URL, timeout=12)
        if resp is None:
            return dashboard_cache.get("phishing_domains", [])
        urls = [line.strip() for line in resp.text.strip().split("\n") if line.strip()]
        results = []
        for url in urls[:40]:
            try:
                parsed = urllib.parse.urlparse(url)
                host = parsed.hostname or "unknown"
            except Exception:
                host = "unknown"
            results.append({
                "url": url[:120],
                "ip": "",
                "country": "",
                "first_seen": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "target": host,
            })
        with cache_lock:
            source_status["phishing"]["online"] = True
            source_status["phishing"]["count"] = len(results)
            source_status["phishing"]["status"] = f"ONLINE (OpenPhish fallback: {len(results)})"
        return results
    except Exception:
        return dashboard_cache.get("phishing_domains", [])


def aggregate_phishing_domains(phishing_items):
    domain_counts = {}
    for item in phishing_items:
        url = item.get("url") or ""
        country = item.get("country") or ""
        try:
            parsed = urllib.parse.urlparse(url)
            host = parsed.hostname or "unknown"
        except Exception:
            host = "unknown"
        if host not in domain_counts:
            domain_counts[host] = {"domain": host, "hits": 0, "country": country, "sample_url": url[:80]}
        domain_counts[host]["hits"] += 1
    ranked = sorted(domain_counts.values(), key=lambda x: x["hits"], reverse=True)
    return ranked[:15]


OTX_LAST_FETCH = 0
OTX_MIN_INTERVAL = 300


def fetch_malware():
    global OTX_LAST_FETCH
    cached = dashboard_cache.get("malware", [])

    if time.time() - OTX_LAST_FETCH < OTX_MIN_INTERVAL and cached:
        with cache_lock:
            source_status["otx"]["online"] = True
            source_status["otx"]["count"] = len(cached)
            source_status["otx"]["status"] = f"ONLINE ({len(cached)} pulses, cached)"
        return cached

    for attempt in range(3):
        try:
            resp = _safe_get(OTX_URL, params={"limit": 15}, timeout=20, retries=2)
            if resp is not None and resp.status_code == 200:
                data = resp.json()
                pulses = data.get("results") or []
                results = []
                for pulse in pulses:
                    if not isinstance(pulse, dict):
                        continue
                    name = pulse.get("name") or "Unknown"
                    created = pulse.get("created") or ""
                    tlp = pulse.get("tlp") or "white"
                    tags = pulse.get("tags") or []
                    if isinstance(tags, list):
                        tags_str = ", ".join(tags[:5])
                    else:
                        tags_str = str(tags)[:60]
                    results.append({
                        "name": name[:100],
                        "tags": tags_str,
                        "tag_list": tags if isinstance(tags, list) else [],
                        "tlp": tlp.upper() if isinstance(tlp, str) else "WHITE",
                        "date": created[:10] if isinstance(created, str) else "",
                    })
                if results:
                    OTX_LAST_FETCH = time.time()
                    with cache_lock:
                        source_status["otx"]["online"] = True
                        source_status["otx"]["count"] = len(results)
                        source_status["otx"]["status"] = f"ONLINE ({len(results)} pulses)"
                    return results
            elif resp is not None and resp.status_code == 429:
                logger.warning("OTX rate limited (429), attempt %d/3", attempt + 1)
                time.sleep(5 * (attempt + 1))
                continue
        except Exception as e:
            logger.warning("OTX fetch error (attempt %d/3): %s", attempt + 1, str(e)[:60])
            time.sleep(3)
            continue

    with cache_lock:
        source_status["otx"]["online"] = False
        source_status["otx"]["status"] = "OFFLINE (rate limited)" if cached else "OFFLINE"
    return cached


def categorize_otx_pulses(pulses):
    categories = {"Ransomware": [], "APT / Campaign": [], "Scam / Botnet": [], "Other": []}
    for pulse in pulses:
        text = (pulse.get("name", "") + " " + pulse.get("tags", "")).lower()
        if any(kw in text for kw in ["ransomware", "ransom", "lockbit", "blackcat", "play", "akira"]):
            categories["Ransomware"].append(pulse)
        elif any(kw in text for kw in ["apt", "nation-state", "state-sponsored", "campaign", "lazarus"]):
            categories["APT / Campaign"].append(pulse)
        elif any(kw in text for kw in ["scam", "botnet", "phishing", "fraud", "trojan", "malware"]):
            categories["Scam / Botnet"].append(pulse)
        else:
            categories["Other"].append(pulse)
    return {k: v for k, v in categories.items() if v}


def fetch_ransomware_live():
    """Fetch recent ransomware victims from Ransomware.live API."""
    try:
        resp = _safe_get(RANSOMWARE_LIVE_URL, timeout=15)
        if resp is not None and resp.status_code == 200:
            data = resp.json()
            records = data if isinstance(data, list) else (data.get("victims") or [])
            victims = []
            for v in records[:40]:
                if not isinstance(v, dict):
                    continue
                group = v.get("group_name") or v.get("group") or "Unknown"
                name = v.get("post_title") or v.get("victim_name") or v.get("title") or "Victim"
                site = v.get("website") or ""
                country = v.get("country") or ""
                sector = v.get("activity") or v.get("sector") or ""
                date = v.get("discovered") or v.get("published") or ""
                victims.append({
                    "group_name": group,
                    "victim_name": name,
                    "website": site,
                    "country": country,
                    "sector": sector,
                    "discovered_at": date[:10] if len(date) >= 10 else date,
                })
            if victims:
                with cache_lock:
                    source_status["ransomware_live"]["online"] = True
                    source_status["ransomware_live"]["count"] = len(victims)
                    source_status["ransomware_live"]["status"] = f"ONLINE ({len(victims)} victims)"
                db.upsert_ransomware_victims(victims)
                return victims
    except Exception as e:
        logger.warning("Ransomware.live fetch error: %s", str(e)[:60])
    with cache_lock:
        source_status["ransomware_live"]["online"] = False
        source_status["ransomware_live"]["status"] = "OFFLINE"
    return db.load_ransomware_victims(50)


def fetch_threatfox_iocs():
    """Fetch recent malware payload URLs and IOCs from URLhaus/OpenPhish feeds."""
    try:
        resp = _safe_get("https://urlhaus-api.abuse.ch/v1/urls/recent/", timeout=10)
        if resp is not None and resp.status_code == 200:
            data = resp.json()
            if data.get("query_status") == "ok":
                items = data.get("urls") or []
                iocs = []
                for item in items[:40]:
                    iocs.append({
                        "ioc_type": "url",
                        "ioc_value": (item.get("url") or "")[:120],
                        "threat_type": item.get("threat") or "malware_download",
                        "malware_family": ", ".join(item.get("tags") or []) or "Malware Payload",
                        "confidence_level": 100,
                        "reporter": item.get("reporter") or "URLhaus",
                        "first_seen": (item.get("date_added") or "")[:10],
                    })
                if iocs:
                    with cache_lock:
                        source_status["threatfox"]["online"] = True
                        source_status["threatfox"]["count"] = len(iocs)
                        source_status["threatfox"]["status"] = f"ONLINE (URLhaus: {len(iocs)} IOCs)"
                    db.upsert_threatfox_iocs(iocs)
                    return iocs
    except Exception:
        pass

    # OpenPhish / PhishStats Fallback
    try:
        resp = _safe_get(OPENPHISH_URL, timeout=10)
        if resp is not None and resp.status_code == 200:
            urls = [line.strip() for line in resp.text.strip().split("\n") if line.strip()]
            iocs = []
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            for url in urls[:30]:
                iocs.append({
                    "ioc_type": "url",
                    "ioc_value": url[:120],
                    "threat_type": "phishing",
                    "malware_family": "Phishing Payload",
                    "confidence_level": 90,
                    "reporter": "OpenPhish",
                    "first_seen": today,
                })
            if iocs:
                with cache_lock:
                    source_status["threatfox"]["online"] = True
                    source_status["threatfox"]["count"] = len(iocs)
                    source_status["threatfox"]["status"] = f"ONLINE (OpenPhish feed: {len(iocs)} IOCs)"
                db.upsert_threatfox_iocs(iocs)
                return iocs
    except Exception:
        pass

    with cache_lock:
        source_status["threatfox"]["online"] = False
        source_status["threatfox"]["status"] = "OFFLINE"
    return db.load_threatfox_iocs(50)


def fetch_epss_scores(cve_items):
    """Fetch EPSS scores from FIRST.org API for a list of KEV/CVE items."""
    if not cve_items:
        return {}
    cve_ids = [item.get("cve_id") for item in cve_items if item.get("cve_id")]
    if not cve_ids:
        return {}
    cve_str = ",".join(cve_ids[:30])
    try:
        resp = _safe_get(f"{EPSS_API_URL}?cve={cve_str}", timeout=12)
        if resp is not None and resp.status_code == 200:
            data = resp.json()
            epss_data = {}
            for row in data.get("data") or []:
                cve = row.get("cve")
                score = float(row.get("epss", 0))
                perc = float(row.get("percentile", 0))
                epss_data[cve] = {"epss": round(score * 100, 2), "percentile": round(perc * 100, 1)}
            db.save_epss_cache(epss_data)
            return epss_data
    except Exception:
        pass
    return db.load_epss_cache()


def correlate_threat_actors(news_items, otx_pulses):
    """Correlate news and OTX threat pulses with known APT threat actors."""
    correlated = []
    for group in APT_GROUPS:
        keywords = [group["name"].lower()] + [a.lower() for a in group["aliases"]]
        matching_headlines = []
        mention_count = 0
        for n in news_items:
            t = f"{n.get('title', '')} {n.get('description', '')}".lower()
            if any(kw in t for kw in keywords):
                mention_count += 1
                if len(matching_headlines) < 2:
                    matching_headlines.append(n.get("title"))

        for p in otx_pulses:
            t = f"{p.get('name', '')} {p.get('tags', '')}".lower()
            if any(kw in t for kw in keywords):
                mention_count += 1

        correlated.append({
            **group,
            "mention_count": mention_count,
            "status": "ACTIVE" if mention_count > 0 else "MONITORING",
            "recent_headlines": matching_headlines,
        })
    correlated.sort(key=lambda x: x["mention_count"], reverse=True)
    return correlated


def aggregate_geo_events(news_items, phishing_items, ransomware_victims, kev_cves):
    """Aggregate global security event counts by country code/name for D3 World Map."""
    country_counts = Counter()

    for p in phishing_items:
        c = (p.get("country") or "").strip()
        if c and len(c) <= 30:
            country_counts[c] += 1

    for r in ransomware_victims:
        c = (r.get("country") or "").strip()
        if c and len(c) <= 30:
            country_counts[c] += 2

    geo_keywords = {
        "United States": ["us", "usa", "united states"],
        "United Arab Emirates": ["uae", "dubai", "abu dhabi", "united arab emirates"],
        "Saudi Arabia": ["saudi", "saudi arabia", "riyadh"],
        "United Kingdom": ["uk", "united kingdom", "britain", "london"],
        "Germany": ["germany", "berlin"],
        "France": ["france", "paris"],
        "Israel": ["israel", "tel aviv"],
        "Iran": ["iran", "tehran"],
        "Russia": ["russia", "moscow"],
        "Ukraine": ["ukraine", "kyiv"],
        "China": ["china", "beijing"],
        "India": ["india", "delhi", "mumbai"],
        "Japan": ["japan", "tokyo"],
        "South Korea": ["south korea", "seoul"],
        "Australia": ["australia", "sydney"],
        "Canada": ["canada", "toronto"],
        "Qatar": ["qatar", "doha"],
        "Kuwait": ["kuwait"],
        "Oman": ["oman", "muscat"],
        "Bahrain": ["bahrain"]
    }

    for item in news_items:
        text = f"{item.get('title', '')} {item.get('description', '')}".lower()
        for country_std, kws in geo_keywords.items():
            if any(re.search(r'\b' + re.escape(kw) + r'\b', text) for kw in kws):
                country_counts[country_std] += 1

    top_geo = [{"country": country, "count": count} for country, count in country_counts.most_common(25)]
    return top_geo



def fetch_news():
    rss_map = {
        "rss_thn": ("THN", "The Hacker News", "https://feeds.feedburner.com/TheHackersNews"),
        "rss_bleeping": ("BLEEPING_COMPUTER", "BleepingComputer", "https://www.bleepingcomputer.com/feed/"),
        "rss_darkreading": ("DARK_READING", "Dark Reading", "https://www.darkreading.com/rss.xml"),
        "rss_securityweek": ("SECURITY_WEEK", "SecurityWeek", "https://www.securityweek.com/feed/"),
        "rss_cisa": ("CISA_GOV", "CISA", "https://www.cisa.gov/cybersecurity-advisories/all.xml"),
        "rss_sans": ("SANS_ISC", "SANS ISC", "https://isc.sans.edu/rssfeed_full.xml"),
        "rss_cisa_ics": ("CISA_ICS", "CISA ICS", "https://www.cisa.gov/cybersecurity-advisories/ics-advisories.xml"),
        "rss_securityweek_ics": ("SECURITYWEEK_ICS", "SecurityWeek ICS/OT", "https://www.securityweek.com/category/ics-ot/feed/"),
    }

    def _fetch_one(key, source_badge, source_name, url):
        items = []
        try:
            resp = None
            try:
                r = requests.get(url, timeout=12, headers={"User-Agent": BROWSER_UA})
                if r.status_code == 403:
                    r = requests.get(url, timeout=12, headers={"User-Agent": MOBILE_UA})
                r.raise_for_status()
                resp = feedparser.parse(r.content)
            except Exception:
                resp = feedparser.parse(url)

            count = len(resp.entries)
            with cache_lock:
                source_status[key]["online"] = count > 0
                source_status[key]["count"] = count
                source_status[key]["status"] = f"ONLINE ({count} articles)"

            for entry in resp.entries[:12]:
                title = entry.get("title") or "No Title"
                link = entry.get("link") or "#"
                published = entry.get("published") or entry.get("updated") or ""
                description = entry.get("summary") or entry.get("description") or ""
                if description:
                    desc_text = BeautifulSoup(description, "html.parser").get_text()[:300]
                else:
                    desc_text = ""
                combined = f"{title} {desc_text}".lower()
                is_regional = False
                matched = []
                for kw in GCC_REGIONAL_KEYWORDS:
                    if kw.lower() in combined:
                        is_regional = True
                        matched.append(kw)

                pub_date = ""
                if published:
                    try:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(published)
                        pub_date = dt.isoformat()
                    except Exception:
                        pub_date = published

                item_vectors = compute_item_attack_vectors(f"{title} {desc_text}")

                items.append({
                    "title": title,
                    "link": link,
                    "source": source_name,
                    "sourceBadge": source_badge,
                    "published": published,
                    "pubDate": pub_date,
                    "description": desc_text,
                    "is_regional": is_regional,
                    "matched_keywords": matched,
                    "attack_vectors": item_vectors,
                })
        except Exception as e:
            with cache_lock:
                source_status[key]["status"] = f"ERROR: {str(e)[:40]}"
        return items

    all_news = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(_fetch_one, key, badge, name, url): key
            for key, (badge, name, url) in rss_map.items()
        }
        for future in as_completed(futures):
            try:
                all_news.extend(future.result())
            except Exception:
                pass

    seen_titles = set()
    deduped = []
    for item in all_news:
        norm = re.sub(r"[^a-z0-9 ]", "", item["title"].lower()).strip()
        short = norm[:60]
        if short not in seen_titles:
            seen_titles.add(short)
            deduped.append(item)

    filtered = []
    for item in deduped:
        title_lower = item["title"].lower()
        desc_lower = (item.get("description") or "").lower()
        combined = f"{title_lower} {desc_lower}"

        excluded = False
        for ex in NEWS_TITLE_EXCLUSIONS:
            if ex in title_lower:
                excluded = True
                break

        if excluded:
            continue

        has_relevant = False
        for kw in NEWS_TITLE_REQUIRED_KEYWORDS:
            if kw in combined:
                has_relevant = True
                break

        if has_relevant or item.get("sourceBadge") == "CISA_GOV":
            filtered.append(item)

    filtered.sort(key=lambda x: x.get("pubDate") or "", reverse=True)
    return filtered[:30]


WORD_CLOUD_EXCLUSIONS = {
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
    "mon", "tue", "wed", "thu", "fri", "sat", "sun",
    "ist", "nd", "rd", "th",
    # Source boilerplate from SecurityWeek / BleepingComputer footers.
    "post", "appeared", "securityweek", "security week",
    "bleepingcomputer", "bleeping computer",
    # Generic news language — not useful for identifying campaigns, actors,
    # products, or affected technologies.  NOTE: security-relevant words
    # like "attack", "flaw", "critical", "exploit", "vulnerability" are
    # intentionally kept so they surface in the analyst word cloud.
    "researchers", "researcher",
    "issue", "issues", "update", "updates", "patch", "patches",
    "released", "release", "latest", "reveals", "reveal",
    "targets", "targeted", "affects", "affected",
    "system", "systems", "company", "companies", "organization",
    "organizations", "industry", "industries", "users", "customer",
    "customers", "online", "service", "services", "software", "platform",
    # Overly generic severity/score language from CVSS descriptions.
    "severity", "base", "score",
    "successful", "potentially", "successfully", "actively",
    "incident", "incidents", "event", "events",
}

KNOWN_PHRASES = [
    "hugging face", "data breach", "zero day", "supply chain",
    "ransomware attack", "cyber attack", "code injection",
    "remote code", "privilege escalation", "denial of service",
    "social engineering", "infostealer malware", "credential theft",
    "back door", "fire wall", "zero trust",
    "sonicwall", "palo alto", "fortinet", "checkpoint",
    "access control", "denial-of-service", "cross-site scripting",
    "sql injection", "buffer overflow", "man in the middle",
    "endpoint detection", "intrusion detection", "threat intelligence",
    "data exfiltration", "remote access", "lateral movement",
    "malware strain", "zero-day exploit", "supply-chain attack",
    "brute force", "memory corruption", "code execution",
    "security flaw", "active exploit", "in-the-wild",
    "security update", "security patch", "critical flaw",
]

# Terms that are security-significant even when a source uses all lowercase.
# This is intentionally compact: unfamiliar recurring names are also retained
# by the entity rules below instead of requiring a constantly-maintained list.
SECURITY_TERMS = {
    "ransomware", "malware", "phishing", "backdoor", "exploit", "zero-day",
    "zero day", "vulnerability", "breach", "exfiltration", "botnet", "trojan",
    "rootkit", "infostealer", "keylogger", "spyware", "rce", "ddos", "apt",
    "ics", "scada", "plc", "oauth", "mfa", "cve", "lockbit", "blackcat",
    "ot", "hmi", "rtu", "dcs", "modbus", "dnp3", "ics-cert",
    "dragos", "claroty", "nozomi", "siemens", "schneider", "rockwell",
    # Security vendors & products
    "sonicwall", "fortinet", "checkpoint", "barracuda", "crowdstrike",
    "sentinelone", "paloalto", "palo alto", "mcafee", "symantec",
    "trendmicro", "kaspersky", "fireeye", "mandiant", "recordedfuture",
    "abuseipdb", "virustotal", "shodan", "censys",
    # Frameworks, orgs, standards
    "cisa", "mitre", "att&ck", "owasp", "nvd", "nist", "iso27001",
    "gdpr", "hipaa", "sox", "pci-dss",
    # Attack types
    "xss", "csrf", "sqli", "ssrf", "xxe", "ssti", "lfi", "rfi",
    "rce", "lpe", "uaf", "oob", "idor",
    "wiper", "loader", "dropper", "stealer", "grabber", "rat",
    "c2", "c&c", "ioc", "iocs", "ttps", "mitre",
    "fileless", "living-off-the-land", "lolbin",
    "spearphishing", "whaling", "smishing", "vishing",
    # Network / infra
    "firewall", "ids", "ips", "siem", "edr", "xdr", "soar", "zt",
    "vpn", "proxy", "dns", "tls", "ssl",
    # Action words that appear across many security articles
    "attack", "attackers", "attacks", "exploited", "exploitation",
    "hacked", "hackers", "hackers", "breached", "compromised",
    "vulnerability", "vulnerabilities", "flaw", "flaws",
    "malicious", "payload", "backdoor", "backdoors",
    "threat", "threats", "adversary", "adversaries",
    "compromise", "exfiltrate", "exfiltrated",
    # Compound terms often used as single tokens
    "sonicwall",
}


def _cloud_stop_words():
    """Combine shipped noise words with analyst-maintained stop words."""
    try:
        return STOP_WORDS | set(db.get_stop_words())
    except Exception:
        return STOP_WORDS


def _cloud_tokens(text):
    """Extract tokens preserving hyphenated/merged security compounds."""
    return re.findall(r"[A-Za-z][A-Za-z0-9]*(?:[-_][A-Za-z0-9]+)*|CVE-\d{4}-\d{4,}", text)


def _is_security_term(token):
    """Return True if token is a recognized security term (case-insensitive)."""
    lower = token.lower().strip(string.punctuation)
    return lower in SECURITY_TERMS


SECURITY_BOOST = 3


def _display_name(names):
    """Prefer the most frequent original spelling, preserving brands/CVEs."""
    return Counter(names).most_common(1)[0][0]


def compute_word_cloud(news_items):
    stop_words = _cloud_stop_words()
    candidates = {}

    def record(raw, article_id, kind, mentions=1, boost=0):
        normalized = raw.lower().strip(string.punctuation)
        if (len(normalized) < 3 or normalized in stop_words or
                normalized in WORD_CLOUD_EXCLUSIONS):
            return
        candidate = candidates.setdefault(normalized, {
            "names": [], "articles": set(), "mentions": 0, "kind": kind,
            "boost": boost,
        })
        candidate["names"].append(raw.strip())
        candidate["articles"].add(article_id)
        candidate["mentions"] += mentions
        candidate["boost"] = max(candidate["boost"], boost)

    for index, item in enumerate(news_items):
        article_id = item.get("id", index)
        title = item.get("title") or ""
        description = item.get("description") or ""
        title_lower = title.lower()
        full_text = f"{title} {description}"

        # Preserve meaningful multi-word concepts and product/vendor names.
        for phrase in KNOWN_PHRASES:
            if phrase in title_lower or phrase in description.lower():
                record(phrase, article_id, "threat", boost=3)
        current_year = datetime.now().year
        for cve in re.findall(r"\bCVE-(\d{4})-(\d{4,})\b", full_text, re.I):
            cve_year = int(cve[0])
            cve_id = f"CVE-{cve[0]}-{cve[1]}".upper()
            # Only include CVEs from the current year — stale references in
            # advisory footers add noise without actionable value.
            if cve_year >= current_year:
                record(cve_id, article_id, "CVE", boost=6)
        for match in re.finditer(r"\b(?:[A-Z][A-Za-z0-9&.-]+\s+){1,2}[A-Z][A-Za-z0-9&.-]+\b", title):
            phrase = match.group(0)
            if not any(part.lower() in stop_words for part in phrase.split()):
                record(phrase, article_id, "named entity", boost=4)

        # Extract tokens from both title AND description so threats mentioned
        # only in body text still surface in the cloud.
        for token in _cloud_tokens(full_text):
            lower = token.lower()
            is_sec = _is_security_term(token)
            is_distinctive = (token != token.lower() or any(ch.isdigit() for ch in token)
                              or "-" in token or is_sec)
            kind = "security term" if is_sec else "entity"
            # Security terms get a higher boost so they survive the ranking
            boost = (SECURITY_BOOST + 2) if is_sec else (SECURITY_BOOST if is_distinctive else 0)
            record(token, article_id, kind, boost=boost)

    ranked = []
    security_ranked = []
    specific_ranked = []
    for data in candidates.values():
        article_count = len(data["articles"])
        if article_count < 2 and data["boost"] < 3:
            continue
        # --- Scoring: boost + mentions weighted more than article count ---
        # For security terms, an indicator that appears prominently in 3
        # articles is more actionable than a generic word sprinkled across 11.
        # Use effective_count (capped at 5) but weight boost and mentions
        # more heavily for the security buckets.
        effective_count = min(article_count, 5)
        base = effective_count * 10 + min(data["mentions"], 6) + data["boost"]
        entry = {
            "text": _display_name(data["names"]), "weight": article_count,
            "mentions": data["mentions"], "type": data["kind"], "score": base,
        }
        if data["kind"] == "CVE":
            # CVEs are always high-value — strong multiplier.
            entry["score"] = int(base * 2.0)
            specific_ranked.append(entry)
        elif data["kind"] == "threat":
            # Multi-word phrases like "data breach", "code execution".
            entry["score"] = int(base * 1.7)
            specific_ranked.append(entry)
        elif data["kind"] == "security term":
            text = _display_name(data["names"])
            is_specific = (
                text.startswith("CVE-")
                or "-" in text
                or text[0].isupper()
                or " " in text
            )
            if is_specific:
                # Capitalized/vendor names/hyphens: emphasize boost+mentions.
                entry["score"] = int(base * 1.5)
                specific_ranked.append(entry)
            else:
                # Generic lowercase ("vulnerability", "malware"): mild boost.
                entry["score"] = int(base * 1.05)
                security_ranked.append(entry)
        else:
            ranked.append(entry)
            continue

    ranked.sort(key=lambda w: (-w["score"], -w["weight"], w["text"].lower()))
    ranked = ranked[:10]
    specific_ranked.sort(key=lambda w: (-w["score"], -w["weight"], w["text"].lower()))
    security_ranked.sort(key=lambda w: (-w["score"], -w["weight"], w["text"].lower()))
    combined = specific_ranked + security_ranked + ranked

    if not combined:
        return []
    max_score = combined[0]["score"]
    for word in combined:
        word["normalized"] = round(word["score"] / max_score, 2)
    return combined[:25]


def refresh_dashboard_word_cloud():
    """Rebuild only the cloud after an analyst changes the stop-word list."""
    todays_news = db.get_todays_news()
    with cache_lock:
        dashboard_cache["word_cloud"] = compute_word_cloud(todays_news)


ATTACK_VECTOR_KEYWORDS = {
    "Ransomware": ["ransomware", "ransom", "extortion", "encryptor", "lockbit", "cl0p", "blackcat", "akira", "revil", "alphv"],
    "Phishing": ["phishing", "phish", "infostealer", "credential harvest", "social engineering", "credential theft"],
    "Zero-Day": ["zero-day", "zero day", "0-day", "exploit", "vulnerability", "kev", "cve"],
    "Supply Chain": ["supply chain", "npm", "pypi", "typosquatting", "dependency confusion", "backdoor"],
    "DDoS": ["ddos", "denial of service"],
    "APT": ["apt", "state-sponsored", "nation-state", "lazarus", "apt28", "apt29", "cozy bear", "fancy bear"],
    "Data Breach": ["data breach", "data leak", "breach", "exfiltrat", "data stolen"],
    "AI Threat": ["artificial intelligence", "llm", "claude", "chatgpt", "openai", "cursor", "generative ai", "machine learning", "deepfake"],
    "Malware": ["malware", "trojan", "worm", "virus", "rat", "remote access", "keylogger", "spyware", "adware", "rootkit", "fileless"],
    "Cloud": ["cloud", "aws", "azure", "okta", "entra", "gcp", "s3 bucket"],
    "Identity": ["identity", "authentication", "mfa", "oauth", "sso", "credential stuffing"],
    "Cryptojacking": ["cryptojack", "cryptomin", "coin miner", "mining malware", "xmrig"],
    "OT/ICS": [
        "ot security", "ics security", "ot network", "ot cyber",
        "operational technology", "industrial control system", "industrial control",
        "scada", "ics", "plc", "dcs", "hmi", "rtu", "historian",
        "control system", "control system security",
        "siemens", "schneider electric", "rockwell automation", "rockwell",
        "abb", "mitsubishi electric", "mitsubishi", "honeywell",
        "yokogawa", "emerson", "omron", "phoenix contact", "advantech",
        "ge electric", "hitachi energy", "fanuc", "beckhoff", "wago",
        "codesys", "allen-bradley", "modicon", "siemens simatic",
        "modbus", "dnp3", "opc ua", "opc", "bacnet", "profinet",
        "ethernet/ip", "ethercat", "iec 61850", "iec 62443",
        "power grid", "water treatment", "wastewater", "oil and gas",
        "pipeline", "nuclear", "manufacturing", "factory automation",
        "building automation", "critical infrastructure",
        "dragos", "claroty", "nozomi networks", "txone", "armis",
        "ics advisory", "ics vulnerability", "ot vulnerability",
        "plc exploit", "plc attack", "engineering workstation",
        "field device", "smart grid", "substation", "scada system",
    ],
    "Mobile": ["mobile", "android", "ios", "app store", "play store", "mobile malware"],
    "Web App": ["web app", "sql injection", "xss", "cross-site", "csrf", "web shell", "rce", "remote code execution"],
    "Insider Threat": ["insider threat", "insider risk", "internal threat", "data sabotage", "malicious insider"],
}


def _count_keyword_matches(text, patterns):
    count = 0
    for pattern in patterns:
        if " " in pattern:
            count += len(re.findall(re.escape(pattern), text))
        else:
            count += len(re.findall(r'\b' + re.escape(pattern) + r'\b', text))
    return count


def _get_live_vector_keywords():
    """Read current vector keywords from the DB (authoritative source)."""
    try:
        db_vectors = db.get_all_vector_keywords()
        if db_vectors:
            return db_vectors
    except Exception:
        pass
    return ATTACK_VECTOR_KEYWORDS


def compute_item_attack_vectors(text):
    text = text.lower()
    matched = []
    for vector, patterns in _get_live_vector_keywords().items():
        if _count_keyword_matches(text, patterns) > 0:
            matched.append(vector)
    return matched


def compute_attack_vectors(news_items):
    all_text = " ".join(
        f"{item.get('title', '')} {item.get('description', '')}"
        for item in news_items
    ).lower()
    counts = {}
    for vector, patterns in _get_live_vector_keywords().items():
        counts[vector] = _count_keyword_matches(all_text, patterns)
    total = sum(counts.values()) or 1
    return {v: round((c / total) * 100, 1) for v, c in counts.items()}


def count_regional_mentions(news_items, phishing_domains, kev_items):
    count = sum(1 for item in news_items if item.get("is_regional"))
    for item in phishing_domains:
        text = " ".join([item.get("country") or "", item.get("domain") or "", item.get("sample_url") or ""]).lower()
        if any(kw in text for kw in ["uae", "dubai", "abu dhabi", "gcc", "middle east"]):
            count += 1
    for item in kev_items:
        text = " ".join([item.get("vendor") or "", item.get("vulnerability") or ""]).lower()
        if any(kw in text for kw in ["uae", "dubai", "abu dhabi", "gcc", "middle east"]):
            count += 1
    return count


TACTIC_BY_VECTOR = {
    "Phishing": "Initial Access", "Web App": "Initial Access",
    "Supply Chain": "Initial Access", "Malware": "Execution",
    "Ransomware": "Impact", "DDoS": "Impact", "Identity": "Credential Access",
    "Insider Threat": "Credential Access", "Cloud": "Persistence",
    "OT/ICS": "Impact", "Mobile": "Initial Access", "AI Threat": "Execution",
    "Cryptojacking": "Impact", "APT": "Persistence", "Zero-Day": "Privilege Escalation",
}


def _collect(name, fetcher):
    """Collect a source only when due, exposing cache freshness to the UI."""
    state = collector_state[name]
    now = time.time()
    if state["last_run"] and now - state["last_run"] < COLLECTOR_INTERVALS[name]:
        return collector_results[name], False
    started = time.time()
    try:
        result = fetcher() or []
        collector_results[name] = result
        source_keys = {
            "kev": ["cisa_kev"], "phishing": ["phishing"], "otx": ["otx"],
            "news": ["rss_thn", "rss_bleeping", "rss_darkreading", "rss_securityweek", "rss_cisa", "rss_sans"],
            "ransomware": ["ransomware_live"], "threatfox": ["threatfox"],
        }[name]
        upstream_online = any(source_status.get(key, {}).get("online") for key in source_keys)
        state.update({
            "last_run": now,
            "last_success": datetime.now(timezone.utc).isoformat() if upstream_online else state["last_success"],
            "latency_ms": round((time.time() - started) * 1000),
            "status": "ONLINE" if upstream_online else "DEGRADED",
            "error": "" if upstream_online else "No upstream feed confirmed healthy", "count": len(result),
        })
        return result, True
    except Exception as exc:
        state.update({"last_run": now, "status": "DEGRADED", "error": str(exc)[:80]})
        return collector_results[name], False


def compute_vulnerability_posture(kev_items):
    buckets = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    overdue = due_7d = 0
    today = datetime.now(timezone.utc).date()
    for item in kev_items:
        score = float(item.get("cvss") or 0)
        bucket = "critical" if score >= 9 else "high" if score >= 7 else "medium" if score >= 4 else "low"
        buckets[bucket] += 1
        try:
            due = datetime.strptime(item.get("due_date") or "", "%Y-%m-%d").date()
            if due < today:
                overdue += 1
            elif (due - today).days <= 7:
                due_7d += 1
        except ValueError:
            pass
    return {"total": len(kev_items), "severity": buckets, "overdue": overdue, "due_7d": due_7d}


def compute_regional_exposure(news_items, phishing_items):
    countries = Counter(item.get("country") for item in phishing_items if item.get("country"))
    regional_news = [item for item in news_items if item.get("is_regional")]
    return {
        "regional_news": len(regional_news),
        "regional_headlines": [item.get("title", "") for item in regional_news[:3]],
        # This is hosting-country metadata provided by the feed, not attribution.
        "hosting_countries": [{"country": country, "count": count} for country, count in countries.most_common(4)],
    }


def compute_ioc_queue(phishing_items):
    queue, seen = [], set()
    for item in phishing_items:
        url = item.get("url") or ""
        try:
            domain = urllib.parse.urlparse(url).hostname or ""
        except Exception:
            domain = ""
        for kind, value in (("domain", domain), ("ip", item.get("ip") or ""), ("url", url)):
            key = f"{kind}:{value}"
            if value and key not in seen:
                seen.add(key)
                queue.append({"type": kind, "value": value[:160], "country": item.get("country") or "", "first_seen": item.get("first_seen") or "", "source": "PhishStats/OpenPhish"})
            if len(queue) >= 12:
                return queue
    return queue


def compute_attack_coverage(news_items):
    counts = Counter()
    for item in news_items:
        for vector in item.get("attack_vectors") or []:
            tactic = TACTIC_BY_VECTOR.get(vector)
            if tactic:
                counts[tactic] += 1
    order = ["Initial Access", "Execution", "Persistence", "Privilege Escalation", "Credential Access", "Impact"]
    return [{"tactic": tactic, "count": counts[tactic]} for tactic in order]


def get_feed_health():
    now = datetime.now(timezone.utc)
    result = {}
    for name, state in collector_state.items():
        age_seconds = None
        if state["last_success"]:
            age_seconds = round((now - datetime.fromisoformat(state["last_success"])).total_seconds())
        result[name] = {**state, "age_seconds": age_seconds, "interval_seconds": COLLECTOR_INTERVALS[name]}
    return result


def refresh_data():
    global kev_display_cache
    kev_raw, kev_refreshed = _collect("kev", fetch_kev)
    if kev_refreshed or not kev_display_cache:
        kev_display_cache = fetch_cves_from_kev(kev_raw)
    kev_cves = kev_display_cache

    # Enrich KEV with EPSS scores
    epss_scores = fetch_epss_scores(kev_cves)
    for item in kev_cves:
        cve = item.get("cve_id")
        if cve in epss_scores:
            item["epss"] = epss_scores[cve]["epss"]
            item["epss_percentile"] = epss_scores[cve]["percentile"]

    phishing_raw, phishing_refreshed = _collect("phishing", fetch_phishing)
    phishing_domains = aggregate_phishing_domains(phishing_raw)
    malware, otx_refreshed = _collect("otx", fetch_malware)
    malware_categorized = categorize_otx_pulses(malware)
    news, news_refreshed = _collect("news", fetch_news)

    # Collect ransomware and ThreatFox IOCs
    ransomware_victims, rw_refreshed = _collect("ransomware", fetch_ransomware_live)
    threatfox_iocs, tf_refreshed = _collect("threatfox", fetch_threatfox_iocs)

    # Derived insights
    threat_actors = correlate_threat_actors(news, malware)
    geo_events = aggregate_geo_events(news, phishing_raw, ransomware_victims, kev_cves)
    regional_count = count_regional_mentions(news, phishing_domains, kev_cves)
    posture = compute_vulnerability_posture(kev_cves)
    regional_exposure = compute_regional_exposure(news, phishing_raw)
    ioc_queue = compute_ioc_queue(phishing_raw)
    attack_coverage = compute_attack_coverage(news)

    if news_refreshed:
        try:
            db.insert_news_batch(news)
        except Exception as e:
            logger.warning("News database update failed: %s", str(e)[:60])
    attack_vectors = db.get_vector_percentages_from_db()
    try:
        word_cloud = compute_word_cloud(db.get_todays_news())
    except Exception as e:
        logger.warning("Today's word cloud query failed: %s", str(e)[:60])
        word_cloud = []

    with cache_lock:
        dashboard_cache["kev"] = kev_cves
        dashboard_cache["phishing_domains"] = phishing_domains
        dashboard_cache["malware"] = malware
        dashboard_cache["malware_categorized"] = malware_categorized
        dashboard_cache["news"] = news
        dashboard_cache["word_cloud"] = word_cloud
        dashboard_cache["attack_vectors"] = attack_vectors
        dashboard_cache["regional_mention_count"] = regional_count
        dashboard_cache["last_updated"] = datetime.now(timezone.utc).isoformat()
        dashboard_cache["source_status"] = dict(source_status)
        dashboard_cache["open_alerts"] = len(kev_cves) + len(phishing_domains) + len(ransomware_victims)
        dashboard_cache["posture"] = posture
        dashboard_cache["regional_exposure"] = regional_exposure
        dashboard_cache["ioc_queue"] = ioc_queue
        dashboard_cache["attack_coverage"] = attack_coverage
        dashboard_cache["feed_health"] = get_feed_health()
        dashboard_cache["ransomware_victims"] = ransomware_victims
        dashboard_cache["threatfox_iocs"] = threatfox_iocs
        dashboard_cache["threat_actors"] = threat_actors
        dashboard_cache["geo_events"] = geo_events


    # Snapshot only after a real upstream collection; do not create a new
    # database record for every browser-cache refresh.
    if kev_refreshed or phishing_refreshed or otx_refreshed or news_refreshed:
      try:
        if kev_cves and (kev_refreshed or not db.load_kev()):
            db.save_kev(kev_cves)
        if kev_refreshed:
            _save_cvss_batch_to_db()
        db.snapshot_attack_vectors(attack_vectors)
        db.snapshot_word_cloud(word_cloud)
        db.upsert_phishing_domains(phishing_domains)
        db.snapshot_otx_pulses(malware, malware_categorized)
        db.snapshot_vulnerability_posture(posture)
        db.snapshot_feed_runs(get_feed_health())
        db.upsert_ioc_observations(ioc_queue)
        db.save_regional_exposure(regional_exposure)
        db.save_source_status(source_status)
        source_badges = {}
        for item in news:
            badge = item.get("sourceBadge", "UNKNOWN")
            source_badges[badge] = source_badges.get(badge, 0) + 1
        db.snapshot_source_counts(source_badges)
        with cache_lock:
            dashboard_cache["total_news_stored"] = db.get_total_news_count()
      except Exception as e:
        logger.warning("DB snapshot error: %s", str(e)[:60])

    logger.info(
        "Refresh: KEV=%d PhishDomains=%d OTX=%d News=%d Words=%d Regional=%d",
        len(kev_cves), len(phishing_domains), len(malware),
        len(news), len(word_cloud), regional_count,
    )


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)


def compute_word_graph(news_items):
    article_words = []
    word_freq = Counter()

    for item in news_items:
        title = (item.get("title") or "").lower()
        title = re.sub(r"[^\w\s\-]", " ", title)

        for phrase in KNOWN_PHRASES:
            if phrase in title:
                title = title.replace(phrase, phrase.replace(" ", "_"))

        words = title.split()
        unique = set()
        for w in words:
            w = w.strip(string.punctuation + string.digits).replace("_", " ")
            if len(w) < 3 or w in STOP_WORDS or w in WORD_CLOUD_EXCLUSIONS:
                continue
            if w not in unique:
                unique.add(w)
                word_freq[w] += 1
        article_words.append(unique)

    top_words = [w for w, c in word_freq.most_common(30) if c >= 2]
    if not top_words:
        return {"nodes": [], "edges": []}

    max_freq = max(word_freq.values())
    nodes = []
    for w in top_words:
        nodes.append({
            "id": w,
            "freq": word_freq[w],
            "size": round(0.3 + 0.7 * (word_freq[w] / max_freq), 2),
        })

    edge_counter = Counter()
    for unique in article_words:
        present = [w for w in top_words if w in unique]
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                pair = tuple(sorted([present[i], present[j]]))
                edge_counter[pair] += 1

    edges = []
    for (a, b), count in edge_counter.most_common(40):
        edges.append({"source": a, "target": b, "strength": round(count / max(1, len(news_items)), 2)})

    return {"nodes": nodes, "edges": edges}


@app.route("/api/word-graph")
def word_graph():
    with cache_lock:
        words = list(dashboard_cache.get("word_cloud", []))
    # Kept for compatible clients; it now returns the exact same scored words
    # used by the dashboard instead of a conflicting secondary tokenizer.
    return jsonify({"nodes": words, "edges": []})


@app.route("/api/dashboard-data")
def dashboard_data():
    with cache_lock:
        data = dict(dashboard_cache)
    return jsonify(data)


@app.route("/api/insights/posture")
def insight_posture():
    with cache_lock:
        return jsonify({
            "posture": dashboard_cache.get("posture", {}),
            "regional_exposure": dashboard_cache.get("regional_exposure", {}),
            "attack_coverage": dashboard_cache.get("attack_coverage", []),
            "feed_health": dashboard_cache.get("feed_health", {}),
        })


@app.route("/api/iocs")
def iocs():
    with cache_lock:
        queue = list(dashboard_cache.get("ioc_queue", []))
    ioc_type = request.args.get("type")
    if ioc_type:
        queue = [item for item in queue if item.get("type") == ioc_type]
    return jsonify({"items": queue, "count": len(queue)})


@app.route("/api/ransomware")
def api_ransomware():
    with cache_lock:
        victims = list(dashboard_cache.get("ransomware_victims", []))
    groups = Counter(v.get("group_name", "Unknown") for v in victims)
    sectors = Counter(v.get("sector", "Other") for v in victims if v.get("sector"))
    return jsonify({
        "victims": victims,
        "total": len(victims),
        "top_groups": [{"group": g, "count": c} for g, c in groups.most_common(10)],
        "top_sectors": [{"sector": s, "count": c} for s, c in sectors.most_common(8)],
    })


@app.route("/api/threat-actors")
def api_threat_actors():
    with cache_lock:
        actors = list(dashboard_cache.get("threat_actors", []))
    return jsonify({"actors": actors, "total": len(actors)})


@app.route("/api/geo-events")
def api_geo_events():
    with cache_lock:
        geo = list(dashboard_cache.get("geo_events", []))
    return jsonify({"events": geo})


@app.route("/api/export-iocs")
def export_iocs():
    fmt = request.args.get("format", "csv").lower()
    with cache_lock:
        iocs = list(dashboard_cache.get("ioc_queue", [])) + list(dashboard_cache.get("threatfox_iocs", []))

    if fmt == "json":
        return jsonify({"iocs": iocs, "exported_at": datetime.now(timezone.utc).isoformat()})

    # CSV format response
    lines = ["type,value,source,country,first_seen"]
    for item in iocs:
        itype = item.get("type") or item.get("ioc_type") or "unknown"
        ival = (item.get("value") or item.get("ioc_value") or "").replace(",", "")
        src = (item.get("source") or item.get("reporter") or "OSINT").replace(",", "")
        country = (item.get("country") or "").replace(",", "")
        seen = item.get("first_seen") or ""
        lines.append(f"{itype},{ival},{src},{country},{seen}")

    csv_data = "\n".join(lines)
    from flask import Response
    return Response(csv_data, mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=soc_iocs_export.csv"})



@app.route("/api/insights/trends")
def insight_trends():
    days = min(int(request.args.get("days", 7)), 90)
    vector_trend = db.get_vector_trend(days)
    word_trend = db.get_word_cloud_trend(days)
    source_trend = db.get_source_trend(days)
    return jsonify({
        "vector_trend": vector_trend,
        "word_trend": word_trend,
        "source_trend": source_trend,
        "days": days,
    })


@app.route("/api/insights/stats")
def insight_stats():
    total = db.get_total_news_count()
    top_kw = db.get_top_keywords(7, 15)
    vector_by_src = db.get_vector_distribution_by_source(7)
    phishing_hist = db.get_phishing_history(30)
    otx_hist = db.get_otx_history(7)
    return jsonify({
        "total_news_stored": total,
        "top_keywords_7d": top_kw,
        "vector_by_source": vector_by_src,
        "phishing_history": phishing_hist,
        "otx_history": otx_hist,
    })


@app.route("/api/articles")
def list_articles():
    search = request.args.get("search", "")
    source = request.args.get("source", "")
    vector = request.args.get("vector", "")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    result = db.get_articles_paginated(search, source, vector, page, per_page)
    return jsonify(result)


@app.route("/api/articles/<int:article_id>")
def get_article(article_id):
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM news WHERE id = ?", (article_id,)).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    article = dict(row)
    article["attack_vectors"] = db.get_article_vectors(article_id)
    return jsonify(article)


@app.route("/api/articles/<int:article_id>/vectors", methods=["PUT"])
def update_article_vectors(article_id):
    data = request.get_json(force=True)
    vectors = data.get("vectors", [])
    db.update_article_vectors(article_id, vectors)
    return jsonify({"ok": True, "vectors": vectors})


@app.route("/api/sources")
def list_sources():
    return jsonify(db.get_all_news_sources())


@app.route("/api/stop-words", methods=["GET"])
def get_stop_words():
    return jsonify(db.get_stop_words())


@app.route("/api/stop-words", methods=["POST"])
def add_stop_word():
    data = request.get_json(force=True)
    word = data.get("word", "")
    db.add_stop_word(word)
    refresh_dashboard_word_cloud()
    return jsonify({"ok": True})


@app.route("/api/stop-words/<word>", methods=["DELETE"])
def delete_stop_word(word):
    db.remove_stop_word(word)
    refresh_dashboard_word_cloud()
    return jsonify({"ok": True})


@app.route("/api/attack-vector-keywords", methods=["GET"])
def get_vector_keywords():
    return jsonify(db.get_all_vector_keywords())


@app.route("/api/attack-vector-keywords", methods=["POST"])
def add_vector_keyword():
    data = request.get_json(force=True)
    vector = data.get("vector", "")
    keywords = data.get("keywords", [])
    if not vector:
        return jsonify({"error": "vector required"}), 400
    db.update_vector_keywords(vector, keywords)
    # Re-tag all articles so the new vector is applied immediately.
    db.retag_all_articles(db.get_all_vector_keywords())
    return jsonify({"ok": True})


@app.route("/api/attack-vector-keywords/<vector>", methods=["PUT"])
def update_vector_keyword(vector):
    data = request.get_json(force=True)
    keywords = data.get("keywords", [])
    db.update_vector_keywords(vector, keywords)
    # Re-tag all articles so updated keywords take effect immediately.
    db.retag_all_articles(db.get_all_vector_keywords())
    return jsonify({"ok": True})


@app.route("/api/attack-vector-keywords/<vector>", methods=["DELETE"])
def delete_vector_keyword(vector):
    conn = db.get_conn()
    conn.execute("DELETE FROM vector_keywords WHERE vector = ?", (vector,))
    conn.execute("DELETE FROM news_vectors WHERE vector = ?", (vector,))
    conn.commit()
    # Re-tag all articles so the deleted vector is removed from all articles.
    db.retag_all_articles(db.get_all_vector_keywords())
    return jsonify({"ok": True})


@app.route("/api/health")
def health():
    return jsonify({
        "status": "healthy",
        "sources": source_status,
        "feed_health": get_feed_health(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "news_in_db": db.get_total_news_count(),
    })


@app.route("/api/diagnostics")
def diagnostics():
    diag = {}

    # --- System Health ---
    uptime_sec = round(time.time() - APP_START_TIME, 1)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    ram_mb = round(usage.ru_maxrss / 1024, 1)
    try:
        load_1, load_5, load_15 = os.getloadavg()
    except (OSError, AttributeError):
        load_1 = load_5 = load_15 = 0.0

    active_threads = threading.active_count()
    gunicorn_workers = os.environ.get("WEB_CONCURRENCY", "1")

    diag["system"] = {
        "status": "ok",
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "hostname": platform.node(),
        "pid": os.getpid(),
        "uptime_seconds": uptime_sec,
        "uptime_human": _format_uptime(uptime_sec),
        "ram_mb": ram_mb,
        "cpu_load_1m": round(load_1, 2),
        "cpu_load_5m": round(load_5, 2),
        "cpu_load_15m": round(load_15, 2),
        "active_threads": active_threads,
        "gunicorn_workers": gunicorn_workers,
        "gunicorn_config": f"{gunicorn_workers} workers, {os.environ.get('THREADS', '4')} threads",
    }

    # --- Database Health ---
    db_info = _check_database_health()
    diag["database"] = db_info

    # --- External Connectivity ---
    connectivity = _check_external_connectivity()
    diag["connectivity"] = connectivity

    # --- Scheduler / Collector Status ---
    diag["scheduler"] = _get_scheduler_status()

    # --- Feed Source Status ---
    diag["sources"] = {}
    for key, info in source_status.items():
        diag["sources"][key] = {
            "online": info.get("online", False),
            "status": info.get("status", "UNKNOWN"),
            "count": info.get("count", 0),
        }

    diag["timestamp"] = datetime.now(timezone.utc).isoformat()
    return jsonify(diag)


def _format_uptime(seconds):
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def _check_database_health():
    info = {"status": "ok", "checks": []}
    try:
        conn = db.get_conn()
        # Connectivity test
        start = time.time()
        row = conn.execute("SELECT 1 AS test").fetchone()
        latency_ms = round((time.time() - start) * 1000, 2)
        info["checks"].append({
            "name": "Connectivity",
            "status": "ok" if row else "error",
            "detail": f"Connected (latency: {latency_ms}ms)",
            "latency_ms": latency_ms,
        })

        # WAL mode check
        mode_row = conn.execute("PRAGMA journal_mode").fetchone()
        journal_mode = mode_row[0] if mode_row else "unknown"
        info["checks"].append({
            "name": "Journal Mode",
            "status": "ok" if journal_mode == "wal" else "warning",
            "detail": f"Mode: {journal_mode.upper()}",
        })

        # DB file size
        db_size = os.path.getsize(db.DB_PATH) if os.path.exists(db.DB_PATH) else 0
        db_size_mb = round(db_size / (1024 * 1024), 2)
        info["file_size_mb"] = db_size_mb
        info["file_path"] = db.DB_PATH
        info["checks"].append({
            "name": "File Size",
            "status": "ok",
            "detail": f"{db_size_mb} MB",
        })

        # WAL file sizes
        shm_path = db.DB_PATH + "-shm"
        wal_path = db.DB_PATH + "-wal"
        shm_size = os.path.getsize(shm_path) if os.path.exists(shm_path) else 0
        wal_size = os.path.getsize(wal_path) if os.path.exists(wal_path) else 0
        info["wal_size_mb"] = round(wal_size / (1024 * 1024), 2)
        info["shm_size_kb"] = round(shm_size / 1024, 1)

        # Table counts
        tables = [
            "news", "news_vectors", "word_cloud_snapshots",
            "attack_vector_snapshots", "phishing_domains",
            "kev_vulnerabilities", "ioc_observations",
            "ransomware_victims", "threatfox_iocs",
        ]
        table_counts = {}
        for tbl in tables:
            try:
                cnt = conn.execute(f"SELECT COUNT(*) AS c FROM {tbl}").fetchone()["c"]
                table_counts[tbl] = cnt
            except Exception:
                table_counts[tbl] = -1
        info["table_counts"] = table_counts

        # Lock/timeout test
        start = time.time()
        conn.execute("BEGIN IMMEDIATE")
        lock_time_ms = round((time.time() - start) * 1000, 2)
        conn.execute("ROLLBACK")
        info["checks"].append({
            "name": "Lock Acquisition",
            "status": "ok" if lock_time_ms < 1000 else "warning",
            "detail": f"{lock_time_ms}ms" + (" (slow — possible contention)" if lock_time_ms > 500 else ""),
            "latency_ms": lock_time_ms,
        })

        # Permissions
        readable = os.access(db.DB_PATH, os.R_OK)
        writable = os.access(db.DB_PATH, os.W_OK)
        info["checks"].append({
            "name": "Permissions",
            "status": "ok" if (readable and writable) else "error",
            "detail": f"Read: {'Yes' if readable else 'No'} | Write: {'Yes' if writable else 'No'}",
        })

    except Exception as e:
        info["status"] = "error"
        info["checks"].append({
            "name": "Connectivity",
            "status": "error",
            "detail": f"Connection failed: {str(e)[:80]}",
        })

    if any(c["status"] == "error" for c in info["checks"]):
        info["status"] = "error"
    elif any(c["status"] == "warning" for c in info["checks"]):
        info["status"] = "warning"

    return info


def _check_external_connectivity():
    """Test outbound connectivity to key services."""
    targets = [
        ("Render Backend", "https://soc-threat-dashboard.onrender.com/api/health", "GET"),
        ("CISA KEV", CISA_KEV_URL, "GET"),
        ("PhishStats", PHISHSTATS_URL, "GET"),
        ("AlienVault OTX", f"{OTX_URL}?limit=1", "GET"),
        ("Ransomware.live", RANSOMWARE_LIVE_URL, "GET"),
        ("URLhaus (abuse.ch)", URLHAUS_URL, "GET"),
        ("CDN: Chart.js", "https://cdn.jsdelivr.net/npm/chart.js@4.4.6/dist/chart.umd.min.js", "GET"),
        ("CDN: D3.js", "https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js", "GET"),
        ("Google Fonts", "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap", "GET"),
        ("EPSS API", EPSS_API_URL, "GET"),
        ("CVE CIRCL", f"{CVE_CIRCL_URL}/CVE-2024-0001", "GET"),
    ]

    results = []
    for name, url, method in targets:
        ok, msg = _test_endpoint(name, url, method=method, timeout=5)
        results.append({
            "name": name,
            "url": url,
            "online": ok,
            "status": msg,
        })

    online_count = sum(1 for r in results if r["online"])
    return {
        "status": "ok" if online_count == len(results) else ("degraded" if online_count > 0 else "offline"),
        "online_count": online_count,
        "total": len(results),
        "targets": results,
    }


def _get_scheduler_status():
    """Return status of the background scheduler and collector state."""
    now = time.time()
    collectors = []
    for name, state in collector_state.items():
        interval = COLLECTOR_INTERVALS[name]
        last_run = state.get("last_run", 0)
        next_run = last_run + interval if last_run else 0
        age = round(now - last_run, 1) if last_run else None
        next_in = round(next_run - now, 1) if next_run > now else 0
        collectors.append({
            "name": name,
            "interval_seconds": interval,
            "interval_human": _format_uptime(interval),
            "last_run": state.get("last_success"),
            "age_seconds": age,
            "next_run_in_seconds": max(0, next_in),
            "status": state.get("status", "PENDING"),
            "error": state.get("error", ""),
            "count": state.get("count", 0),
            "latency_ms": state.get("latency_ms"),
        })

    return {
        "status": "ok",
        "thread_alive": any(
            t.name == "background_scheduler" or "scheduler" in getattr(t, "name", "").lower()
            for t in threading.enumerate()
        ),
        "active_threads": [
            {"name": t.name, "daemon": t.daemon, "alive": t.is_alive()}
            for t in threading.enumerate()
        ],
        "collectors": collectors,
    }


def background_scheduler():
    last_cleanup = 0
    while True:
        try:
            refresh_data()
        except Exception as e:
            logger.error("Background refresh failed: %s", e)
        now = time.time()
        if now - last_cleanup > 86400:
            try:
                db.cleanup_old_data(90)
                last_cleanup = now
            except Exception:
                pass
        # This refreshes only derived cache values between source-specific
        # collections; it does not re-query public feeds every 15 seconds.
        time.sleep(15)


def load_cache_from_db():
    global kev_display_cache
    try:
        db_data = db.load_dashboard_from_db()

        news = db_data.get("news", [])
        word_cloud = compute_word_cloud(db.get_todays_news())
        attack_vectors = db.get_vector_percentages_from_db()
        regional_count = count_regional_mentions(
            news, db_data.get("phishing_domains", []), []
        )

        with cache_lock:
            dashboard_cache["news"] = news
            dashboard_cache["word_cloud"] = word_cloud
            dashboard_cache["attack_vectors"] = attack_vectors
            dashboard_cache["phishing_domains"] = db_data.get("phishing_domains", [])
            dashboard_cache["malware"] = db_data.get("malware", [])
            dashboard_cache["malware_categorized"] = db_data.get("malware_categorized", {})
            dashboard_cache["regional_mention_count"] = regional_count
            dashboard_cache["total_news_stored"] = db_data.get("total_news_stored", 0)
            dashboard_cache["last_updated"] = datetime.now(timezone.utc).isoformat()
            dashboard_cache["source_status"] = dict(source_status)

        # Load persisted CVSS cache to avoid re-fetching from NVD on restart.
        try:
            cvss_db = db.load_cvss_cache()
            if cvss_db:
                now = time.time()
                with cvss_cache_lock:
                    for cve_id, entry in cvss_db.items():
                        if cve_id not in cvss_cache:
                            cvss_cache[cve_id] = {"cvss": entry["cvss"], "severity": entry["severity"], "ts": now}
        except Exception:
            pass

        # Load persisted KEV so the dashboard shows data instantly on startup
        # without waiting for the first CISA fetch + CVSS enrichment cycle.
        try:
            kev_from_db = db.load_kev()
            if not kev_from_db and os.path.exists(KEV_CACHE_FILE):
                try:
                    with open(KEV_CACHE_FILE, "r") as f:
                        raw_kev = json.load(f)
                    if raw_kev:
                        kev_from_db = fetch_cves_from_kev(raw_kev[:50])
                        db.save_kev(kev_from_db)
                        _save_cvss_batch_to_db()
                except Exception:
                    pass
            if kev_from_db:
                kev_display_cache = kev_from_db
                with cache_lock:
                    dashboard_cache["kev"] = kev_from_db
                    dashboard_cache["open_alerts"] = len(kev_from_db) + len(dashboard_cache.get("phishing_domains", []))
                    dashboard_cache["posture"] = compute_vulnerability_posture(kev_from_db)
        except Exception:
            pass

        # Load persisted feed health, IOC queue, regional exposure, source status.
        try:
            fh = db.load_feed_health()
            if fh:
                dashboard_cache["feed_health"] = fh
        except Exception:
            pass
        try:
            iocs = db.load_ioc_queue()
            if iocs:
                dashboard_cache["ioc_queue"] = iocs
        except Exception:
            pass
        try:
            re_data = db.load_regional_exposure()
            if re_data:
                dashboard_cache["regional_exposure"] = re_data
        except Exception:
            pass
        try:
            saved_status = db.load_source_status()
            if saved_status:
                with cache_lock:
                    for k, v in saved_status.items():
                        if k in source_status:
                            source_status[k].update(v)
                    dashboard_cache["source_status"] = dict(source_status)
        except Exception:
            pass

        logger.info("Loaded from DB: News=%d Words=%d Vectors=%d Phish=%d OTX=%d KEV=%d",
                     len(news), len(word_cloud), len(attack_vectors),
                     len(db_data.get("phishing_domains", [])),
                     len(db_data.get("malware", [])),
                     len(dashboard_cache.get("kev", [])))
    except Exception as e:
        logger.warning("DB cache load failed: %s", str(e)[:60])


if __name__ == "__main__":
    logger.info("Starting SOC Threat Dashboard backend...")
    os.makedirs(CACHE_DIR, exist_ok=True)

    db.init_db()
    db.seed_stop_words(STOP_WORDS)
    db.seed_vector_keywords(ATTACK_VECTOR_KEYWORDS)
    logger.info("Database initialized: %s", db.DB_PATH)

    load_cache_from_db()

    threading.Thread(target=verify_and_test_scrapers, daemon=True).start()

    scheduler_thread = threading.Thread(target=background_scheduler, daemon=True)
    scheduler_thread.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
else:
    # Running under gunicorn — initialize DB + background threads at import time
    os.makedirs(CACHE_DIR, exist_ok=True)
    db.init_db()
    db.seed_stop_words(STOP_WORDS)
    db.seed_vector_keywords(ATTACK_VECTOR_KEYWORDS)
    load_cache_from_db()
    threading.Thread(target=verify_and_test_scrapers, daemon=True).start()
    threading.Thread(target=background_scheduler, daemon=True).start()
