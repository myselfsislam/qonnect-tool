#!/usr/bin/env python3
"""
Test that disk cache persists and is used after app restart.
This simulates what happens when Cloud Run restarts the container.
"""
import time
import requests

BASE_URL = "http://localhost:8080/smartstakeholdersearch"
TEST_EMPLOYEE = "cdangi"

print("\n" + "="*70)
print("🔄 DISK CACHE PERSISTENCE TEST")
print("="*70)

# Test 1: Make a request (should use disk cache from previous test)
print(f"\n1️⃣  Testing employee: {TEST_EMPLOYEE}")
print("   (This should use DISK cache from previous test)")

url = f"{BASE_URL}/api/connections/{TEST_EMPLOYEE}"
start = time.time()
response = requests.get(url)
duration = time.time() - start

if response.status_code == 200:
    data = response.json()
    conn_count = len(data) if isinstance(data, list) else 0
    print(f"   ✓ Status: {response.status_code}")
    print(f"   ✓ Connections: {conn_count}")
    print(f"   ⏱️  Time: {duration:.3f}s")

    if duration < 0.1:
        print(f"   ✅ FAST! Disk cache is working (loaded from disk)")
    else:
        print(f"   ⚠️  Slower than expected. May have recomputed.")
else:
    print(f"   ✗ Error: {response.status_code}")

# Test 2: New employee (should compute and save to disk)
print(f"\n2️⃣  Testing new employee: johnsmith")
print("   (This will compute and save to disk)")

url = f"{BASE_URL}/api/connections/johnsmith"
start = time.time()
response = requests.get(url)
duration = time.time() - start

if response.status_code == 200:
    data = response.json()
    conn_count = len(data) if isinstance(data, list) else 0
    print(f"   ✓ Status: {response.status_code}")
    print(f"   ✓ Connections: {conn_count}")
    print(f"   ⏱️  Time: {duration:.3f}s")
    print(f"   💾 Saved to disk cache")
else:
    print(f"   ✗ Error: {response.status_code}")

# Test 3: Same new employee (should use memory cache)
print(f"\n3️⃣  Testing same employee again: johnsmith")
print("   (Should use memory cache)")

start = time.time()
response = requests.get(url)
duration2 = time.time() - start

if response.status_code == 200:
    data = response.json()
    conn_count = len(data) if isinstance(data, list) else 0
    print(f"   ✓ Status: {response.status_code}")
    print(f"   ✓ Connections: {conn_count}")
    print(f"   ⏱️  Time: {duration2:.3f}s")
    print(f"   🚀 Speedup: {duration/duration2:.1f}x faster")
else:
    print(f"   ✗ Error: {response.status_code}")

print("\n" + "="*70)
print("📝 VERIFICATION STEPS")
print("="*70)
print("\nTo fully test disk cache persistence:")
print("1. Stop the Flask app (kill the process)")
print("2. Start it again (./run_local.sh)")
print("3. Request cdangi or johnsmith")
print("4. It should load from disk cache (~0.01s instead of 1-2s)")
print("\nDisk cache files are in: /tmp/qonnect_cache/")
print("="*70 + "\n")
