"""
VulnForge - CTF Challenge Miner
================================
Mines Docker-based CTF challenges from three community repos:
  1. CTFTraining  — classic CTF competition challenges (git submodules)
  2. SniperOJ     — jeopardy-style web/pwn/misc challenges
  3. omega-coder  — dockerized web challenges

Usage:
    python ctf_miner.py                  # mine all three repos
    python ctf_miner.py --source sniperoj
    python ctf_miner.py --dry-run
    python ctf_miner.py --count
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

TIMEOUT = 15
REQUEST_DELAY = 0.4

HEADERS = {
    "User-Agent": "VulnForge-CTFMiner/1.0",
    "Accept": "application/vnd.github.v3+json",
}

# Repo definitions
REPOS = {
    "ctftraining": {
        "api": "https://api.github.com/repos/CTFTraining/CTFTraining/contents",
        "raw": "https://raw.githubusercontent.com/CTFTraining/CTFTraining/master",
        "submodule": True,  # uses git submodules — each challenge is a separate repo
    },
    "sniperoj": {
        "api": "https://api.github.com/repos/SniperOJ/Jeopardy-Dockerfiles/contents",
        "raw": "https://raw.githubusercontent.com/SniperOJ/Jeopardy-Dockerfiles/master",
        "subdirs": ["web"],   # only mine web challenges
        "submodule": False,
    },
    "omega-coder": {
        "api": "https://api.github.com/repos/omega-coder/dockerized-web-challenges/contents",
        "raw": "https://raw.githubusercontent.com/omega-coder/dockerized-web-challenges/master",
        "subdirs": None,  # challenges are at root level
        "submodule": False,
    },
}

# ─────────────────────────────────────────────
# VULNERABILITY TYPE INFERENCE
# ─────────────────────────────────────────────

VULN_PATTERNS = {
    "sqli":              r"sql.?inject|sqli|blind.?sql|union.?select|sql.?bypass",
    "xss":               r"\bxss\b|cross.?site.?script|reflected.?xss|stored.?xss",
    "ssti":              r"\bssti\b|server.?side.?template|template.?inject|jinja|twig",
    "rce":               r"\brce\b|remote.?code|command.?execut|code.?execut|eval.?inject",
    "command_injection": r"command.?inject|os.?command|ping.?inject|cmd.?inject",
    "deserialization":   r"deserializ|unserializ|object.?inject|phar.?deseri",
    "ssrf":              r"\bssrf\b|server.?side.?request",
    "lfi":               r"\blfi\b|local.?file.?inclu|path.?traversal|directory.?traversal",
    "file_upload":       r"file.?upload|unrestricted.?upload|webshell.?upload",
    "auth_bypass":       r"auth.?bypass|authentication.?bypass|login.?bypass",
    "nosql_injection":   r"nosql|mongo.?inject|nosequels",
    "xxe":               r"\bxxe\b|xml.?external.?entity",
    "php_tricks":        r"php.?weak|php.?type|php.?object|php.?exit|php.?key",
    "crypto":            r"crypto|hash.?crack|md5.?vs|base64.?trick",
}


def infer_vuln_types(name: str, description: str = "", tags: list = None) -> list:
    """Infer vulnerability types from the challenge name and description."""
    combined = f"{name} {description} {' '.join(tags or [])}".lower()
    found = []
    for vuln_type, pattern in VULN_PATTERNS.items():
        if re.search(pattern, combined, re.IGNORECASE):
            found.append(vuln_type)
    if not found:
        # Fallback: try to infer from common challenge name patterns
        if any(x in combined for x in ["inject", "injection"]):
            found.append("sqli")
        elif any(x in combined for x in ["eval", "exec", "shell"]):
            found.append("rce")
        elif any(x in combined for x in ["upload"]):
            found.append("file_upload")
        else:
            found.append("web")  # generic web challenge
    return found


def infer_difficulty(name: str) -> str:
    """Guess difficulty from challenge name patterns."""
    lower = name.lower()
    if any(x in lower for x in ["baby", "easy", "simple", "basic", "beginner"]):
        return "easy"
    if any(x in lower for x in ["hard", "revenge", "advanced", "expert"]):
        return "hard"
    return "medium"


def slugify(text: str) -> str:
    """Convert a name into a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\-_]', '-', text)
    text = re.sub(r'-+', '-', text).strip('-')
    return text


# ─────────────────────────────────────────────
# FETCH HELPERS
# ─────────────────────────────────────────────

def fetch_json(url: str) -> list | dict | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 403:
            print(f"  [warn] GitHub rate limit — wait or use GITHUB_TOKEN")
        elif resp.status_code != 404:
            print(f"  [warn] {url} → {resp.status_code}")
        return None
    except Exception as e:
        print(f"  [warn] fetch {url}: {e}")
        return None


