import os, sys, re, json, time, uuid, argparse, socket
import yaml
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv
import vfdb as DB

# Load .env from the project root (three levels up: core/ → Project/)
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

# ── CONFIG ────────────────────────────────────────────────────────────────────
GROQ_API_KEY    = os.environ.get("GROQ_API_KEY_1")
GENERATOR_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct"
OUTPUT_BASE     = Path("generated_machines")
POLL_INTERVAL   = 6
# Public host used to build the lab access URL exposed to users
_SERVER_HOST    = os.environ.get("SERVER_HOST", "http://localhost").rstrip("/")
groq_client     = Groq(api_key=GROQ_API_KEY)

# ── MySQL registration helper ─────────────────────────────────────────────────
# Resolve the path to database.py so bridge.py can write the completed machine
# into MySQL. We search parent directories for the database module.
# If MySQL is unreachable for any reason the job is still marked done in vfdb
# — the except block ensures bridge.py never crashes because of this.
_DB_SEARCH_PATHS = [
    Path(__file__).resolve().parent,                   # same dir as bridge.py
    Path(__file__).resolve().parents[1],               # one level up
    Path(__file__).resolve().parents[1] / "forge",     # ../forge/
    Path(__file__).resolve().parents[1] / "web" / "api",
    Path(os.environ.get("DATABASE_MODULE_PATH", "")),  # explicit override via env
]

def _setup_mysql_path() -> bool:
    """Add the directory containing database.py to sys.path. Returns True if found."""
    for p in _DB_SEARCH_PATHS:
        if p and (p / "database.py").exists():
            if str(p) not in sys.path:
                sys.path.insert(0, str(p))
            return True
    return False

_mysql_path_ready = _setup_mysql_path()


def _register_machine_in_mysql(manifest: dict, job: dict) -> None:
    """
    Write a permanent record to MySQL generated_machines table.

    This is a best-effort call — it is always wrapped in try/except so a
    MySQL failure never prevents bridge.py from marking the vfdb job done.

    Args:
        manifest: the dict written to manifest.json by process_job
        job:      the vfdb job dict (contains id, student_id, campaign_id, etc.)
    """
    try:
        from database import get_db
        mysql_db = get_db()
        mysql_db.register_generated_machine({
            "machine_id":    manifest["machine_id"],
            "job_id":        manifest["job_id"],
            "user_id":       job.get("student_id"),       # vfdb field name
            "cve_id":        manifest["cve_id"],
            "difficulty":    manifest["difficulty"],
            "port":          manifest["port"],
            "access_url":    manifest["access_url"],
            "machine_dir":   str(OUTPUT_BASE / manifest["machine_id"]),
            "service_name":  manifest["service_name"],
            "flag_location": manifest["flag_location"],
            "flag_content":  manifest["flag_content"],
        })
        print(f"  [MySQL] Machine registered: {manifest['machine_id']}")
    except Exception as e:
        # Never crash bridge.py due to a MySQL issue
        print(f"  [MySQL] Warning — could not register machine in MySQL: {e}")
        print(f"  [MySQL] The machine files are intact; the Machines tab will")
        print(f"  [MySQL] not show this machine until MySQL is reachable.")


# ══════════════════════════════════════════════════════════════════════════════
#  YAML GROUND TRUTH PARSER
# ══════════════════════════════════════════════════════════════════════════════

INFRA_SERVICES = {"db", "mysql", "postgres", "postgresql", "redis", "mongo",
                  "mongodb", "zookeeper", "kafka", "elasticsearch", "memcached",
                  "rabbitmq", "mariadb", "influxdb", "cassandra", "etcd"}

def sanitize_compose_yml(raw: str) -> str:
    raw = re.sub(r'\$\{[^}]+:-([^}]*)\}', r'\1', raw)
    raw = re.sub(r'\$\{[^}]+\}', 'PLACEHOLDER', raw)
    raw = re.sub(r'\$([A-Z_][A-Z0-9_]*)', 'PLACEHOLDER', raw)
    return raw


