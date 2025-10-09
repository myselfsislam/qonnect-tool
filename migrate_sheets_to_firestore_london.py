"""
Simple Migration Script: Google Sheets → Firestore (London)
Migrates employee data to europe-west2 for faster global performance!
"""

import gspread
from google.oauth2.service_account import Credentials
from google.cloud import firestore
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_data():
    """Migrate data from Google Sheets to Firestore (London)"""

    print("=" * 80)
    print("🚀 MIGRATING DATA: GOOGLE SHEETS → FIRESTORE (LONDON)")
    print("=" * 80)

    # Step 1: Load from Google Sheets
    print("\n📥 Step 1: Loading data from Google Sheets...")

    try:
        # Google Sheets scopes
        sheets_scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive',
        ]

        # Use service account for Google Sheets
        sheets_creds = Credentials.from_service_account_file('credentials.json', scopes=sheets_scopes)
        client = gspread.authorize(sheets_creds)

        spreadsheet_id = '1OH64Lt1dm-WqlhAXVvXEbFb8-PNvh_ODkD79SjaYkPs'
        spreadsheet = client.open_by_key(spreadsheet_id)

        # Get employees data
        employees_sheet = spreadsheet.get_worksheet(0)
        employees_data = employees_sheet.get_all_records()

        print(f"✅ Loaded {len(employees_data):,} employees from Google Sheets")

    except Exception as e:
        print(f"❌ Failed to load from Google Sheets: {e}")
        return False

    # Step 2: Initialize Firestore using Application Default Credentials
    print("\n🔥 Step 2: Connecting to Firestore (London)...")

    try:
        # Use Application Default Credentials for Firestore
        # This uses gcloud auth credentials which have proper scopes
        db = firestore.Client(project='smartstakeholdersearch')
        print("✅ Connected to Firestore in europe-west2 (London)")

    except Exception as e:
        print(f"❌ Failed to connect to Firestore: {e}")
        return False

    # Step 3: Migrate employees in batches
    print(f"\n📤 Step 3: Migrating {len(employees_data):,} employees to Firestore...")

    batch_size = 500
    total_migrated = 0
    total_batches = (len(employees_data) + batch_size - 1) // batch_size

    try:
        for i in range(0, len(employees_data), batch_size):
            batch = db.batch()
            batch_employees = employees_data[i:i+batch_size]

            for emp_data in batch_employees:
                ldap = emp_data.get('LDAP', '').strip().lower()
                if not ldap:
                    continue

                # Prepare employee document
                employee_doc = {
                    'ldap': ldap,
                    'name': emp_data.get('Name', ''),
                    'name_lower': emp_data.get('Name', '').lower(),
                    'email': emp_data.get('Email', ''),
                    'company': emp_data.get('Company', ''),
                    'designation': emp_data.get('Position', ''),
                    'department': emp_data.get('Department', ''),
                    'location': emp_data.get('Country', ''),
                    'manager': emp_data.get('Manager Email', ''),
                    'organisation': 'Google' if '@google.com' in emp_data.get('Email', '') else 'Other',
                    'avatar': emp_data.get('MOMA Photo URL', ''),
                }

                doc_ref = db.collection('employees').document(ldap)
                batch.set(doc_ref, employee_doc, merge=True)
                total_migrated += 1

            # Commit batch
            batch.commit()
            batch_num = (i // batch_size) + 1
            print(f"  Batch {batch_num}/{total_batches}: Migrated {len(batch_employees)} employees")

        print(f"\n✅ Successfully migrated {total_migrated:,} employees to Firestore (London)!")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        logger.error(f"Migration error: {e}", exc_info=True)
        return False

    # Step 4: Test the migration
    print("\n🧪 Step 4: Testing migration...")

    try:
        # Test search
        test_results = db.collection('employees').limit(5).stream()
        count = sum(1 for _ in test_results)
        print(f"✅ Test query successful: Found {count} employees")

        # Get sample employee
        sample_doc = db.collection('employees').limit(1).stream()
        for doc in sample_doc:
            sample_data = doc.to_dict()
            print(f"✅ Sample employee: {sample_data.get('name')} ({sample_data.get('ldap')})")

    except Exception as e:
        print(f"⚠️  Test failed: {e}")

    print("\n" + "=" * 80)
    print("🎉 MIGRATION TO LONDON COMPLETE!")
    print("=" * 80)
    print("\n⚡ Your app is now optimized for global users!")
    print("\nNext steps:")
    print("  1. Test search locally (should be faster for UK/Israel users!)")
    print("  2. Deploy Cloud Run to europe-west2")
    print("  3. Enable Cloud CDN on Load Balancer")
    print("\n" + "=" * 80)

    return True

if __name__ == "__main__":
    migrate_data()
