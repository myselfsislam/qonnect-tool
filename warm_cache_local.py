#!/usr/bin/env python3
"""
Local Cache Warming Script - Production Safe
Runs from your local machine with rate limiting to protect production service.

Features:
- Fetches employee list from production API
- Runs cache warming with gentle rate limiting
- Checkpoint-based resume capability
- Won't overwhelm production service

Usage:
  python3 warm_cache_local.py                    # Resume from checkpoint
  python3 warm_cache_local.py --limit 10         # Test with 10 employees
  python3 warm_cache_local.py --no-resume        # Start fresh
  python3 warm_cache_local.py --delay 3          # 3 seconds between requests
"""

import requests
import time
import json
import argparse
import sys
from datetime import datetime
from pathlib import Path

# Configuration
BASE_URL = "https://qualitest.info/smartstakeholdersearch"
CHECKPOINT_FILE = "cache_warming_checkpoint.json"
LOG_FILE = "cache_warming.log"
TIMEOUT_PER_EMPLOYEE = 30  # seconds
DELAY_BETWEEN_REQUESTS = 2  # seconds - gentle on production

def log(message, flush=True):
    """Log to both console and file"""
    print(message, flush=flush)
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(message + '\n')
            if flush:
                f.flush()
    except Exception:
        pass

def load_checkpoint():
    """Load progress from checkpoint file"""
    if Path(CHECKPOINT_FILE).exists():
        try:
            with open(CHECKPOINT_FILE, 'r') as f:
                checkpoint = json.load(f)
                log(f"📂 Loaded checkpoint: {len(checkpoint.get('processed_ldaps', []))} already processed")
                return checkpoint
        except Exception as e:
            log(f"⚠️  Warning: Could not load checkpoint: {e}")
    return {'processed_ldaps': [], 'successful': 0, 'failed': 0, 'results': []}

def save_checkpoint(checkpoint):
    """Save progress to checkpoint file"""
    try:
        with open(CHECKPOINT_FILE, 'w') as f:
            json.dump(checkpoint, f, indent=2)
    except Exception as e:
        log(f"⚠️  Warning: Could not save checkpoint: {e}")

def get_all_google_employees():
    """Fetch all Google employees from the API"""
    log("📥 Fetching all Google employees from API...")

    try:
        response = requests.get(f"{BASE_URL}/api/google-employees", timeout=60)
        response.raise_for_status()
        employees = response.json()
        log(f"✅ Found {len(employees)} Google employees")
        return employees
    except Exception as e:
        log(f"❌ Error fetching employees: {e}")
        log(f"💡 Make sure {BASE_URL} is accessible and not overloaded")
        return []

def warm_cache_for_employee(ldap, employee_name=None, timeout_seconds=TIMEOUT_PER_EMPLOYEE):
    """Warm cache for a specific employee with timeout protection"""
    try:
        start_time = time.time()

        response = requests.get(
            f"{BASE_URL}/api/connections/{ldap}",
            timeout=timeout_seconds
        )

        elapsed = time.time() - start_time

        if response.status_code == 200:
            connections = response.json()
            conn_count = len(connections)
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

    except requests.Timeout:
        return {
            'success': False,
            'ldap': ldap,
            'name': employee_name or ldap,
            'error': f"TIMEOUT after {timeout_seconds}s",
            'time': timeout_seconds
        }
    except Exception as e:
        elapsed = time.time() - start_time if 'start_time' in locals() else 0
        return {
            'success': False,
            'ldap': ldap,
            'name': employee_name or ldap,
            'error': str(e)[:200],
            'time': round(elapsed, 2)
        }

def check_service_health():
    """Check if the service is healthy before starting"""
    log("🏥 Checking service health...")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=10)
        if response.status_code in [200, 302]:  # 302 is redirect to login
            log("✅ Service is healthy")
            return True
        else:
            log(f"⚠️  Service returned {response.status_code}")
            return False
    except Exception as e:
        log(f"❌ Service health check failed: {e}")
        return False

