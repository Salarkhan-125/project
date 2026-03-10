"""
VulnForge - labapp.py  (FastAPI edition)
=========================================
Fixed: vulhub_path now attached when confirming CVEs from kve.json
Added: continuous job monitor thread with live logging
"""

import sys, io
# Force UTF-8 stdout/stderr so emoji prints don't crash on Windows cp1252
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import json, os, re, threading, time
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

import vfdb as DB

# Load .env from the project root (one level up from core/)
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

# ── lazy imports ─────────────────────────────────────────────────────────────
import chromadb
from sentence_transformers import SentenceTransformer
from groq import Groq

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL   = "llama-3.3-70b-versatile"
KVE_FILE     = os.path.join(os.path.dirname(__file__), "kve.json")
EMBED_MODEL  = "all-MiniLM-L6-v2"
# Public host used in ready-notification links
_SERVER_HOST = os.environ.get("SERVER_HOST", "http://localhost").rstrip("/")

# ─────────────────────────────────────────────────────────────────────────────
# STARTUP — models, ChromaDB, CVE data
# ─────────────────────────────────────────────────────────────────────────────

print("Loading embedding model (CPU)...")
embedder = SentenceTransformer(EMBED_MODEL)
print("✅ Embedding model ready")

print("Setting up ChromaDB...")
from chromadb.config import Settings
chroma_client = chromadb.Client(Settings(anonymized_telemetry=False))
collection    = chroma_client.get_or_create_collection(name="cve_data")

# ─────────────────────────────────────────────────────────────────────────────
# CVE ID NORMALIZER
# ─────────────────────────────────────────────────────────────────────────────

def normalize_cve_id(text: str):
    pattern = r'(?:CVE[\s\.\-_]+)?(\d{4})[\s\.\-_]+(\d+)'
    match   = re.search(pattern, text, re.IGNORECASE)
    if match:
        year, num = match.group(1), match.group(2)
        if 1999 <= int(year) <= 2030:
            return f"CVE-{year}-{num}"
    return None


