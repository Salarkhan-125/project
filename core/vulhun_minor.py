"""
VulnForge - Vulhub Miner
========================
Run ONCE to populate the vulhub_recipes table from GitHub.
After this runs you have ~600 CVEs covered with zero AI generation needed.

Usage:
    python3 vulhub_miner.py
    python3 vulhub_miner.py --dry-run     # just print what it would store
    python3 vulhub_miner.py --cve CVE-2021-44228  # fetch one specific CVE
"""

import re
import sys
import json
import time
import argparse
import requests
from pathlib import Path

import vfdb as DB

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

GITHUB_RAW   = "https://raw.githubusercontent.com/vulhub/vulhub/master"
GITHUB_API   = "https://api.github.com/repos/vulhub/vulhub"
TOML_URL     = f"{GITHUB_RAW}/environments.toml"
REQUEST_DELAY = 0.5   # seconds between GitHub requests — be polite
TIMEOUT       = 15

HEADERS = {
    "User-Agent": "VulnForge-Miner/1.0",
    "Accept":     "application/vnd.github.v3+json",
}

# ─────────────────────────────────────────────
# TOML PARSER  (minimal, no toml library needed)
# Vulhub's environments.toml is simple enough to parse with regex
# ─────────────────────────────────────────────

def parse_environments_toml(content: str) -> list[dict]:
    """
    Parse Vulhub environments.toml into list of:
    { name, path, cves: [...], tags: [...] }
    """
    environments = []
    current = {}

    for line in content.splitlines():
        line = line.strip()

        if line == "[[environment]]":
            if current:
                environments.append(current)
            current = {"cves": [], "tags": []}
            continue

        # name = "..."
        m = re.match(r'^name\s*=\s*"(.+)"', line)
        if m:
            current["name"] = m.group(1)
            continue

        # path = "..."
        m = re.match(r'^path\s*=\s*"(.+)"', line)
        if m:
            current["path"] = m.group(1)
            continue

        # cve = ["CVE-...", ...]
        m = re.match(r'^cve\s*=\s*\[(.+)\]', line)
        if m:
            cves = re.findall(r'"(CVE-[\d-]+)"', m.group(1), re.IGNORECASE)
            current["cves"] = [c.upper() for c in cves]
            continue

        # tags = ["...", ...]
        m = re.match(r'^tags\s*=\s*\[(.+)\]', line)
        if m:
            tags = re.findall(r'"([^"]+)"', m.group(1))
            current["tags"] = tags
            continue

    if current:
        environments.append(current)

    # Filter to only entries that have both a path and at least one CVE
    valid = [e for e in environments if e.get("path") and e.get("cves")]
    print(f"[Miner] Parsed {len(environments)} environments, {len(valid)} with CVE IDs")
    return valid


# ─────────────────────────────────────────────
# FETCH HELPERS
# ─────────────────────────────────────────────

def fetch_text(url: str) -> str | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            return resp.text
        if resp.status_code == 404:
            return None
        print(f"  [warn] {url} → {resp.status_code}")
        return None
    except Exception as e:
        print(f"  [warn] fetch {url}: {e}")
        return None


def extract_port_from_compose(compose_yml: str) -> int:
    """Parse the host port from docker-compose.yml ports mapping."""
    # Matches: "8080:80" or - "8080:80"
    m = re.search(r'["\s\-]+(\d{2,5}):(\d+)', compose_yml)
    if m:
        return int(m.group(1))
    return 80


# ─────────────────────────────────────────────
# MAIN MINER
# ─────────────────────────────────────────────

def mine_all(dry_run: bool = False) -> int:
    print(f"[Miner] Fetching environments.toml from Vulhub GitHub...")
    toml_content = fetch_text(TOML_URL)
    if not toml_content:
        print("[Miner] ❌ Could not fetch environments.toml — check network")
        return 0

    environments = parse_environments_toml(toml_content)
    if not environments:
        print("[Miner] ❌ No environments parsed")
        return 0

    DB.init_db()
    stored = 0
    skipped = 0
    failed = 0

    for i, env in enumerate(environments, 1):
        path = env["path"]
        cves = env["cves"]
        tags = env["tags"]
        name = env.get("name", path)

        print(f"  [{i}/{len(environments)}] {path} | CVEs: {cves}")

        # Fetch docker-compose.yml
        compose_url = f"{GITHUB_RAW}/{path}/docker-compose.yml"
        compose_yml = fetch_text(compose_url)
        if not compose_yml:
            print(f"    ✗ No docker-compose.yml found")
            failed += 1
            time.sleep(REQUEST_DELAY)
            continue

        # Fetch Dockerfile (optional — not all have one at root)
        dockerfile_url = f"{GITHUB_RAW}/{path}/Dockerfile"
        dockerfile = fetch_text(dockerfile_url)

        port = extract_port_from_compose(compose_yml)

        for cve_id in cves:
            if dry_run:
                print(f"    [dry-run] Would store {cve_id} | port={port} | has_dockerfile={dockerfile is not None}")
                stored += 1
                continue

            # Check if already stored
            existing = DB.get_vulhub_recipe(cve_id)
            if existing:
                print(f"    ↷ {cve_id} already in DB, skipping")
                skipped += 1
                continue

            DB.store_vulhub_recipe(
                cve_id     = cve_id,
                path       = path,
                compose_yml= compose_yml,
                dockerfile = dockerfile or "",
                port       = port,
                tags       = tags,
            )
            print(f"    ✓ Stored {cve_id} (port={port})")
            stored += 1

        time.sleep(REQUEST_DELAY)

    print(f"\n[Miner] Done — stored={stored} skipped={skipped} failed={failed}")
    if not dry_run:
        print(f"[Miner] DB now has {DB.get_vulhub_count()} vulhub recipes")
    return stored


def mine_one(cve_id: str) -> bool:
    """Fetch and store a single CVE by ID."""
    cve_id = cve_id.upper()
    print(f"[Miner] Fetching single CVE: {cve_id}")

    toml_content = fetch_text(TOML_URL)
    if not toml_content:
        print("[Miner] ❌ Could not fetch environments.toml")
        return False

    environments = parse_environments_toml(toml_content)
    match = next((e for e in environments if cve_id in e.get("cves", [])), None)
    if not match:
        print(f"[Miner] ❌ {cve_id} not found in Vulhub")
        return False

    path = match["path"]
    compose_yml = fetch_text(f"{GITHUB_RAW}/{path}/docker-compose.yml")
    if not compose_yml:
        print(f"[Miner] ❌ No compose file for {path}")
        return False

    dockerfile = fetch_text(f"{GITHUB_RAW}/{path}/Dockerfile")
    port = extract_port_from_compose(compose_yml)

    DB.init_db()
    DB.store_vulhub_recipe(
        cve_id     = cve_id,
        path       = path,
        compose_yml= compose_yml,
        dockerfile = dockerfile or "",
        port       = port,
        tags       = match.get("tags", []),
    )
    print(f"[Miner] ✓ Stored {cve_id} from {path} (port={port})")
    return True


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mine Vulhub CVE recipes into DB")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be stored without writing")
    parser.add_argument("--cve",     type=str,            help="Fetch a single CVE only")
    parser.add_argument("--count",   action="store_true", help="Just print current DB count")
    args = parser.parse_args()

    if args.count:
        DB.init_db()
        print(f"Vulhub recipes in DB: {DB.get_vulhub_count()}")
        sys.exit(0)

    if args.cve:
        success = mine_one(args.cve)
        sys.exit(0 if success else 1)

    mine_all(dry_run=args.dry_run)