def fetch_text(url: str) -> str | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            return resp.text
        return None
    except Exception:
        return None


def extract_port_from_compose(compose_yml: str) -> int:
    """Parse the host port from docker-compose.yml."""
    m = re.search(r'[\"\s\-]+(\d{2,5}):(\d+)', compose_yml)
    if m:
        return int(m.group(1))
    return 80


# ─────────────────────────────────────────────
# MINER: CTFTraining (git submodules)
# ─────────────────────────────────────────────

def mine_ctftraining(dry_run: bool = False) -> int:
    """
    CTFTraining uses git submodules. The main repo has a .gitmodules file
    pointing to individual repos like CTFTraining/wdb_2018_comment.
    Each sub-repo has its own docker-compose.yml.
    """
    print(f"\n[CTFTraining] Mining git submodules...")

    # Fetch .gitmodules to find all challenge repos
    gitmodules_url = f"{REPOS['ctftraining']['raw']}/.gitmodules"
    content = fetch_text(gitmodules_url)
    if not content:
        print("[CTFTraining] ❌ Could not fetch .gitmodules")
        return 0

    # Parse submodule entries
    submodules = re.findall(
        r'\[submodule\s+"([^"]+)"\]\s*path\s*=\s*(\S+)\s*url\s*=\s*(\S+)',
        content
    )
    print(f"[CTFTraining] Found {len(submodules)} submodules")

    stored = 0
    for name, path, url in submodules:
        challenge_id = f"ctftraining-{slugify(name)}"

        if not dry_run:
            existing = DB.get_ctf_challenge(challenge_id)
            if existing:
                continue

        # Extract org/repo from URL
        match = re.search(r'github\.com/([^/]+/[^/]+?)(?:\.git)?$', url)
        if not match:
            continue
        repo_full = match.group(1)

        # Fetch docker-compose.yml from the sub-repo
        compose_url = f"https://raw.githubusercontent.com/{repo_full}/master/docker-compose.yml"
        compose_yml = fetch_text(compose_url)
        if not compose_yml:
            compose_url = f"https://raw.githubusercontent.com/{repo_full}/main/docker-compose.yml"
            compose_yml = fetch_text(compose_url)

        if not compose_yml:
            continue

        dockerfile_url = f"https://raw.githubusercontent.com/{repo_full}/master/Dockerfile"
        dockerfile = fetch_text(dockerfile_url) or ""

        port = extract_port_from_compose(compose_yml)
        vuln_types = infer_vuln_types(name)
        difficulty = infer_difficulty(name)

        if dry_run:
            print(f"  [dry-run] {challenge_id} | vulns={vuln_types} | port={port}")
            stored += 1
            continue

        DB.store_ctf_challenge(
            challenge_id=challenge_id,
            name=name,
            source="ctftraining",
            repo_path=repo_full,
            category="web",
            vuln_types=vuln_types,
            description=f"CTF Training challenge: {name}",
            compose_yml=compose_yml,
            dockerfile=dockerfile,
            port=port,
            difficulty=difficulty,
            tags=["ctf", "competition", "ctftraining"],
        )
        print(f"  ✓ {challenge_id} (port={port}, vulns={vuln_types})")
        stored += 1
        time.sleep(REQUEST_DELAY)

    print(f"[CTFTraining] Stored {stored} challenges")
    return stored


# ─────────────────────────────────────────────
# MINER: SniperOJ
# ─────────────────────────────────────────────

def mine_sniperoj(dry_run: bool = False) -> int:
    """Mine web challenges from SniperOJ/Jeopardy-Dockerfiles."""
    print(f"\n[SniperOJ] Mining web challenges...")

    api_base = REPOS["sniperoj"]["api"]
    raw_base = REPOS["sniperoj"]["raw"]
    stored = 0

    for subdir in REPOS["sniperoj"]["subdirs"]:
        entries = fetch_json(f"{api_base}/{subdir}")
        if not entries:
            print(f"[SniperOJ] ❌ Could not list {subdir}/")
            continue

        dirs = [e for e in entries if e.get("type") == "dir"]
        print(f"[SniperOJ] Found {len(dirs)} challenges in {subdir}/")

        for entry in dirs:
            name = entry["name"]
            path = entry["path"]
            challenge_id = f"sniperoj-{slugify(name)}"

            if not dry_run:
                existing = DB.get_ctf_challenge(challenge_id)
                if existing:
                    continue

            # Try docker-compose.yml first, then Dockerfile
            compose_yml = fetch_text(f"{raw_base}/{path}/docker-compose.yml") or ""
            dockerfile = fetch_text(f"{raw_base}/{path}/Dockerfile") or ""

            if not compose_yml and not dockerfile:
                continue  # no deployable config

            port = extract_port_from_compose(compose_yml) if compose_yml else 80
            vuln_types = infer_vuln_types(name)
            difficulty = infer_difficulty(name)

            if dry_run:
                print(f"  [dry-run] {challenge_id} | vulns={vuln_types}")
                stored += 1
                continue

            DB.store_ctf_challenge(
                challenge_id=challenge_id,
                name=name,
                source="sniperoj",
                repo_path=path,
                category="web",
                vuln_types=vuln_types,
                description=f"SniperOJ Jeopardy challenge: {name}",
                compose_yml=compose_yml,
                dockerfile=dockerfile,
                port=port,
                difficulty=difficulty,
                tags=["ctf", "jeopardy", "sniperoj"],
            )
            print(f"  ✓ {challenge_id} (port={port}, vulns={vuln_types})")
            stored += 1
            time.sleep(REQUEST_DELAY)

    print(f"[SniperOJ] Stored {stored} challenges")
    return stored


