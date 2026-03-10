"""
VulnForge - NVD CVE Enrichment
===============================
Enriches the kve.json knowledge base with NVD metadata for all Vulhub recipes.
This gives richer descriptions, CWE IDs, and CVSS scores for better semantic search.

Usage:
    python enrich_cves.py            # enrich all Vulhub CVEs
    python enrich_cves.py --dry-run  # preview without writing
    python enrich_cves.py --output kve_enriched.json
"""

import json
import re
import sys
import time
import argparse
import requests
from pathlib import Path

import vfdb as DB

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
KVE_FILE = Path(__file__).parent / "kve.json"
OUTPUT_FILE = Path(__file__).parent / "kve_enriched.json"
TIMEOUT = 12
# NVD allows ~5 req/30s unauthenticated, or 50 req/30s with API key
NVD_DELAY = 6.5   # seconds between requests (conservative, no API key)

HEADERS = {"User-Agent": "VulnForge-Enricher/1.0"}


# ─────────────────────────────────────────────
# NVD FETCH
# ─────────────────────────────────────────────

def fetch_nvd_cve(cve_id: str) -> dict | None:
    """Fetch a single CVE from NVD API 2.0."""
    try:
        resp = requests.get(
            NVD_API, params={"cveId": cve_id},
            headers=HEADERS, timeout=TIMEOUT
        )
        if resp.status_code == 200:
            data = resp.json()
            vulns = data.get("vulnerabilities", [])
            if vulns:
                return vulns[0].get("cve", {})
        elif resp.status_code == 403:
            print(f"  [warn] NVD rate limit — increase delay or use API key")
            time.sleep(30)
        else:
            print(f"  [warn] NVD {cve_id}: HTTP {resp.status_code}")
        return None
    except Exception as e:
        print(f"  [warn] NVD {cve_id}: {e}")
        return None


def extract_nvd_metadata(nvd_cve: dict) -> dict:
    """Extract useful metadata from NVD CVE response."""
    result = {}

    # Description
    descs = nvd_cve.get("descriptions", [])
    for d in descs:
        if d.get("lang") == "en":
            result["nvd_description"] = d.get("value", "")
            break

    # CWEs
    cwes = []
    for weakness in nvd_cve.get("weaknesses", []):
        for desc in weakness.get("description", []):
            cwe_val = desc.get("value", "")
            if cwe_val.startswith("CWE-"):
                cwes.append(cwe_val)
    result["cwes"] = list(set(cwes))

    # CVSS score
    metrics = nvd_cve.get("metrics", {})
    for version_key in ["cvssMetricV31", "cvssMetricV30", "cvssMetricV2"]:
        metric_list = metrics.get(version_key, [])
        if metric_list:
            cvss_data = metric_list[0].get("cvssData", {})
            result["cvss_score"] = cvss_data.get("baseScore")
            result["cvss_severity"] = cvss_data.get("baseSeverity", "")
            result["cvss_vector"] = cvss_data.get("vectorString", "")
            break

    # Affected products from CPE
    products = []
    for cfg in nvd_cve.get("configurations", []):
        for node in cfg.get("nodes", []):
            for cpe_match in node.get("cpeMatch", []):
                cpe = cpe_match.get("criteria", "")
                parts = cpe.split(":")
                if len(parts) >= 5:
                    vendor = parts[3]
                    product = parts[4]
                    if vendor != "*" and product != "*":
                        products.append(f"{vendor}/{product}")
    result["affected_products"] = list(set(products))[:5]

    # Published date
    result["published"] = nvd_cve.get("published", "")

    return result


# ─────────────────────────────────────────────
# ENRICHMENT
# ─────────────────────────────────────────────

def enrich(output_path: str = None, dry_run: bool = False) -> int:
    """Main enrichment: merge Vulhub CVEs + NVD metadata into kve.json"""
    DB.init_db()

    # Load existing kve.json
    try:
        with open(KVE_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        existing = raw if isinstance(raw, list) else raw.get("vulnerabilities", [])
    except (FileNotFoundError, json.JSONDecodeError):
        existing = []

    # Build lookup from existing entries
    lookup = {}
    for entry in existing:
        _id = entry.get("cveID", "")
        m = re.search(r'(CVE-\d{4}-\d+)', _id, re.IGNORECASE)
        if m:
            lookup[m.group(1).upper()] = entry

    print(f"[Enrich] Existing kve.json: {len(lookup)} entries")

    # Get all Vulhub CVEs not already in kve.json
    with DB.get_db() as db:
        rows = db.execute("SELECT cve_id, path, tags FROM vulhub_recipes").fetchall()

    missing = []
    for row in rows:
        cve_id = row["cve_id"]
        if cve_id not in lookup:
            missing.append(dict(row))

    print(f"[Enrich] Vulhub CVEs not in kve.json: {len(missing)}")
    if not missing:
        print("[Enrich] ✅ All Vulhub CVEs already in kve.json")
        return 0

    enriched_count = 0
    for i, row in enumerate(missing, 1):
        cve_id = row["cve_id"]
        path = row["path"]
        tags = json.loads(row.get("tags") or "[]")
        software = path.split("/")[0] if "/" in path else path

        print(f"  [{i}/{len(missing)}] {cve_id}...", end=" ", flush=True)

        if dry_run:
            print("[dry-run]")
            enriched_count += 1
            continue

        # Fetch NVD data
        nvd_cve = fetch_nvd_cve(cve_id)
        nvd_meta = extract_nvd_metadata(nvd_cve) if nvd_cve else {}

        # Build enriched entry
        entry = {
            "cveID": cve_id,
            "vendorProject": software.title(),
            "product": software,
            "vulnerabilityName": f"{software.title()} {cve_id}",
            "shortDescription": nvd_meta.get("nvd_description", f"{software.title()} vulnerability ({cve_id})"),
            "dateAdded": nvd_meta.get("published", "")[:10],
            "notes": "",
            "cwes": nvd_meta.get("cwes", []),
            "vulhub_path": path,
            "tier": "1",
            "source": "vulhub+nvd",
        }

        if nvd_meta.get("cvss_score"):
            entry["cvss_score"] = nvd_meta["cvss_score"]
            entry["cvss_severity"] = nvd_meta.get("cvss_severity", "")

        if nvd_meta.get("affected_products"):
            entry["affected_products"] = nvd_meta["affected_products"]

        lookup[cve_id] = entry
        enriched_count += 1
        print(f"✓ ({nvd_meta.get('cvss_score', '?')})")

        time.sleep(NVD_DELAY)

    # Write the enriched file
    if not dry_run:
        out_path = Path(output_path) if output_path else OUTPUT_FILE
        all_entries = list(lookup.values())
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(all_entries, f, indent=2, ensure_ascii=False)
        print(f"\n[Enrich] ✅ Written {len(all_entries)} entries to {out_path}")

    return enriched_count


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich CVE database with NVD metadata")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=str, default=None, help="Output file path")
    args = parser.parse_args()

    enrich(output_path=args.output, dry_run=args.dry_run)