print(f"Loading CVE data from {KVE_FILE}...")
try:
    with open(KVE_FILE, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    cve_list = raw_data if isinstance(raw_data, list) else raw_data.get("vulnerabilities", [])
    cve_lookup: dict = {}
    for _entry in cve_list:
        _norm = normalize_cve_id(_entry.get("cveID", ""))
        if _norm:
            cve_lookup[_norm] = _entry
    print(f"✅ Loaded {len(cve_list)} CVE records, {len(cve_lookup)} indexed")
except FileNotFoundError:
    print(f"❌ {KVE_FILE} not found.")
    cve_list, cve_lookup = [], {}
except json.JSONDecodeError:
    print(f"❌ {KVE_FILE} is corrupted.")
    cve_list, cve_lookup = [], {}


# ─────────────────────────────────────────────────────────────────────────────
# INDEX CVEs INTO CHROMADB
# ─────────────────────────────────────────────────────────────────────────────

def build_and_index_cves(entries: list):
    documents, metadatas, ids = [], [], []
    for entry in entries:
        norm_id = normalize_cve_id(entry.get("cveID", ""))
        if not norm_id:
            continue
        # All kve.json entries are deployable (cleaned)
        rich_doc = " | ".join(filter(None, [
            entry.get("vulnerabilityName", ""),
            entry.get("vendorProject", ""),
            entry.get("product", ""),
            entry.get("shortDescription", ""),
            entry.get("ai_category", ""),
            entry.get("ai_reason", ""),
            " ".join(entry.get("cwes", [])),
        ]))
        documents.append(rich_doc)
        ids.append(norm_id)
        metadatas.append({
            "cve_id":     norm_id,
            "vendor":     entry.get("vendorProject", ""),
            "product":    entry.get("product", ""),
            "name":       entry.get("vulnerabilityName", ""),
            "category":   entry.get("ai_category", ""),
            "date_added": entry.get("dateAdded", ""),
            "short_desc": entry.get("shortDescription", ""),
            "cwes":       ",".join(entry.get("cwes", [])),
            "notes":      entry.get("notes", ""),
            "tier":       "1",
            "entry_type": "cve",
        })
    if not documents:
        return
    print(f"Generating embeddings for {len(documents)} CVEs...")
    embeddings = embedder.encode(documents, show_progress_bar=True).tolist()
    batch_size = 500
    for i in range(0, len(documents), batch_size):
        collection.add(
            documents  = documents[i:i+batch_size],
            embeddings = embeddings[i:i+batch_size],
            metadatas  = metadatas[i:i+batch_size],
            ids        = ids[i:i+batch_size],
        )
    print(f"✅ Indexed {len(documents)} CVEs into ChromaDB")

build_and_index_cves(cve_list)


def build_and_index_vulhub():
    DB.init_db()
    try:
        with DB.get_db() as db:
            rows = db.execute("SELECT cve_id, path, tags FROM vulhub_recipes").fetchall()
    except Exception as e:
        print(f"⚠️  Could not load Vulhub recipes: {e}")
        return
    if not rows:
        print("⚠️  No Vulhub recipes in DB yet — run: python3 vulhub_miner.py")
        return

    documents, metadatas, ids = [], [], []
    existing_ids = set(collection.get()["ids"]) if collection.count() > 0 else set()

    for row in rows:
        cve_id = row["cve_id"]
        if cve_id in existing_ids:
            continue
        path     = row["path"] or ""
        tags     = json.loads(row["tags"] or "[]")
        software = path.split("/")[0] if "/" in path else path
        doc = f"{cve_id} | {software} | pre-built lab environment | {' '.join(tags)}"
        documents.append(doc)
        ids.append(cve_id)
        metadatas.append({
            "cve_id": cve_id, "vendor": software, "product": software,
            "name": f"{software} {cve_id}", "category": "", "date_added": "",
            "short_desc": f"{software.title()} {cve_id} — {' '.join(tags)}",
            "cwes": "", "notes": "", "vulhub_path": path, "tier": "1",
            "entry_type": "cve",
        })
        cve_lookup[cve_id] = {
            "cveID": cve_id, "vendorProject": software, "product": software,
            "shortDescription": f"{software.title()} {cve_id} — {' '.join(tags)}",
            "vulnerabilityName": f"{software.title()} {cve_id}",
            "notes": "", "dateAdded": "", "vulhub_path": path, "tier": "1",
        }

    if not documents:
        print(f"✅ Vulhub: all {len(rows)} recipes already indexed")
        return

    print(f"Indexing {len(documents)} Vulhub CVEs into ChromaDB...")
    embeddings = embedder.encode(documents, show_progress_bar=False).tolist()
    batch_size = 500
    for i in range(0, len(documents), batch_size):
        collection.add(
            documents  = documents[i:i+batch_size],
            embeddings = embeddings[i:i+batch_size],
            metadatas  = metadatas[i:i+batch_size],
            ids        = ids[i:i+batch_size],
        )
    print(f"✅ Indexed {len(documents)} Vulhub CVEs (total: {collection.count()})")

build_and_index_vulhub()


# ─────────────────────────────────────────────────────────────────────────────
# INDEX CTF CHALLENGES INTO CHROMADB
# ─────────────────────────────────────────────────────────────────────────────

def build_and_index_ctf_challenges():
    """Index non-CVE CTF challenges from ctf_challenges table."""
    try:
        challenges = DB.list_ctf_challenges()
    except Exception as e:
        print(f"⚠️  Could not load CTF challenges: {e}")
        return
    if not challenges:
        print("⚠️  No CTF challenges in DB yet — run: python ctf_miner.py")
        return

    documents, metadatas, ids = [], [], []
    existing_ids = set(collection.get()["ids"]) if collection.count() > 0 else set()

    for ch in challenges:
        ch_id = ch["challenge_id"]
        if ch_id in existing_ids:
            continue
        vuln_types = ch.get("vuln_types", [])
        tags = ch.get("tags", [])
        doc = " | ".join(filter(None, [
            ch["name"],
            ch.get("description", ""),
            ch["source"],
            " ".join(vuln_types),
            " ".join(tags),
            ch.get("category", "web"),
            f"CTF challenge {ch.get('difficulty', 'medium')} difficulty",
        ]))
        documents.append(doc)
        ids.append(ch_id)
        metadatas.append({
            "cve_id":     ch_id,      # using cve_id field for unified search
            "vendor":     ch["source"],
            "product":    ch["name"],
            "name":       ch["name"],
            "category":   ch.get("category", "web"),
            "date_added": "",
            "short_desc": ch.get("description", ch["name"]),
            "cwes":       ",".join(vuln_types),
            "notes":      "",
            "tier":       "ctf",
            "entry_type": "ctf_challenge",
            "source":     ch["source"],
            "difficulty": ch.get("difficulty", "medium"),
        })

    if not documents:
        print(f"✅ CTF challenges: all {len(challenges)} already indexed")
        return

    print(f"Indexing {len(documents)} CTF challenges into ChromaDB...")
    embeddings = embedder.encode(documents, show_progress_bar=False).tolist()
    batch_size = 500
    for i in range(0, len(documents), batch_size):
        collection.add(
            documents  = documents[i:i+batch_size],
            embeddings = embeddings[i:i+batch_size],
            metadatas  = metadatas[i:i+batch_size],
            ids        = ids[i:i+batch_size],
        )
    print(f"✅ Indexed {len(documents)} CTF challenges (total: {collection.count()})")

build_and_index_ctf_challenges()

groq_client = Groq(api_key=GROQ_API_KEY)
print("✅ Groq client ready")

DB.init_db()


# ─────────────────────────────────────────────────────────────────────────────
# ██████████████████████████████████████████████████████████████████████████
#  CONTINUOUS JOB MONITOR  — logs job lifecycle to console in real-time
# ██████████████████████████████████████████████████████████████████████████
# ─────────────────────────────────────────────────────────────────────────────

_monitor_seen: dict = {}   # job_id -> last status seen

def _monitor_loop():
    """Background thread: polls jobs every 4s and prints status changes."""
    print("[MONITOR] 🟢 Job monitor started — watching all jobs")
    while True:
        try:
            jobs = DB.list_jobs(limit=100)
            for job in jobs:
                jid    = job["id"]
                status = job.get("status", "?")
                prev   = _monitor_seen.get(jid)

                if prev != status:
                    _monitor_seen[jid] = status
                    sid   = (job.get("student_id") or "?")[:16]
                    port  = job.get("port") or "-"
                    mid   = (job.get("machine_id") or "-")
                    err   = job.get("error") or ""

                    icon = {
                        "pending":    "⏳",
                        "generating": "⚙️ ",
                        "done":       "✅",
                        "failed":     "❌",
                    }.get(status, "❓")

                    ts = time.strftime("%H:%M:%S")
                    print(f"[MONITOR {ts}] {icon}  Job {jid[:8]}  →  {status:<12}  "
                          f"session={sid}  port={port}  machine={mid}", flush=True)
                    if status == "done":
                        print(f"[MONITOR]     🎯  {_SERVER_HOST}:{port}", flush=True)
                    if status == "failed" and err:
                        print(f"[MONITOR]     💥  {err}", flush=True)

        except Exception as e:
            print(f"[MONITOR] ⚠️  poll error: {e}", flush=True)

        time.sleep(4)


# Start monitor as daemon so it dies with the server
_monitor_thread = threading.Thread(target=_monitor_loop, daemon=True, name="job-monitor")
_monitor_thread.start()


# ─────────────────────────────────────────────────────────────────────────────
# VERSION LOOKUP
# ─────────────────────────────────────────────────────────────────────────────

import requests as _requests

def fetch_nvd_data(cve_id: str) -> dict:
    try:
        url  = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
        resp = _requests.get(url, timeout=8, headers={"User-Agent": "VulnForge/1.0"})
        if resp.status_code != 200:
            return {}
        data  = resp.json()
        vulns = data.get("vulnerabilities", [])
        return vulns[0].get("cve", {}) if vulns else {}
    except Exception as e:
        print(f"[NVD fetch warn] {cve_id}: {e}")
        return {}


def parse_nvd_versions(nvd_cve: dict) -> dict:
    configs = nvd_cve.get("configurations", [])
    ranges  = []
    for cfg in configs:
        for node in cfg.get("nodes", []):
            for cpe_match in node.get("cpeMatch", []):
                if not cpe_match.get("vulnerable", False):
                    continue
                cpe   = cpe_match.get("criteria", "")
                parts = cpe.split(":")
                pinned_ver  = parts[5] if len(parts) >= 6 else "*"
                ver_start   = cpe_match.get("versionStartIncluding", "")
                ver_end_inc = cpe_match.get("versionEndIncluding", "")
                ver_end_exc = cpe_match.get("versionEndExcluding", "")
                if ver_end_inc or ver_end_exc or ver_start:
                    parts_range = []
                    if ver_start:   parts_range.append(f">= {ver_start}")
                    if ver_end_inc: parts_range.append(f"<= {ver_end_inc}")
                    if ver_end_exc: parts_range.append(f"< {ver_end_exc}")
                    ranges.append({"range_str": ", ".join(parts_range), "last_vuln": ver_end_inc or "",
                                   "fixed_in": ver_end_exc or "", "start": ver_start or ""})
                elif pinned_ver not in ("*", "-", ""):
                    ranges.append({"range_str": pinned_ver, "last_vuln": pinned_ver, "fixed_in": "", "start": pinned_ver})
    if not ranges:
        return {}
    best = next((r for r in ranges if r["fixed_in"]), ranges[0])
    return best


def lookup_affected_version(cve_id: str, cve_meta: dict) -> dict:
    nvd_cve = fetch_nvd_data(cve_id)
    if nvd_cve:
        parsed = parse_nvd_versions(nvd_cve)
        if parsed:
            result = {"affected_range": parsed["range_str"],
                      "last_vulnerable": parsed["last_vuln"] or parsed["range_str"],
                      "fixed_in": parsed["fixed_in"]}
            strategy = _fetch_install_strategy_from_notes(cve_id, cve_meta.get("notes", ""))
            if strategy:
                result["install_strategy"] = strategy
            return result
    notes    = cve_meta.get("notes", "")
    strategy = _fetch_install_strategy_from_notes(cve_id, notes)
    desc     = cve_meta.get("short_desc", "")
    name     = cve_meta.get("name", "")
    prompt = (
        f"You are a CVE analyst. Extract version details.\n"
        f"Respond ONLY with JSON, no markdown:\n"
        f'{{ "affected_range": "...", "last_vulnerable": "...", "fixed_in": "..." }}\n\n'
        f"CVE: {cve_id}\nName: {name}\nDescription: {desc}\nNotes: {notes}"
    )
    try:
        resp = groq_client.chat.completions.create(
            model=GROQ_MODEL, messages=[{"role": "user", "content": prompt}],
            temperature=0.0, max_tokens=120)
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"```[a-z]*", "", raw).replace("```", "").strip()
        p   = json.loads(raw)
        result = {"affected_range": p.get("affected_range", "unknown"),
                  "last_vulnerable": p.get("last_vulnerable", "unknown"),
                  "fixed_in": p.get("fixed_in", "unknown")}
        if strategy:
            result["install_strategy"] = strategy
        return result
    except Exception as e:
        print(f"[VERSION LLM error] {e}")
        result = {"affected_range": "unknown", "last_vulnerable": "unknown", "fixed_in": "unknown"}
        if strategy:
            result["install_strategy"] = strategy
        return result