# ─────────────────────────────────────────────
# MINER: omega-coder
# ─────────────────────────────────────────────

def mine_omega_coder(dry_run: bool = False) -> int:
    """Mine web challenges from omega-coder/dockerized-web-challenges."""
    print(f"\n[omega-coder] Mining web challenges...")

    api_base = REPOS["omega-coder"]["api"]
    raw_base = REPOS["omega-coder"]["raw"]
    stored = 0

    entries = fetch_json(api_base)
    if not entries:
        print("[omega-coder] ❌ Could not list repo")
        return 0

    dirs = [e for e in entries if e.get("type") == "dir"]
    print(f"[omega-coder] Found {len(dirs)} challenges")

    for entry in dirs:
        name = entry["name"]
        path = entry["path"]
        challenge_id = f"omega-{slugify(name)}"

        if not dry_run:
            existing = DB.get_ctf_challenge(challenge_id)
            if existing:
                continue

        compose_yml = fetch_text(f"{raw_base}/{path}/docker-compose.yml") or ""
        dockerfile = fetch_text(f"{raw_base}/{path}/Dockerfile") or ""

        if not compose_yml and not dockerfile:
            continue

        port = extract_port_from_compose(compose_yml) if compose_yml else 80
        vuln_types = infer_vuln_types(name)
        difficulty = infer_difficulty(name)

        if dry_run:
            print(f"  [dry-run] {challenge_id} | vulns={vuln_types}")
            stored += 1
            continue

        DB.store_ctf_challenge(
            challenge_id=challenge_id,
            name=name,
            source="omega-coder",
            repo_path=path,
            category="web",
            vuln_types=vuln_types,
            description=f"Dockerized web challenge: {name}",
            compose_yml=compose_yml,
            dockerfile=dockerfile,
            port=port,
            difficulty=difficulty,
            tags=["ctf", "web", "omega-coder"],
        )
        print(f"  ✓ {challenge_id} (port={port}, vulns={vuln_types})")
        stored += 1
        time.sleep(REQUEST_DELAY)

    print(f"[omega-coder] Stored {stored} challenges")
    return stored


# ─────────────────────────────────────────────
# MINER: VulApps (Dockerfile-only → compose wrapper)
# ─────────────────────────────────────────────

# VulApps app letter → full app name mapping
VULAPPS_APPS = {
    "b/bash": "bash",
    "c/cisco": "cisco",
    "c/cmseasy": "cmseasy",
    "d/drupal": "drupal",
    "g/git": "git",
    "i/imagemagick": "imagemagick",
    "j/jboss": "jboss",
    "j/jenkins": "jenkins",
    "j/joomla": "joomla",
    "m/memcached": "memcached",
    "n/nagios": "nagios",
    "n/nodejs": "nodejs",
    "n/nginx": "nginx",
    "o/openssl": "openssl",
    "p/phpmailer": "phpmailer",
    "r/redis": "redis",
    "s/samba": "samba",
    "s/shiro": "shiro",
    "s/spring": "spring",
    "s/springboot": "springboot",
    "s/struts2": "struts2",
    "s/springwebflow": "springwebflow",
    "s/supervisor": "supervisor",
    "t/tomcat": "tomcat",
    "w/wordpress": "wordpress",
    "z/zabbix": "zabbix",
}

# Port defaults by app type (from VulApps README patterns)
VULAPPS_PORTS = {
    "struts2": 8080, "tomcat": 8080, "jboss": 8080, "spring": 8080,
    "springboot": 8080, "springwebflow": 8080, "jenkins": 8080,
    "wordpress": 80, "drupal": 80, "joomla": 80, "cmseasy": 80,
    "nginx": 80, "nagios": 80, "zabbix": 80, "phpmailer": 80,
    "nodejs": 3000, "redis": 6379, "memcached": 11211,
    "supervisor": 9001,
}


def extract_port_from_readme(readme: str, app_name: str) -> int:
    """Parse port from VulApps README (e.g. '-p 80:8080')."""
    m = re.search(r'-p\s+\d+:(\d+)', readme)
    if m:
        return int(m.group(1))
    return VULAPPS_PORTS.get(app_name, 80)


