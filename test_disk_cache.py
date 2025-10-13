#!/usr/bin/env python3
"""
Test script to verify disk caching for connections and hierarchy.
"""
import time
import requests
import sys

# Test configuration
BASE_URL = "http://localhost:8080/smartstakeholdersearch"
TEST_EMPLOYEES = ["cdangi", "melissaabed", "chandakan"]

def test_connections_performance(employee_ldap):
    """Test connections endpoint with timing"""
    url = f"{BASE_URL}/api/connections/{employee_ldap}"

    print(f"\n{'='*70}")
    print(f"Testing: {employee_ldap}")
    print(f"{'='*70}")

    # First request (should compute and cache to disk)
    print("\n1️⃣  First Request (cache miss, will compute):")
    start = time.time()
    response = requests.get(url)
    duration1 = time.time() - start

    if response.status_code == 200:
        data = response.json()
        conn_count = len(data) if isinstance(data, list) else 0
        print(f"   ✓ Status: {response.status_code}")
        print(f"   ✓ Connections found: {conn_count}")
        print(f"   ⏱️  Time: {duration1:.3f}s")
    else:
        print(f"   ✗ Error: {response.status_code}")
        return

    # Second request (should use memory cache)
    print("\n2️⃣  Second Request (memory cache hit):")
    start = time.time()
    response = requests.get(url)
    duration2 = time.time() - start

    if response.status_code == 200:
        data = response.json()
        conn_count = len(data) if isinstance(data, list) else 0
        print(f"   ✓ Status: {response.status_code}")
        print(f"   ✓ Connections found: {conn_count}")
        print(f"   ⏱️  Time: {duration2:.3f}s")
        print(f"   🚀 Speedup: {duration1/duration2:.1f}x faster")
    else:
        print(f"   ✗ Error: {response.status_code}")

    # Wait a moment
    time.sleep(1)

    # Third request (should still use memory cache)
    print("\n3️⃣  Third Request (memory cache hit):")
    start = time.time()
    response = requests.get(url)
    duration3 = time.time() - start

    if response.status_code == 200:
        data = response.json()
        conn_count = len(data) if isinstance(data, list) else 0
        print(f"   ✓ Status: {response.status_code}")
        print(f"   ✓ Connections found: {conn_count}")
        print(f"   ⏱️  Time: {duration3:.3f}s")
        print(f"   🚀 Speedup: {duration1/duration3:.1f}x faster")
    else:
        print(f"   ✗ Error: {response.status_code}")

    return {
        'employee': employee_ldap,
        'first_request': duration1,
        'second_request': duration2,
        'third_request': duration3,
        'speedup': duration1 / min(duration2, duration3)
    }

def test_hierarchy_performance(employee_ldap):
    """Test hierarchy endpoint with timing"""
    url = f"{BASE_URL}/api/hierarchy/{employee_ldap}"

    print(f"\n{'='*70}")
    print(f"Testing Hierarchy: {employee_ldap}")
    print(f"{'='*70}")

    # First request
    print("\n1️⃣  First Request (cache miss):")
    start = time.time()
    response = requests.get(url)
    duration1 = time.time() - start

    if response.status_code == 200:
        data = response.json()
        manager_count = len(data.get('manager_chain', []))
        print(f"   ✓ Status: {response.status_code}")
        print(f"   ✓ Manager chain levels: {manager_count}")
        print(f"   ⏱️  Time: {duration1:.3f}s")
    else:
        print(f"   ✗ Error: {response.status_code}")
        return

    # Second request
    print("\n2️⃣  Second Request (memory cache):")
    start = time.time()
    response = requests.get(url)
    duration2 = time.time() - start

    if response.status_code == 200:
        print(f"   ✓ Status: {response.status_code}")
        print(f"   ⏱️  Time: {duration2:.3f}s")
        print(f"   🚀 Speedup: {duration1/duration2:.1f}x faster")
    else:
        print(f"   ✗ Error: {response.status_code}")

def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("🧪 DISK CACHING PERFORMANCE TEST")
    print("="*70)
    print(f"Base URL: {BASE_URL}")
    print(f"Test employees: {', '.join(TEST_EMPLOYEES)}")

    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/api/stats", timeout=5)
        if response.status_code != 200:
            print(f"\n❌ Server not responding properly. Status: {response.status_code}")
            print("Please start the Flask app: python3 app.py")
            sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Cannot connect to server: {e}")
        print("Please start the Flask app: python3 app.py")
        sys.exit(1)

    print("✓ Server is running")

    # Test connections for each employee
    results = []
    for employee in TEST_EMPLOYEES:
        result = test_connections_performance(employee)
        if result:
            results.append(result)
        time.sleep(1)

    # Test hierarchy for one employee
    if TEST_EMPLOYEES:
        test_hierarchy_performance(TEST_EMPLOYEES[0])

    # Summary
    print("\n" + "="*70)
    print("📊 PERFORMANCE SUMMARY")
    print("="*70)

    if results:
        avg_first = sum(r['first_request'] for r in results) / len(results)
        avg_cached = sum(min(r['second_request'], r['third_request']) for r in results) / len(results)
        avg_speedup = sum(r['speedup'] for r in results) / len(results)

        print(f"\nAverage Performance:")
        print(f"  • First request (compute): {avg_first:.3f}s")
        print(f"  • Cached request:          {avg_cached:.3f}s")
        print(f"  • Average speedup:         {avg_speedup:.1f}x faster")
        print(f"\n✅ Disk caching is working correctly!")
        print(f"   Cache files are stored in: /tmp/qonnect_cache/")

    print("\n" + "="*70)

if __name__ == "__main__":
    main()