def parse_compose_ground_truth(compose_yml: str) -> dict:
    clean = sanitize_compose_yml(compose_yml)
    try:
        parsed = yaml.safe_load(clean) or {}
    except yaml.YAMLError as e:
        print(f"  [YAML] Parse error after sanitize: {e} — using empty ground truth")
        return {"services": {}, "main_service": None, "all_service_names": set()}

    services_raw = parsed.get("services", {}) or {}
    services = {}

    for name, cfg in services_raw.items():
        cfg = cfg or {}
        ports_host      = []
        ports_container = []
        for p in cfg.get("ports", []):
            p_str = str(p)
            parts = p_str.split(":")
            if len(parts) == 2:
                try:
                    ports_host.append(int(parts[0]))
                    ports_container.append(int(parts[1]))
                except ValueError:
                    pass
            elif len(parts) == 1:
                try:
                    ports_container.append(int(parts[0]))
                    ports_host.append(int(parts[0]))
                except ValueError:
                    pass

        services[name] = {
            "image":           cfg.get("image", ""),
            "has_build":       "build" in cfg,
            "ports_host":      ports_host,
            "ports_container": ports_container,
        }

    all_names = set(services.keys())

    main_service = None
    for name in services:
        if name.lower() not in INFRA_SERVICES:
            main_service = name
            break
    if not main_service and services:
        main_service = next(iter(services))

    print(f"  [GT] services={list(all_names)} main={main_service}")

    return {
        "services":          services,
        "main_service":      main_service,
        "all_service_names": all_names,
        "parsed":            parsed,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  AI CALLS
# ══════════════════════════════════════════════════════════════════════════════

def call_ai_json(prompt: str, label: str, max_tokens: int = 1024) -> dict:
    for attempt in range(3):
        try:
            completion = groq_client.chat.completions.create(
                model=GENERATOR_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_completion_tokens=max_tokens,
                top_p=1,
                stream=True,
                stop=None,
            )
            raw = ""
            for chunk in completion:
                raw += chunk.choices[0].delta.content or ""

            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
            raw = re.sub(r"^```[\w\-]*\n?", "", raw, flags=re.MULTILINE)
            raw = re.sub(r"\n?```\s*$",      "", raw, flags=re.MULTILINE)
            raw = raw.strip()

            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                if m:
                    try:
                        return json.loads(m.group(0))
                    except Exception:
                        pass
            print(f"  [AI] {label} JSON parse failed — raw: {raw[:200]}")
            return {}

        except Exception as e:
            err = str(e)
            if ("rate_limit" in err.lower() or "429" in err) and attempt < 2:
                print(f"  [AI] Rate limit on {label}, retrying...")
                time.sleep(15 * (attempt + 1))
            else:
                print(f"  [AI] {label} error: {err[:100]}")
                return {}
    return {}


def fetch_vulhub_readme(vulhub_path: str) -> str:
    import requests
    url = f"https://raw.githubusercontent.com/vulhub/vulhub/master/{vulhub_path}/README.md"
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "VulnForge/1.0"})
        if resp.status_code == 200:
            text = resp.text.strip()[:3000]
            print(f"  [README] fetched {len(text)} chars")
            return text
        return ""
    except Exception as e:
        print(f"  [README] fetch error: {e}")
        return ""


# ══════════════════════════════════════════════════════════════════════════════
#  FLAG ANALYSIS — only AI decision in this pipeline
# ══════════════════════════════════════════════════════════════════════════════

def analyze_compose_for_flag(compose_yml: str, cve_id: str, difficulty: str,
                              gt: dict, readme: str = "") -> dict:
    readme_block = f"\nVulhub README:\n{readme}" if readme else ""
    service_list = ", ".join(gt["all_service_names"]) or "unknown"

    result = call_ai_json(f"""You are setting up a CTF lab. Decide where to place flag.txt inside the main vulnerable container.

CVE: {cve_id}
Difficulty: {difficulty}
Services in this compose: {service_list}

docker-compose.yml:
{compose_yml}
{readme_block}

Scale flag placement to difficulty:
- easy: obvious, readable by anyone (e.g. /flag.txt)
- medium: inside the app's real working directory (e.g. /opt/activemq/flag.txt)
- hard: requires privilege to read (e.g. /root/flag.txt, permission 400)

Return ONLY this JSON:
{{
  "service_name": "pick from: {service_list}",
  "base_image": "exact image tag from compose",
  "flag_location": "/full/path/flag.txt",
  "flag_permission": "644 or 400"
}}""", "flag_analysis")

    if not result:
        result = {}

    all_names    = gt["all_service_names"]
    main_service = gt["main_service"]

    # Validate service_name
    svc = result.get("service_name", "")
    if svc not in all_names:
        print(f"  [FLAG] AI service '{svc}' not in compose — using '{main_service}'")
        svc = main_service
    result["service_name"] = svc

    # Always use real image from ground truth
    if svc and svc in gt["services"]:
        real_image = gt["services"][svc].get("image", "")
        if real_image and real_image != "PLACEHOLDER":
            result["base_image"] = real_image

    # Defaults
    if not result.get("flag_location"):
        defaults = {"easy": "/flag.txt", "medium": "/app/flag.txt", "hard": "/root/flag.txt"}
        result["flag_location"] = defaults.get(difficulty, "/flag.txt")

    loc = result["flag_location"]
    if not loc.startswith("/"):
        result["flag_location"] = "/" + loc

    perm = str(result.get("flag_permission", "644"))
    if perm not in ("644", "640", "600", "400"):
        perm = "400" if difficulty == "hard" else "644"
    result["flag_permission"] = perm

    print(f"  [FLAG] svc={result['service_name']} loc={result['flag_location']} perm={result['flag_permission']}")
    return result


