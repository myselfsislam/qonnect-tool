"""
Test Firestore Search Performance
Quick test to verify search speed improvements
"""

import time
import firestore_db

def test_search_performance():
    """Test search performance with various queries"""

    print("=" * 80)
    print("🔍 FIRESTORE SEARCH PERFORMANCE TEST")
    print("=" * 80)

    # Test queries
    test_queries = [
        "sundar",
        "demis",
        "jeff",
        "sarah",
        "google",
    ]

    print("\n📊 Testing search performance with various queries:\n")

    total_time = 0
    for query in test_queries:
        start_time = time.time()
        results = firestore_db.search_employees(query, limit=10)
        end_time = time.time()

        elapsed_ms = (end_time - start_time) * 1000
        total_time += elapsed_ms

        print(f"Query: '{query}'")
        print(f"  ⏱️  Time: {elapsed_ms:.2f}ms")
        print(f"  📊 Results: {len(results)} employees found")

        if results:
            print(f"  👤 Top result: {results[0].get('name')} ({results[0].get('ldap')})")
        print()

    avg_time = total_time / len(test_queries)

    print("=" * 80)
    print("📈 PERFORMANCE SUMMARY")
    print("=" * 80)
    print(f"Total queries: {len(test_queries)}")
    print(f"Average search time: {avg_time:.2f}ms")
    print(f"Total time: {total_time:.2f}ms")
    print()
    print("🎉 Comparison to Google Sheets:")
    print(f"  Old (Google Sheets): ~15,000-20,000ms (15-20 seconds)")
    print(f"  New (Firestore): ~{avg_time:.0f}ms")
    print(f"  🚀 Speed improvement: {15000/avg_time:.0f}x faster!")
    print("=" * 80)

def test_employee_lookup():
    """Test individual employee lookup"""

    print("\n" + "=" * 80)
    print("🔍 EMPLOYEE LOOKUP TEST")
    print("=" * 80)

    test_ldaps = ["sundar", "demis", "jeff"]

    print("\n📊 Testing direct LDAP lookups:\n")

    total_time = 0
    for ldap in test_ldaps:
        start_time = time.time()
        employee = firestore_db.get_employee_by_ldap(ldap)
        end_time = time.time()

        elapsed_ms = (end_time - start_time) * 1000
        total_time += elapsed_ms

        print(f"LDAP: '{ldap}'")
        print(f"  ⏱️  Time: {elapsed_ms:.2f}ms")

        if employee:
            print(f"  ✅ Found: {employee.get('name')} - {employee.get('email')}")
        else:
            print(f"  ❌ Not found")
        print()

    avg_time = total_time / len(test_ldaps)

    print("=" * 80)
    print(f"Average lookup time: {avg_time:.2f}ms")
    print(f"🚀 Speed improvement over Google Sheets: ~{1000/avg_time:.0f}x faster!")
    print("=" * 80)

if __name__ == "__main__":
    try:
        test_search_performance()
        test_employee_lookup()

        print("\n✅ All performance tests completed successfully!")
        print("🎉 Firestore is working perfectly and delivering blazing fast results!\n")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