def warm_all_caches(limit=None, resume=True, delay=None):
    """Warm caches for all employees"""

    if delay is None:
        delay = DELAY_BETWEEN_REQUESTS

    start_time = datetime.now()
    log(f"\n🔥 Starting cache warming at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 80)

    # Check service health first
    if not check_service_health():
        log("❌ Service is not healthy. Aborting to avoid overwhelming it.")
        log("💡 Please check if https://qualitest.info/smartstakeholdersearch/ is accessible")
        return

    # Load checkpoint
    checkpoint = load_checkpoint() if resume else {'processed_ldaps': [], 'successful': 0, 'failed': 0, 'results': []}
    processed_ldaps = set(checkpoint['processed_ldaps'])

    # Get all employees
    employees = get_all_google_employees()
    if not employees:
        log("❌ No employees found. Exiting.")
        log("💡 The service might be down or overloaded. Try again later.")
        return

    # Filter out already processed
    employees_to_process = [e for e in employees if e.get('ldap') not in processed_ldaps]

    if limit:
        employees_to_process = employees_to_process[:limit]
        log(f"🔬 Limiting to {limit} employees")

    total = len(employees)
    remaining = len(employees_to_process)

    log(f"\n📊 Status:")
    log(f"   Total employees: {total}")
    log(f"   Already processed: {len(processed_ldaps)}")
    log(f"   Remaining: {remaining}")
    log(f"   Delay between requests: {delay}s")
    log(f"   Timeout per employee: {TIMEOUT_PER_EMPLOYEE}s")

    if remaining == 0:
        log("\n✅ All employees already processed!")
        log(f"💡 To start fresh, delete {CHECKPOINT_FILE}")
        return

    # Estimate time
    estimated_seconds = remaining * (TIMEOUT_PER_EMPLOYEE + delay) / 2  # Rough estimate
    estimated_hours = estimated_seconds / 3600
    log(f"\n⏱️  Estimated completion time: {estimated_hours:.1f} hours")
    log(f"💡 This will run gently to avoid overwhelming your production service")
    log("")

    successful = checkpoint['successful']
    failed = checkpoint['failed']
    processed_count = len(processed_ldaps)

    # Process employees sequentially
    for employee in employees_to_process:
        ldap = employee.get('ldap')
        name = employee.get('name', ldap)

        processed_count += 1

        log(f"[{processed_count}/{total}] Processing: {name} ({ldap})...")

        # Warm cache
        result = warm_cache_for_employee(ldap, name)

        # Update checkpoint
        checkpoint['processed_ldaps'].append(ldap)
        checkpoint['results'].append(result)

        if result['success']:
            successful += 1
            checkpoint['successful'] = successful
            log(f"   ✅ Cached {result['connections']} connections ({result['precomputed_paths']} precomputed) in {result['time']}s")
        else:
            failed += 1
            checkpoint['failed'] = failed
            log(f"   ❌ Failed: {result['error']}")

            # If we get multiple consecutive failures, stop to avoid hammering the service
            if failed > 0 and len(checkpoint['results']) > 0:
                recent_results = checkpoint['results'][-5:]  # Last 5 results
                recent_failures = sum(1 for r in recent_results if not r['success'])
                if recent_failures >= 5:
                    log(f"\n⚠️  WARNING: 5 consecutive failures detected!")
                    log(f"💡 The service might be overloaded. Stopping to protect it.")
                    save_checkpoint(checkpoint)
                    return

        # Save checkpoint after every employee
        save_checkpoint(checkpoint)

        # Progress update every 10 employees
        if processed_count % 10 == 0:
            progress = (processed_count / total) * 100
            log(f"\n📊 Progress: {progress:.1f}% ({processed_count}/{total}) | Success: {successful} | Failed: {failed}\n")

        # Rate limiting - delay between requests
        if processed_count < total:
            time.sleep(delay)

    # Final summary
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    log("\n" + "=" * 80)
    log("🎉 CACHE WARMING COMPLETE!")
    log("=" * 80)
    log(f"\n📊 Summary:")
    log(f"   Total employees: {total}")
    log(f"   Processed in this run: {remaining}")
    log(f"   ✅ Successful: {successful}")
    log(f"   ❌ Failed: {failed}")
    log(f"   ⏱️  Total time: {elapsed:.2f}s ({elapsed/60:.1f} minutes)")

    if remaining > 0:
        avg_time = elapsed / remaining
        log(f"   ⚡ Average time per employee: {avg_time:.2f}s")

    # Show some failed employees if any
    if failed > 0:
        failed_results = [r for r in checkpoint['results'] if not r['success']]
        log(f"\n❌ Failed employees ({failed} total):")
        for result in failed_results[:10]:
            log(f"   - {result['name']} ({result['ldap']}): {result['error']}")
        if failed > 10:
            log(f"   ... and {failed - 10} more")

    log(f"\n✅ Cache is now warmed! All {successful} employees will load INSTANTLY!")
    log(f"\n💾 Checkpoint file: {CHECKPOINT_FILE}")
    log(f"💾 Log file: {LOG_FILE}")

def main():
    parser = argparse.ArgumentParser(
        description='Local Cache Warming Script - Production Safe',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                       # Resume from checkpoint
  %(prog)s --limit 10            # Test with 10 employees
  %(prog)s --no-resume           # Start fresh
  %(prog)s --delay 3             # 3 seconds between requests (even gentler)

Tips:
  - Script runs sequentially with delays to protect production
  - Automatically stops if service becomes unhealthy
  - Can be interrupted (Ctrl+C) and resumed anytime
  - Delete checkpoint file to start from scratch
  - Increase --delay if service is slow or overloaded
        """
    )
    parser.add_argument('--limit', type=int, help='Limit to first N employees (testing)')
    parser.add_argument('--no-resume', action='store_true', help='Start fresh (ignore checkpoint)')
    parser.add_argument('--delay', type=float, default=DELAY_BETWEEN_REQUESTS,
                       help=f'Delay between requests in seconds (default: {DELAY_BETWEEN_REQUESTS})')
    parser.add_argument('--url', type=str, help='Base URL for the API')

    args = parser.parse_args()

    global BASE_URL
    if args.url:
        BASE_URL = args.url.rstrip('/')

    delay = args.delay if args.delay else DELAY_BETWEEN_REQUESTS

    log(f"🌐 Using URL: {BASE_URL}")
    log(f"⏱️  Delay between requests: {delay}s")

    try:
        warm_all_caches(
            limit=args.limit,
            resume=not args.no_resume,
            delay=delay
        )
    except KeyboardInterrupt:
        log("\n\n⚠️  Interrupted by user. Progress saved!")
        log(f"💡 Run again to resume: python3 warm_cache_local.py")
        sys.exit(0)
    except Exception as e:
        log(f"\n\n❌ Fatal error: {e}")
        import traceback
        log(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