def validate_flag_placement(flag_analysis: dict, gt: dict) -> dict:
    """Sanity-check AI's flag placement against compose ground truth."""
    svc = flag_analysis.get("service_name", "")
    loc = flag_analysis.get("flag_location", "/flag.txt")

    # Validate service exists in compose
    if svc and svc not in gt["all_service_names"]:
        old_svc = svc
        svc = gt["main_service"]
        flag_analysis["service_name"] = svc
        print(f"  [VALIDATE] Service '{old_svc}' not in compose — using '{svc}'")

    # Validate flag path doesn't conflict with volume mounts
    if svc and svc in gt.get("services", {}):
        svc_cfg = gt["services"][svc]
        # If there's a build context, prefer /app or /opt paths for medium
        if svc_cfg.get("has_build") and loc == "/flag.txt":
            flag_analysis["flag_location"] = "/app/flag.txt"
            print(f"  [VALIDATE] Adjusted flag path to /app/flag.txt (service has build context)")

    # Ensure path starts with /
    if not flag_analysis["flag_location"].startswith("/"):
        flag_analysis["flag_location"] = "/" + flag_analysis["flag_location"]

    return flag_analysis


# ══════════════════════════════════════════════════════════════════════════════
#  DOCKERFILE + EXTRA FILES
# ══════════════════════════════════════════════════════════════════════════════

def fetch_vulhub_file(vulhub_path: str, filename: str) -> bytes | None:
    import requests
    url = f"https://raw.githubusercontent.com/vulhub/vulhub/master/{vulhub_path}/{filename}"
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "VulnForge/1.0"})
        if resp.status_code == 200:
            print(f"  [FETCH] {filename} ({len(resp.content)} bytes)")
            return resp.content
        print(f"  [FETCH] {filename} not found ({resp.status_code})")
        return None
    except Exception as e:
        print(f"  [FETCH] {filename} error: {e}")
        return None


def build_dockerfile(vulhub_path: str) -> str:
    raw = fetch_vulhub_file(vulhub_path, "Dockerfile") if vulhub_path else None
    if raw:
        print(f"  [DOCKERFILE] Fetched ({len(raw)} bytes)")
        return raw.decode("utf-8", errors="replace")
    print(f"  [DOCKERFILE] Not found upstream")
    return ""


def fetch_vulhub_dir_files(vulhub_path: str, machine_dir: Path,
                            exclude: set[str] | None = None) -> list[str]:
    import requests
    exclude = (exclude or set()) | {"Dockerfile", "docker-compose.yml", "README.md", "README.zh-cn.md"}

    api_url = f"https://api.github.com/repos/vulhub/vulhub/contents/{vulhub_path}"
    try:
        resp = requests.get(api_url, timeout=10, headers={"User-Agent": "VulnForge/1.0"})
        if resp.status_code != 200:
            print(f"  [DIR] GitHub API error {resp.status_code}")
            return []
        entries = resp.json()
    except Exception as e:
        print(f"  [DIR] GitHub API error: {e}")
        return []

    fetched = []
    for entry in entries:
        if entry.get("type") != "file":
            continue
        name = entry["name"]
        if name in exclude:
            continue
        data = fetch_vulhub_file(vulhub_path, name)
        if data is not None:
            (machine_dir / name).write_bytes(data)
            fetched.append(name)
    return fetched


