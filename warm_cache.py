#!/usr/bin/env python3
"""
Cache Warming Script for Qonnect Tool
Pre-computes and caches detailed connection hierarchies for all Google employees.

This script:
1. Fetches all Google employees from the data source
2. For each employee, calls the connections API to compute and cache their connections
3. Stores results in permanent GCS cache so end users get instant responses
4. Can be run manually or scheduled via cron/Cloud Scheduler

Usage:
  python3 warm_cache.py                    # Warm cache for all employees
  python3 warm_cache.py --limit 10         # Test with first 10 employees only
  python3 warm_cache.py --ldap mellferrier # Warm cache for specific employee
"""

import requests
import time
import json
import argparse
import sys
from datetime import datetime

# Configuration
BASE_URL = "https://qualitest.info/smartstakeholdersearch"
# For testing with v2: BASE_URL = "https://qonnect-tool-v2-167154731583.europe-west2.run.app/smartstakeholdersearch"
# For local testing: BASE_URL = "http://localhost:8080/smartstakeholdersearch"

def get_all_google_employees():
    """Fetch all Google employees from the API"""
    print("📥 Fetching all Google employees...")

    try:
        response = requests.get(f"{BASE_URL}/api/google-employees", timeout=60)
        response.raise_for_status()
        employees = response.json()

        print(f"✅ Found {len(employees)} Google employees")
        return employees

    except Exception as e:
        print(f"❌ Error fetching employees: {e}")
        return []

def warm_cache_for_employee(ldap, employee_name=None):
    """Warm cache for a specific employee by calling the connections API"""
    try:
        start_time = time.time()

        # Call connections API - this will compute and cache the results
        response = requests.get(
            f"{BASE_URL}/api/connections/{ldap}",
            timeout=120  # Allow up to 2 minutes for first-time computation
        )

        elapsed = time.time() - start_time

        if response.status_code == 200:
            connections = response.json()
            conn_count = len(connections)

            # Count precomputed paths
            precomputed_count = sum(1 for c in connections if c.get('precomputedPath'))

            return {
                'success': True,
                'ldap': ldap,
                'name': employee_name or ldap,
                'connections': conn_count,
                'precomputed_paths': precomputed_count,
                'time': round(elapsed, 2)
            }
        else:
            return {
                'success': False,
                'ldap': ldap,
                'name': employee_name or ldap,
                'error': f"HTTP {response.status_code}",
                'time': round(elapsed, 2)
            }

    except Exception as e:
        return {
            'success': False,
            'ldap': ldap,
            'name': employee_name or ldap,
            'error': str(e),
            'time': 0
        }

def warm_all_caches(limit=None, specific_ldap=None):
    """Warm caches for all employees or a specific employee"""

    start_time = datetime.now()
    print(f"\n🔥 Starting cache warming at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    if specific_ldap:
        # Warm cache for specific employee
        print(f"\n🎯 Warming cache for specific employee: {specific_ldap}")
        result = warm_cache_for_employee(specific_ldap)

        if result['success']:
            print(f"\n✅ SUCCESS: {result['name']}")
            print(f"   Connections: {result['connections']}")
            print(f"   Precomputed paths: {result['precomputed_paths']}")
            print(f"   Time: {result['time']}s")
        else:
            print(f"\n❌ FAILED: {result['name']}")
            print(f"   Error: {result['error']}")

        return

    # Get all Google employees
    employees = get_all_google_employees()

    if not employees:
        print("❌ No employees found. Exiting.")
        return

    # Apply limit if specified
    if limit:
        employees = employees[:limit]
        print(f"🔬 Testing mode: Warming cache for first {limit} employees only\n")

    # Warm cache for each employee
    total = len(employees)
    successful = 0
    failed = 0
    total_connections = 0
    total_precomputed = 0

    results = []

    for i, employee in enumerate(employees, 1):
        ldap = employee.get('ldap')
        name = employee.get('name', ldap)

        print(f"\n[{i}/{total}] Processing: {name} ({ldap})...")

        result = warm_cache_for_employee(ldap, name)
        results.append(result)

        if result['success']:
            successful += 1
            total_connections += result['connections']
            total_precomputed += result['precomputed_paths']

            print(f"   ✅ Cached {result['connections']} connections ({result['precomputed_paths']} precomputed) in {result['time']}s")
        else:
            failed += 1
            print(f"   ❌ Failed: {result['error']}")

        # Progress update every 10 employees
        if i % 10 == 0:
            progress = (i / total) * 100
            print(f"\n📊 Progress: {progress:.1f}% ({i}/{total}) | Success: {successful} | Failed: {failed}")

        # Small delay to avoid overwhelming the API
        if i < total:
            time.sleep(0.5)

    # Final summary
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    print("\n" + "=" * 80)
    print("🎉 CACHE WARMING COMPLETE!")
    print("=" * 80)
    print(f"\n📊 Summary:")
    print(f"   Total employees: {total}")
    print(f"   ✅ Successful: {successful}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📦 Total connections cached: {total_connections}")
    print(f"   ⚡ Precomputed paths: {total_precomputed}")
    print(f"   ⏱️  Total time: {elapsed:.2f}s ({elapsed/60:.1f} minutes)")
    print(f"   ⚡ Average time per employee: {elapsed/total:.2f}s")

    # Show failed employees if any
    if failed > 0:
        print(f"\n❌ Failed employees ({failed}):")
        for result in results:
            if not result['success']:
                print(f"   - {result['name']} ({result['ldap']}): {result['error']}")

    # Save results to file
    results_file = f"cache_warming_results_{start_time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump({
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'total_time_seconds': elapsed,
            'total_employees': total,
            'successful': successful,
            'failed': failed,
            'total_connections': total_connections,
            'total_precomputed_paths': total_precomputed,
            'results': results
        }, f, indent=2)

    print(f"\n💾 Results saved to: {results_file}")

    print(f"\n✅ Cache is now warmed! All {successful} employees will load INSTANTLY for end users!")

def main():
    parser = argparse.ArgumentParser(
        description='Warm cache for Qonnect Tool - Pre-compute connections for all employees'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit to first N employees (for testing)'
    )
    parser.add_argument(
        '--ldap',
        type=str,
        help='Warm cache for specific employee LDAP'
    )
    parser.add_argument(
        '--url',
        type=str,
        default=None,
        help='Base URL for the API (default: production)'
    )

    args = parser.parse_args()

    # Update base URL if provided
    global BASE_URL
    if args.url:
        BASE_URL = args.url.rstrip('/')
    print(f"🌐 Using URL: {BASE_URL}")

    try:
        warm_all_caches(limit=args.limit, specific_ldap=args.ldap)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Exiting...")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
