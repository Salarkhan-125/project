#!/usr/bin/env python3
"""
Diagnostic script to test all imports and identify issues
Run this from forge/ directory: python3 web/api/test_imports.py
"""
import sys
from pathlib import Path

# Add forge/ to path
FORGE_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(FORGE_ROOT))

print("="*60)
print("HACKFORGE IMPORT DIAGNOSTICS")
print("="*60)
print(f"\nForge Root: {FORGE_ROOT}")
print(f"Python Path: {sys.path[:3]}")

# Test 1: Config
print("\n[TEST 1] Importing config...")
try:
    from web.api.config import CORE_PATH, logger, CORS_ORIGINS
    print("✓ Config imported successfully")
    print(f"  CORE_PATH: {CORE_PATH}")
except Exception as e:
    print(f"✗ Config import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Dependencies
print("\n[TEST 2] Importing dependencies...")
try:
    from web.api.dependencies import db, generator, orchestrator
    print("✓ Dependencies imported successfully")
except Exception as e:
    print(f"✗ Dependencies import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Models
print("\n[TEST 3] Importing models...")
try:
    from web.api.models.user import UserCreate
    from web.api.models.campaign import CampaignCreateRequest
    from web.api.models.flag import FlagSubmitRequest
    print("✓ Models imported successfully")
except Exception as e:
    print(f"✗ Models import failed: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Individual Routers
print("\n[TEST 4] Importing routers...")
routers = [
    ('users', 'web.api.routes.users'),
    ('campaigns', 'web.api.routes.campaigns'),
    ('machines', 'web.api.routes.machines'),
    ('flags', 'web.api.routes.flags'),
    ('blueprints', 'web.api.routes.blueprints'),
    ('configs', 'web.api.routes.configs'),
    ('docker', 'web.api.routes.docker'),
    ('leaderboard', 'web.api.routes.leaderboard'),
    ('stats', 'web.api.routes.stats'),
]

failed_routers = []
for name, module_path in routers:
    try:
        module = __import__(module_path, fromlist=['router'])
        router = getattr(module, 'router')
        print(f"  ✓ {name}: {len(router.routes)} routes")
    except Exception as e:
        print(f"  ✗ {name}: {e}")
        failed_routers.append((name, e))

if failed_routers:
    print(f"\n✗ {len(failed_routers)} routers failed to import")
    for name, error in failed_routers:
        print(f"  - {name}: {error}")
else:
    print(f"\n✓ All routers imported successfully")

# Test 5: Services
print("\n[TEST 5] Importing services...")
try:
    from web.api.services.docker_service import start_campaign_containers
    print("✓ Services imported successfully")
except Exception as e:
    print(f"✗ Services import failed: {e}")

# Test 6: Database connection
print("\n[TEST 6] Testing database connection...")
try:
    result = db.users.find_one()
    print(f"✓ Database connection successful")
except Exception as e:
    print(f"✗ Database connection failed: {e}")

# Test 7: Generator blueprints
print("\n[TEST 7] Testing generator blueprints...")
try:
    blueprints = generator.list_blueprints()
    print(f"✓ Found {len(blueprints)} blueprints")
except Exception as e:
    print(f"✗ Generator failed: {e}")

print("\n" + "="*60)
print("DIAGNOSTICS COMPLETE")
print("="*60)

if failed_routers:
    print("\n⚠ ISSUES FOUND - Review failed imports above")
    sys.exit(1)
else:
    print("\n✓ ALL TESTS PASSED - API should work correctly")
    sys.exit(0)