def fetch_compose_extra_files(vulhub_path: str, parsed_compose: dict,
                               machine_dir: Path) -> list[str]:
    to_fetch: set[str] = set()
    fetched_all: list[str] = []
    services = parsed_compose.get("services", {}) or {}
    has_whole_dir_mount = False

    for svc_name, cfg in services.items():
        cfg = cfg or {}
        for vol in cfg.get("volumes", []):
            parts = str(vol).split(":")
            if len(parts) < 2:
                continue
            host_part = parts[0].strip()
            if host_part in (".", "./"):
                has_whole_dir_mount = True
                continue
            if not host_part.startswith("./"):
                continue
            rel_path = host_part[2:]
            if not Path(rel_path).suffix:
                continue
            to_fetch.add(rel_path)

    if has_whole_dir_mount:
        print(f"  [EXTRA] Whole-dir mount — fetching all vulhub files")
        all_files = fetch_vulhub_dir_files(vulhub_path, machine_dir)
        fetched_all.extend(all_files)

    dockerfile_path = machine_dir / "Dockerfile"
    if dockerfile_path.exists():
        for line in dockerfile_path.read_text(errors="replace").splitlines():
            stripped = line.strip()
            if not stripped.upper().startswith(("COPY ", "ADD ")):
                continue
            tokens = [t for t in stripped.split()[1:] if not t.startswith("--")]
            for src in tokens[:-1]:
                if src.startswith("http") or src.startswith("/") or src in (".", "*"):
                    continue
                if Path(src).suffix or src in (
                    "Makefile", "requirements.txt", "package.json",
                    "pom.xml", "build.gradle", "build.xml", "setup.py",
                    "Gemfile", "composer.json", "go.mod",
                ):
                    to_fetch.add(src)

    for rel_path in sorted(to_fetch):
        if rel_path in fetched_all:
            continue
        data = fetch_vulhub_file(vulhub_path, rel_path)
        if data is not None:
            dest = machine_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            fetched_all.append(rel_path)

    return fetched_all


# ══════════════════════════════════════════════════════════════════════════════
#  PORT AVAILABILITY CHECK
# ══════════════════════════════════════════════════════════════════════════════

def is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def get_free_port(start_port: int, max_attempts: int = 20) -> int:
    port = start_port
    for _ in range(max_attempts):
        if is_port_free(port):
            return port
        print(f"  [PORT] {port} in use — trying next")
        port = DB.get_next_port()
    raise RuntimeError(f"Could not find a free port after {max_attempts} attempts")


# ══════════════════════════════════════════════════════════════════════════════
#  COMPOSE PATCHER
# ══════════════════════════════════════════════════════════════════════════════

def patch_compose(gt: dict, svc_name: str, host_port: int,
                  flag_location: str = "/flag.txt",
                  flag_permission: str = "644",
                  has_dockerfile: bool = True,
                  job_id: str = "") -> str:
    try:
        import copy
        parsed   = copy.deepcopy(gt["parsed"])
        services = parsed.get("services", {})
        parsed.pop("version", None)

        if svc_name not in services:
            svc_name = gt["main_service"]
            print(f"  [PATCH] Falling back to main service: '{svc_name}'")

        svc = services[svc_name] or {}

        # Use build: . if vulhub has a Dockerfile, else keep image: as-is
        if has_dockerfile:
            svc.pop("image", None)
            svc["build"] = "."

        # Inject flag as read-only volume mount
        flag_vol = f"./flag.txt:{flag_location}:ro"
        existing_vols = svc.get("volumes", [])
        if flag_vol not in existing_vols:
            existing_vols.append(flag_vol)
        svc["volumes"] = existing_vols
        print(f"  [PATCH] Flag volume: {flag_vol}")

        # Remap ports to our allocated host port
        if "ports" in svc:
            old_ports = svc["ports"]
            svc["ports"] = [
                f"{host_port + i}:{str(p).split(':')[-1]}"
                for i, p in enumerate(old_ports)
            ]
            print(f"  [PATCH] Ports: {old_ports} → {svc['ports']}")
        else:
            svc["ports"] = [f"{host_port}:80"]
            print(f"  [PATCH] No ports found — defaulting to {host_port}:80")

        services[svc_name] = svc

        # Inject isolated bridge network if none defined
        if not parsed.get("networks"):
            net_name = f"vf_{job_id[:8]}"
            parsed["networks"] = {net_name: {"driver": "bridge"}}
            for name, cfg in parsed.get("services", {}).items():
                if cfg is None:
                    cfg = {}
                    parsed["services"][name] = cfg
                existing_nets = cfg.get("networks", [])
                if isinstance(existing_nets, list):
                    if net_name not in existing_nets:
                        existing_nets.append(net_name)
                    cfg["networks"] = existing_nets
                elif isinstance(existing_nets, dict):
                    existing_nets[net_name] = None
                    cfg["networks"] = existing_nets
                else:
                    cfg["networks"] = [net_name]
            print(f"  [PATCH] Injected network '{net_name}'")
        else:
            print(f"  [PATCH] Keeping existing networks: {list(parsed['networks'].keys())}")

        return yaml.dump(parsed, default_flow_style=False, sort_keys=False)

    except Exception as e:
        import traceback
        print(f"  [PATCH] Error: {e}")
        traceback.print_exc()
        return gt.get("raw_yml", "")