def generate_compose_from_image(image_tag: str, port: int) -> str:
    """Generate a minimal docker-compose.yml from a DockerHub image tag."""
    return f"""version: '2'
services:
  vulapps:
    image: {image_tag}
    ports:
      - "{port}"
"""


def mine_vulapps(dry_run: bool = False) -> int:
    """
    Mine vulnerable Docker environments from Medicean/VulApps.
    VulApps uses Dockerfiles that reference pre-built DockerHub images.
    We generate docker-compose.yml wrappers for each.
    """
    print(f"\n[VulApps] Mining Dockerfile-based environments...")

    api_base = "https://api.github.com/repos/Medicean/VulApps/contents"
    raw_base = "https://raw.githubusercontent.com/Medicean/VulApps/master"
    stored = 0

    for app_path, app_name in VULAPPS_APPS.items():
        print(f"\n  [{app_name}] Checking {app_path}/...")
        entries = fetch_json(f"{api_base}/{app_path}")
        if not entries:
            print(f"  [{app_name}] Could not list")
            continue

        # Get sub-vulnerability directories
        vuln_dirs = [e for e in entries if e.get("type") == "dir"]
        if not vuln_dirs:
            continue

        for vuln_entry in vuln_dirs:
            vuln_name = vuln_entry["name"]
            vuln_path = vuln_entry["path"]
            challenge_id = f"vulapps-{slugify(app_name)}-{slugify(vuln_name)}"

            if not dry_run:
                existing = DB.get_ctf_challenge(challenge_id)
                if existing:
                    continue

            # Fetch the Dockerfile
            dockerfile = fetch_text(f"{raw_base}/{vuln_path}/Dockerfile")
            if not dockerfile:
                continue

            # Extract the DockerHub image from the Dockerfile
            # Pattern: FROM medicean/vulapps:tag or FROM someimage:tag
            from_match = re.search(r'^FROM\s+(\S+)', dockerfile, re.MULTILINE)
            if not from_match:
                continue
            image_tag = from_match.group(1)

            # Fetch README for port info and description
            readme = fetch_text(f"{raw_base}/{vuln_path}/README.md") or ""
            port = extract_port_from_readme(readme, app_name)

            # Generate a compose wrapper around the Docker image
            compose_yml = generate_compose_from_image(image_tag, port)

            # Infer vuln type from app name + vuln name
            vuln_types = infer_vuln_types(
                f"{app_name} {vuln_name}",
                description=readme[:500]
            )
            difficulty = infer_difficulty(vuln_name)
            display_name = f"{app_name}/{vuln_name}"

            if dry_run:
                print(f"    [dry-run] {challenge_id} | image={image_tag} | port={port} | vulns={vuln_types}")
                stored += 1
                continue

            DB.store_ctf_challenge(
                challenge_id=challenge_id,
                name=display_name,
                source="vulapps",
                repo_path=vuln_path,
                category="web",
                vuln_types=vuln_types,
                description=f"VulApps {app_name} vulnerability: {vuln_name}",
                compose_yml=compose_yml,
                dockerfile=dockerfile,
                port=port,
                difficulty=difficulty,
                tags=["vulapps", app_name, "cve-env"],
            )
            print(f"    + {challenge_id} (image={image_tag}, port={port})")
            stored += 1
            time.sleep(REQUEST_DELAY)

    print(f"\n[VulApps] Stored {stored} challenges")
    return stored


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def mine_all(dry_run: bool = False) -> int:
    DB.init_db()
    total = 0
    total += mine_ctftraining(dry_run)
    total += mine_sniperoj(dry_run)
    total += mine_omega_coder(dry_run)
    total += mine_vulapps(dry_run)
    if not dry_run:
        print(f"\n[CTF Miner] Total: {total} new challenges stored")
        print(f"[CTF Miner] DB now has {DB.get_ctf_count()} CTF challenges")
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mine CTF challenges into DB")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--source", choices=["ctftraining", "sniperoj", "omega-coder", "vulapps"])
    parser.add_argument("--count", action="store_true")
    args = parser.parse_args()

    if args.count:
        DB.init_db()
        for src in ["ctftraining", "sniperoj", "omega-coder", "vulapps"]:
            print(f"  {src}: {DB.get_ctf_count(src)}")
        print(f"  total: {DB.get_ctf_count()}")
        sys.exit(0)

    if args.source:
        DB.init_db()
        miners = {
            "ctftraining": mine_ctftraining,
            "sniperoj": mine_sniperoj,
            "omega-coder": mine_omega_coder,
            "vulapps": mine_vulapps,
        }
        miners[args.source](dry_run=args.dry_run)
    else:
        mine_all(dry_run=args.dry_run)