def _fetch_install_strategy_from_notes(cve_id: str, notes: str) -> dict | None:
    if not notes:
        return None
    cached = DB.get_install_strategy(cve_id)
    if cached:
        return cached
    urls = re.findall(r'https?://[^\s;,]+', notes)
    for url in urls:
        if "nvd.nist.gov" in url or "web.archive.org" in url:
            continue
        strategy = None
        if "github.com" in url and any(x in url for x in ("/releases/", "/commit/", "/pull/")):
            strategy = _parse_github_for_strategy(cve_id, url)
        if strategy:
            DB.store_install_strategy(
                cve_id=cve_id, base_image=strategy.get("base_image", ""),
                install_method=strategy.get("method", ""), install_package=strategy.get("package", ""),
                install_version=strategy.get("version", ""), extra_commands=strategy.get("extra_commands", []),
                source_url=url)
            return strategy
    return None


def _parse_github_for_strategy(cve_id: str, url: str) -> dict | None:
    try:
        resp = _requests.get(url, timeout=8, headers={"User-Agent": "VulnForge/1.0"})
        if resp.status_code != 200:
            return None
        text = resp.text
        versions = re.findall(
            r'(?:before|prior to|< ?|fixed in|patched in)\s*v?([\d]+\.[\d]+\.[\d]+)', text, re.IGNORECASE)
        if not versions:
            return None
        version   = versions[0]
        url_lower = url.lower()
        method, package, base_image = "", "", ""
        if "phpmailer" in url_lower:
            method, package, base_image = "composer", "phpmailer/phpmailer", "php:7.4-apache"
        elif "rails" in url_lower:
            method, package, base_image = "gem", "rails", "ruby:2.7-slim"
        elif "laravel" in url_lower:
            method, package, base_image = "composer", "laravel/framework", "php:7.4-apache"
        elif "log4j" in url_lower:
            method, package, base_image = "maven", "org.apache.logging.log4j:log4j-core", "eclipse-temurin:11-jdk-jammy"
        elif "airflow" in url_lower:
            method, package, base_image = "pip", "apache-airflow", "python:3.9-slim"
        if not method:
            return None
        return {"method": method, "package": package, "version": version,
                "base_image": base_image, "extra_commands": []}
    except Exception as e:
        print(f"[STRATEGY PARSE] {url}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# CVE + CHALLENGE RETRIEVAL (TIERED)
# ─────────────────────────────────────────────────────────────────────────────

def retrieve_cve_context(query: str, n: int = 8) -> str:
    if collection.count() == 0:
        return "CVE database is empty."
    query_emb = embedder.encode([query]).tolist()
    results   = collection.query(query_embeddings=query_emb,
                                  n_results=min(n, collection.count()),
                                  include=["documents", "metadatas", "distances"])
    if not results or not results["ids"] or not results["ids"][0]:
        return "No relevant CVEs found."

    # Sort: CVE labs first, then CTF challenges, then by relevance
    tier_order = {"1": 0, "ctf": 1}
    scored = []
    for meta, doc, dist in zip(results["metadatas"][0], results["documents"][0], results["distances"][0]):
        relevance = round(1 - dist, 3)
        tier = meta.get("tier", "1")
        entry_type = meta.get("entry_type", "cve")
        scored.append((tier_order.get(tier, 2), -relevance, meta, relevance, entry_type))
    scored.sort()

    lines = []
    for _, _, meta, relevance, entry_type in scored:
        if entry_type == "ctf_challenge":
            label = "CTF Challenge"
            lines.append(
                f"[{label}] [{relevance:.2f}] {meta.get('name','')} | "
                f"Source: {meta.get('vendor','')} | "
                f"Type: {meta.get('cwes','')} | "
                f"Difficulty: {meta.get('difficulty', 'medium')} | "
                f"{meta.get('short_desc','')}")
        else:
            label = "CVE Lab"
            lines.append(
                f"[{label}] [{relevance:.2f}] {meta.get('cve_id')} | {meta.get('name','')} | "
                f"Vendor: {meta.get('vendor','')} | Product: {meta.get('product','')} | "
                f"Category: {meta.get('category','')} | CWEs: {meta.get('cwes','')} | "
                f"{meta.get('short_desc','')}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# REQUIREMENTS / GENERATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_missing_fields(reqs: dict) -> list:
    missing = []
    if reqs.get("cve_confirmed") != "yes":
        missing.append("cve_id")
    if not reqs.get("difficulty"):
        missing.append("difficulty")
    return missing


def clean_version(val):
    if not val or str(val).lower() in ("latest", "old", "stable", "unknown", "none", "*", ""):
        return None
    return val


def resolve_installable_version(software, ver_info, cve_date, cve_id, cve_desc):
    candidate = ver_info.get("last_vulnerable", "")
    if candidate and candidate not in ("unknown", "", "*"):
        return candidate
    if not software:
        return None
    cve_date_str = cve_date or "the CVE publication date"
    prompt = (
        "You are a DevOps engineer setting up a CTF lab.\n"
        f"You need to install a SPECIFIC, REAL version of '{software}' that:\n"
        f"  - Was publicly available on or before {cve_date_str}\n"
        f"  - Is affected by {cve_id}: {cve_desc}\n"
        "  - Can be installed via apt, pip, npm, docker pull, or a direct download\n\n"
        "Respond with ONLY the version number (e.g. '2.4.49').\n"
        "Do NOT write 'latest', 'stable', 'unknown', or any explanation.\n"
        "If you are not confident, respond with the single word: skip"
    )
    try:
        resp = groq_client.chat.completions.create(
            model=GROQ_MODEL, messages=[{"role": "user", "content": prompt}],
            temperature=0.0, max_tokens=20)
        ver = resp.choices[0].message.content.strip().strip('"').strip("v")
        if ver.lower() in ("skip", "unknown", "latest", "stable", ""):
            return None
        if re.match(r"^\d+[\d\.\-a-z]+$", ver, re.IGNORECASE):
            return ver
        return None
    except Exception as e:
        print(f"[RESOLVE VERSION error] {e}")
        return None


def _infer_platform_from_cve(reqs: dict) -> dict:
    cve_id   = (reqs.get("cve_id") or "").upper()
    vendor   = (reqs.get("cve_vendor", "") or "").lower()
    product  = (reqs.get("cve_product", "") or "").lower()
    desc     = (reqs.get("cve_description") or "").lower()
    name     = (reqs.get("cve_name", "") or "").lower()
    combined = f"{vendor} {product} {desc} {name} {cve_id.lower()}"
    if any(x in combined for x in ["activemq", "rocketmq", "solr", "spark", "elasticsearch", "kafka"]):
        return {"category": "software", "software": product or vendor, "language": "java"}
    if any(x in combined for x in ["tomcat", "struts", "log4j", "log4j2", "ofbiz", "shiro"]):
        return {"category": "software", "software": product or vendor, "language": "java"}
    if any(x in combined for x in ["apache http", "httpd", "mod_", "nginx", "iis"]):
        return {"category": "software", "software": "apache2", "language": "php"}
    if any(x in combined for x in ["airflow", "superset", "django", "flask", "fastapi"]):
        return {"category": "framework", "framework": product or vendor, "language": "python"}
    if any(x in combined for x in ["rails", "ruby on rails", "activerecord"]):
        return {"category": "framework", "framework": "rails", "language": "ruby"}
    if any(x in combined for x in ["laravel", "symfony", "codeigniter", "phpmailer", "php"]):
        return {"category": "framework", "framework": product or "php", "language": "php"}
    if any(x in combined for x in ["node", "express", "npm", "javascript", "react", "next.js"]):
        return {"category": "framework", "framework": product or "express", "language": "nodejs"}
    if any(x in combined for x in ["spring", "java", "jre", "jdk", "deserialization"]):
        return {"category": "framework", "framework": product or "spring", "language": "java"}
    if any(x in combined for x in ["mongo", "mongodb", "mongo-express"]):
        return {"category": "software", "software": "mongodb", "language": "nodejs", "database": "mongodb"}
    if any(x in combined for x in ["bash", "shellshock", "sudo", "linux", "ubuntu", "privilege"]):
        return {"category": "os", "software": "ubuntu", "language": "python"}
    if any(x in combined for x in ["firefox", "thunderbird", "chrome", "browser"]):
        return {"category": "software", "software": product or "firefox", "language": "javascript"}
    if any(x in combined for x in ["thinkphp", "wordpress", "drupal", "joomla"]):
        return {"category": "framework", "framework": product or vendor, "language": "php"}
    return {"category": "web", "language": "python", "database": "sqlite"}


def build_generation_prompt(reqs: dict) -> dict:
    cve_id   = reqs.get("cve_id") or "N/A"
    ver_info = reqs.get("version_info", {})
    cve_date = reqs.get("cve_date", "")
    cve_desc = reqs.get("cve_description", "")
    inferred = _infer_platform_from_cve(reqs)
    cat      = inferred.get("category", "web")
    lang     = inferred.get("language", "python")
    software = inferred.get("software", "")
    framework= inferred.get("framework", "")
    database = inferred.get("database", "")
    vuln_type = reqs.get("vulnerability_type", "")
    if not vuln_type:
        desc_lower = cve_desc.lower()
        if any(x in desc_lower for x in ["sql", "sqli"]):             vuln_type = "sql_injection"
        elif any(x in desc_lower for x in ["rce", "remote code"]):    vuln_type = "rce"
        elif any(x in desc_lower for x in ["path traversal", "lfi"]): vuln_type = "path_traversal"
        elif any(x in desc_lower for x in ["deserialization"]):        vuln_type = "deserialization"
        elif any(x in desc_lower for x in ["ssrf"]):                   vuln_type = "ssrf"
        elif any(x in desc_lower for x in ["xss"]):                    vuln_type = "xss"
        elif any(x in desc_lower for x in ["command inject"]):         vuln_type = "command_injection"
        elif any(x in desc_lower for x in ["auth", "bypass"]):         vuln_type = "authentication_bypass"
        elif any(x in desc_lower for x in ["privilege", "escalation"]):vuln_type = "privilege_escalation"
        elif any(x in desc_lower for x in ["buffer overflow"]):         vuln_type = "buffer_overflow"
        else:                                                            vuln_type = "rce"
    install_ver    = clean_version(ver_info.get("last_vulnerable")) or clean_version(reqs.get("affected_version"))
    affected_range = clean_version(ver_info.get("affected_range"))
    fixed_in       = clean_version(ver_info.get("fixed_in"))
    sw_name = software or framework or lang
    if not install_ver and sw_name:
        install_ver = resolve_installable_version(sw_name, ver_info, cve_date, cve_id, cve_desc)
    platform: dict = {}
    if lang:      platform["language"]  = lang
    if software:  platform["software"]  = software
    if framework: platform["framework"] = framework
    if database:  platform["database"]  = database
    if install_ver and (software or framework):
        platform["version"] = install_ver
    cve_block: dict = {"id": cve_id, "description": cve_desc}
    if install_ver:    cve_block["install_version"] = install_ver
    if affected_range: cve_block["affected_range"]  = affected_range
    if fixed_in:       cve_block["fixed_in"]        = fixed_in
    spec: dict = {
        "category": cat, "vulnerability_type": vuln_type,
        "difficulty": reqs.get("difficulty", "medium"),
        "platform": platform, "cve": cve_block,
        "docker": {"ports": [80], "flag_location": "/app/flag.txt", "base_image": "ubuntu:22.04"},
    }
    if reqs.get("vulhub_path"): spec["vulhub_path"] = reqs["vulhub_path"]
    if reqs.get("vulhub_port"): spec["vulhub_port"] = reqs["vulhub_port"]
    if reqs.get("tier"):        spec["tier"]        = reqs["tier"]
    return spec


def _trigger_bridge_once():
    try:
        import bridge
        bridge.run_once()
    except Exception as e:
        print(f"[BRIDGE THREAD] Error: {e}")


def store_requirements(session_id: str, reqs: dict, gen_prompt: dict) -> str:
    gen_prompt["seed"] = session_id[:12]
    job_id = DB.create_job(session_id=session_id, spec=gen_prompt)
    print(f"[QUEUED] Job {job_id} for session {session_id}")
    threading.Thread(target=_trigger_bridge_once, daemon=True).start()
    return job_id


# ─────────────────────────────────────────────────────────────────────────────
# ██  HELPER: confirm CVE and attach vulhub_path if available  ████████████████
# ─────────────────────────────────────────────────────────────────────────────

def _confirm_cve_from_lookup(cve_id: str, reqs: dict):
    """
    Shared logic: confirm a CVE from kve.json AND attach vulhub_path
    if a recipe exists in the DB.  Called from both the direct-message
    check and the <REQS> block parser so the fix is applied everywhere.
    """
    entry = cve_lookup.get(cve_id)
    if not entry:
        return

    reqs["cve_id"]          = cve_id
    reqs["cve_confirmed"]   = "yes"
    reqs["cve_description"] = entry.get("shortDescription", "")

    if not reqs.get("category"):
        reqs["category"] = entry.get("ai_category", "")

    if not reqs.get("version_info"):
        meta = {
            "short_desc": entry.get("shortDescription", ""),
            "notes":      entry.get("notes", ""),
            "name":       entry.get("vulnerabilityName", ""),
        }
        ver = lookup_affected_version(cve_id, meta)
        reqs["version_info"]    = ver
        reqs["affected_version"] = ver.get("last_vulnerable", "unknown")

    if not reqs.get("cve_date"):
        reqs["cve_date"] = entry.get("dateAdded", "")

    # ── FIX: pull vulhub_path from recipes table ──────────────────────────
    if not reqs.get("vulhub_path"):
        _vh = DB.get_vulhub_recipe(cve_id)
        if _vh:
            reqs["vulhub_path"] = _vh["path"]
            reqs["vulhub_port"] = _vh["port"]
            reqs["tier"]        = "1"
            print(f"[CVE] ✅ {cve_id} → vulhub_path={_vh['path']}")
        else:
            print(f"[CVE] ⚠️  {cve_id} confirmed in kve.json but no Vulhub recipe — will attempt on-demand mine")


def _confirm_cve_from_vulhub(cve_id: str, reqs: dict):
    """Fallback: CVE not in kve.json but has a vulhub recipe."""
    vulhub = DB.get_vulhub_recipe(cve_id)
    if vulhub:
        reqs["cve_id"]          = cve_id
        reqs["cve_confirmed"]   = "yes"
        reqs["cve_description"] = f"Pre-built Vulhub environment ({vulhub['path']})"
        reqs["vulhub_path"]     = vulhub["path"]
        reqs["vulhub_port"]     = vulhub["port"]
        reqs["tier"]            = "1"
        print(f"[CVE] ✅ {cve_id} → vulhub only, path={vulhub['path']}")
    else:
        reqs["cve_confirmed"] = "not_found"
        print(f"[CVE] ❌ {cve_id} not found in kve.json or vulhub_recipes")


# ─────────────────────────────────────────────────────────────────────────────
# CORE CHAT FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def chat_with_model(message: str, history: list, requirements: dict, session_id: str = "default"):
    if requirements.get("_triggered"):
        job_id = requirements.get("_job_id", "")
        trigger_time = requirements.get("_triggered_time", 0)
        import time
        elapsed = time.time() - trigger_time

        if elapsed < 120:
            return (
                "Your lab environment is currently being provisioned. Please allow up to 2 minutes for the process to complete before starting a new lab.",
                requirements,
                job_id,
            )
        else:
            # 120 seconds have passed; clear the current lab request context.
            requirements.clear()

    # ── STEP 1: Confirm CVE BEFORE building system prompt ────────────────────
    # This ensures the AI sees cve_confirmed=yes and gives the right response
    direct_cve = normalize_cve_id(message)
    if direct_cve and requirements.get("cve_confirmed") != "yes":
        if direct_cve in cve_lookup:
            _confirm_cve_from_lookup(direct_cve, requirements)
        else:
            _confirm_cve_from_vulhub(direct_cve, requirements)

    # ── STEP 2: Build CVE context for system prompt ───────────────────────────
    search_query = " ".join(filter(None, [
        message,
        requirements.get("vulnerability_type", ""),
        requirements.get("framework_name", ""),
        requirements.get("software_name", ""),
        requirements.get("platform", ""),
        requirements.get("category", ""),
    ]))
    cve_context = retrieve_cve_context(search_query)

    # Inject the confirmed CVE at top of context so AI sees it prominently
    if requirements.get("cve_confirmed") == "yes" and requirements.get("cve_id"):
        cve_id_confirmed = requirements["cve_id"]
        desc = requirements.get("cve_description", "")
        vh   = requirements.get("vulhub_path", "")
        pinned = (
            f"* {cve_id_confirmed} | {desc}"
            + (f" | vulhub_path={vh}" if vh else "")
        )
        cve_context = "[USER-REQUESTED CVE - CONFIRMED IN DB]\n" + pinned + "\n\n[SEMANTIC RESULTS]\n" + cve_context
    elif direct_cve and direct_cve in cve_lookup:
        # fallback for kve-only entries
        entry  = cve_lookup[direct_cve]
        pinned = (
            "* " + direct_cve + " | " + entry.get("vulnerabilityName", "") + " | "
            "Vendor: " + entry.get("vendorProject", "") + " | " + entry.get("shortDescription", "")
        )
        cve_context = "[USER-REQUESTED CVE - CONFIRMED IN DB]\n" + pinned + "\n\n[SEMANTIC RESULTS]\n" + cve_context

    known_reqs = {k: v for k, v in requirements.items() if not k.startswith("_")}
    missing    = get_missing_fields(requirements)
    is_ready   = len(missing) == 0

    version_note = ""
    ver_info = requirements.get("version_info", {})
    if ver_info and ver_info.get("last_vulnerable", "unknown") != "unknown":
        version_note = (
            f"\nVersion info for {requirements.get('cve_id','')}:"
            f" affected_range={ver_info.get('affected_range','?')},"
            f" install_version={ver_info.get('last_vulnerable','?')},"
            f" fixed_in={ver_info.get('fixed_in','?')}"
        )
    elif requirements.get("affected_version") and requirements["affected_version"] != "unknown":
        version_note = f"\nConfirmed affected version: {requirements['affected_version']}"

    cve_status_note = ""
    if requirements.get("cve_confirmed") == "yes":
        if requirements.get("tier") == "1":
            cve_status_note = (
                f"\n⚠️  CVE {requirements.get('cve_id')} is CONFIRMED. We have a ready-made lab environment. "
                f"Do NOT mention third-party tools or where the environment comes from."
            )
        else:
            cve_status_note = f"\n⚠️  CVE {requirements.get('cve_id')} is CONFIRMED in our database."
    elif requirements.get("cve_confirmed") == "not_found":
        cve_status_note = f"\n⚠️  The CVE provided was NOT found in our database."

    system_prompt = f"""You are VulnForge, a cybersecurity lab assistant. You help security researchers and students spin up real vulnerable environments for CVE research and CTF practice.

== LABS YOU CAN BUILD ==
Results marked 🟢 Ready have pre-built lab environments (instant spin-up).
Results marked 🔵 CTF are community CTF challenges (proven challenges, instant spin-up).
Results marked ⚪ Catalog are in our knowledge base but may not yet have a ready lab.

{cve_context}
{cve_status_note}

== WHAT YOU ALREADY KNOW ==
{json.dumps(known_reqs, indent=2) if known_reqs else "Nothing collected yet."}{version_note}
{"✅ Ready to build." if is_ready else f"Still need: {missing}"}

== YOUR JOB ==
Get two things from the user, nothing more:
1. Which CVE or CTF challenge they want
2. Difficulty: easy | medium | hard

Everything else is inferred automatically. Never ask about tech stack.

== BEHAVIOR ==
- If user gives a CVE ID → confirm it, say what it is in one line, ask difficulty
- If user describes a vuln type (e.g. "SQL injection") → suggest 🟢 Ready and 🔵 CTF options FIRST, then mention ⚪ Catalog ones. ALWAYS prefer recommending labs that are ready to deploy.
- If user picks a CTF challenge → confirm it, ask difficulty
- If CVE/challenge confirmed and difficulty set → say "spinning up your lab now" and set ready=true
- If a CVE is NOT in our database → tell the user honestly, then suggest similar CVEs or CTF challenges that ARE available. Never pretend we can build something we don't have.
- Never ask more than ONE thing per message
- Never mention Docker, ports, flag.txt, Dockerfiles, or implementation details
- Keep responses short — 1-3 sentences max

== ALWAYS APPEND THIS AFTER YOUR RESPONSE ==
<REQS>
{{
  "cve_id": "CVE-XXXX-XXXXX or challenge_id or null",
  "cve_confirmed": "yes | not_found | null",
  "difficulty": "easy | medium | hard | null",
  "ready": true or false
}}
</REQS>
Set ready=true ONLY when cve_confirmed=yes AND difficulty is set."""

    messages_list = [{"role": "system", "content": system_prompt}]
    for user_msg, bot_msg in history[-6:]:
        messages_list.append({"role": "user", "content": user_msg})
        clean_bot = re.sub(r'<REQS>.*?</REQS>', '', bot_msg, flags=re.DOTALL).strip()
        messages_list.append({"role": "assistant", "content": clean_bot})
    messages_list.append({"role": "user", "content": message})

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL, messages=messages_list, temperature=0.35, max_tokens=350)
    resp = response.choices[0].message.content.strip()

    # ── Parse <REQS> ──────────────────────────────────────────────────────────
    reqs_match = re.search(r'<REQS>(.*?)</REQS>', resp, re.DOTALL)
    job_id_out = None
    if reqs_match:
        try:
            extracted = json.loads(reqs_match.group(1).strip())
            for key, val in extracted.items():
                if key == "ready" or val in (None, "null", ""):
                    continue
                if key == "cve_id" and requirements.get("cve_confirmed") == "yes":
                    continue
                if not requirements.get(key):
                    requirements[key] = val

            if requirements.get("cve_confirmed") != "yes":
                cve_raw = extracted.get("cve_id")
                if cve_raw and cve_raw not in (None, "null"):
                    norm = normalize_cve_id(str(cve_raw))
                    if norm:
                        if norm in cve_lookup:
                            _confirm_cve_from_lookup(norm, requirements)   # ← FIX applied
                        else:
                            _confirm_cve_from_vulhub(norm, requirements)   # ← FIX applied

            if extracted.get("ready") is True and not get_missing_fields(requirements):
                requirements["_triggered"] = True
                import time
                requirements["_triggered_time"] = time.time()
                gen    = build_generation_prompt(requirements)
                job_id_out = store_requirements(session_id, requirements, gen)
                requirements["_job_id"] = job_id_out

        except json.JSONDecodeError as e:
            print(f"[WARN] REQS parse failed: {e}")

    visible = re.sub(r'<REQS>.*?</REQS>', '', resp, flags=re.DOTALL).strip()
    return visible, requirements, job_id_out


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STORE
# ─────────────────────────────────────────────────────────────────────────────

history_data: dict = {}

# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI ROUTER
# ─────────────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/lab", tags=["lab"])


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ResetRequest(BaseModel):
    session_id: str = "default"


@router.post("/chat")
async def chat(body: ChatRequest):
    message    = body.message.strip()
    session_id = body.session_id

    if not message:
        return JSONResponse({"response": "Please say something."})

    if session_id not in history_data:
        history_data[session_id] = {"history": [], "requirements": {}}

    session      = history_data[session_id]
    history      = session["history"]
    requirements = session["requirements"]

    try:
        response, requirements, job_id = chat_with_model(message, history, requirements, session_id)
        history.append((message, response))
        session["requirements"] = requirements
        if len(history) > 20:
            session["history"] = history[-20:]

        result: dict = {"response": response}
        if job_id:
            result["job_id"] = job_id
        return JSONResponse(result)

    except Exception as e:
        import traceback; traceback.print_exc()
        return JSONResponse({"response": f"Error: {str(e)}"}, status_code=500)


@router.post("/reset")
async def reset(body: ResetRequest):
    history_data.pop(body.session_id, None)
    return JSONResponse({"status": "reset"})


@router.get("/status/{job_id}")
async def job_status(job_id: str):
    job = DB.get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    job.pop("spec_json", None)
    if job.get("status") == "done":
        job["url"] = f"http://localhost:{job.get('port', '?')}"
    return JSONResponse(job)


@router.get("/jobs")
async def list_jobs():
    jobs = DB.list_jobs(limit=50)
    for j in jobs:
        if j.get("status") == "done" and j.get("port"):
            j["url"] = f"http://localhost:{j['port']}"
    return JSONResponse({"jobs": jobs, "total": len(jobs)})


@router.get("/status")
async def lab_info():
    return JSONResponse({
        "cve_count":       collection.count(),
        "active_sessions": len(history_data),
        "model":           GROQ_MODEL,
    })