# ══════════════════════════════════════════════════════════════════════════════
#  JOB PROCESSOR
# ══════════════════════════════════════════════════════════════════════════════

def process_job(job: dict) -> bool:
    job_id = job["id"]
    print(f"\n{'─' * 60}")
    print(f"[JOB] {job_id[:8]}")
    DB.update_job_status(job_id, "generating")

    try:
        spec       = json.loads(job["spec_json"])
        cve_id     = spec.get("cve", {}).get("id", "N/A")
        difficulty = str(spec.get("difficulty", "medium")).lower()
        seed       = spec.get("seed", job_id[:8])

        raw_port  = DB.get_next_port()
        host_port = get_free_port(raw_port)

        # ── Fetch compose ──────────────────────────────────────────────────
        compose_yml = ""
        vulhub_path = ""

        # Check if this is a CTF challenge (non-CVE)
        challenge_id = spec.get("challenge_id")
        if challenge_id:
            ctf_ch = DB.get_ctf_challenge(challenge_id) if hasattr(DB, 'get_ctf_challenge') else None
            if ctf_ch and ctf_ch.get("compose_yml"):
                compose_yml = ctf_ch["compose_yml"]
                vulhub_path = ""  # CTF challenges don't have vulhub paths
                print(f"  [Compose] loaded CTF challenge: {challenge_id}")
            else:
                raise RuntimeError(f"CTF challenge {challenge_id} not found or has no compose")
        else:
            recipe = DB.get_vulhub_recipe(cve_id)
            if recipe and recipe.get("compose_yml"):
                compose_yml = recipe["compose_yml"]
                print(f"  [Compose] loaded from DB")
            else:
                vulhub_path = spec.get("vulhub_path") or (recipe.get("path") if recipe else None)
                if not vulhub_path:
                    raise RuntimeError(f"No vulhub_path for {cve_id} — run vulhub_miner.py first")
                url = f"https://raw.githubusercontent.com/vulhub/vulhub/master/{vulhub_path}/docker-compose.yml"
                print(f"  [Compose] fetching: {url}")
                import requests
                r = requests.get(url, timeout=15, headers={"User-Agent": "VulnForge/1.0"})
                if r.status_code != 200:
                    raise RuntimeError(f"GitHub fetch failed ({r.status_code})")
                compose_yml = r.text
                DB.store_vulhub_recipe(cve_id=cve_id, path=vulhub_path,
                                       compose_yml=compose_yml, dockerfile="", port=80, tags=[])
                print(f"  [Compose] fetched and cached")

        gt = parse_compose_ground_truth(compose_yml)
        gt["raw_yml"] = compose_yml

        # For Vulhub CVEs, resolve vulhub_path; for CTF challenges, skip Vulhub-specific steps
        is_ctf = bool(challenge_id)
        if not is_ctf:
            vulhub_path = (
                spec.get("vulhub_path")
                or (recipe.get("path") if recipe else None)
                or ""
            )
            if not vulhub_path:
                raise RuntimeError(f"vulhub_path empty for {cve_id}")
        else:
            vulhub_path = ""

        print(f"  {'CTF' if is_ctf else 'CVE'}={challenge_id or cve_id} | difficulty={difficulty} | port={host_port}")

        readme = fetch_vulhub_readme(vulhub_path) if vulhub_path else ""

        # ── Step 1: AI decides flag placement ─────────────────────────────
        print("  [1/3] Flag placement...", end=" ", flush=True)
        flag_analysis = analyze_compose_for_flag(compose_yml, challenge_id or cve_id, difficulty, gt, readme)
        flag_analysis = validate_flag_placement(flag_analysis, gt)
        svc_name  = flag_analysis["service_name"]
        flag_loc  = flag_analysis["flag_location"]
        flag_perm = flag_analysis["flag_permission"]
        print("✓")

        flag_content = f"FLAG{{VULNFORGE_{seed.upper()}_OWNED}}"

        # ── Step 2: Fetch Dockerfile + extra files ────────────────────────
        print("  [2/3] Fetching files...", end=" ", flush=True)
        machine_id  = f"machine_{job_id[:8]}"
        machine_dir = OUTPUT_BASE / machine_id
        machine_dir.mkdir(parents=True, exist_ok=True)

        if is_ctf:
            # CTF challenges: use Dockerfile from DB if available
            ctf_dockerfile = ctf_ch.get("dockerfile", "") if ctf_ch else ""
            has_dockerfile = bool(ctf_dockerfile)
            if has_dockerfile:
                (machine_dir / "Dockerfile").write_text(ctf_dockerfile)
            extra_files = []
        else:
            dockerfile     = build_dockerfile(vulhub_path)
            has_dockerfile = bool(dockerfile)

            if has_dockerfile:
                (machine_dir / "Dockerfile").write_text(dockerfile)
            else:
                needs_build = any(
                    (cfg or {}).get("build")
                    for cfg in gt["parsed"].get("services", {}).values()
                )
                if needs_build:
                    raise RuntimeError(
                        f"Dockerfile fetch failed for vulhub/{vulhub_path} but compose has build: "
                        f"— check vulhub_path and GitHub connectivity."
                    )
            extra_files = fetch_compose_extra_files(vulhub_path, gt["parsed"], machine_dir)

        # Write flag.txt — volume-mounted read-only into container
        (machine_dir / "flag.txt").write_text(flag_content)
        if flag_perm == "400":
            (machine_dir / "flag.txt").chmod(0o400)

        if extra_files:
            print(f"\n  [EXTRA] {extra_files}", end=" ")
        print("✓")

        # ── Step 3: Patch and write compose ───────────────────────────────
        print("  [3/3] Patching compose...", end=" ", flush=True)
        patched = patch_compose(
            gt, svc_name, host_port,
            flag_location=flag_loc,
            flag_permission=flag_perm,
            has_dockerfile=has_dockerfile,
            job_id=job_id,
        )
        (machine_dir / "docker-compose.yml").write_text(patched)
        print("✓")

        # ── Manifest ──────────────────────────────────────────────────────
        access_url = f"{_SERVER_HOST}:{host_port}"
        manifest = {
            "machine_id":    machine_id,
            "job_id":        job_id,
            "cve_id":        cve_id,
            "difficulty":    difficulty,
            "port":          host_port,
            "flag_location": flag_loc,
            "flag_content":  flag_content,
            "service_name":  svc_name,
            "access_url":    access_url,
        }
        (machine_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

        print(f"\n  ✅ Done")
        print(f"  📁 {machine_dir}")
        print(f"  🎯 {access_url}")

        # ── Update vfdb (SQLite job queue) — unchanged ────────────────────
        DB.update_job_status(job_id, "done", port=host_port,
                             machine_id=machine_id, machine_dir=str(machine_dir))

        # ── Register in MySQL (permanent record for Machines tab) ─────────
        # This runs AFTER vfdb is updated so a MySQL failure never blocks
        # the job from being marked done in the queue.
        _register_machine_in_mysql(manifest, job)

        return True

    except Exception as e:
        import traceback
        print(f"  ✗ {e}")
        traceback.print_exc()
        DB.update_job_status(job_id, "failed", error=str(e))
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  LOOP
# ══════════════════════════════════════════════════════════════════════════════

def run_loop():
    print(f"\n{'=' * 60}\n  VulnForge Bridge | Model: {GENERATOR_MODEL}\n{'=' * 60}")
    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
    DB.init_db()
    while True:
        try:
            jobs = DB.get_pending_jobs(limit=1)
            if jobs:
                process_job(jobs[0])
            else:
                print("  Waiting for jobs...", end="\r")
        except KeyboardInterrupt:
            print("\n[BRIDGE] Stopped.")
            break
        except Exception as e:
            print(f"[ERROR] {e}")
        time.sleep(POLL_INTERVAL)


def run_once():
    DB.init_db()
    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
    jobs = DB.get_pending_jobs(limit=20)
    if not jobs:
        print("[BRIDGE] No pending jobs.")
        return
    for job in jobs:
        process_job(job)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    run_once() if args.once else run_loop()
