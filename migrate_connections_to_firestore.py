"""
Migrate Connections Data: Google Sheets → Firestore
Migrates connection data for instant hierarchy loading!
"""

import gspread
from google.oauth2.service_account import Credentials
from google.cloud import firestore
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clear_connections(db):
    """Clear all existing connections from Firestore"""
    print("\n" + "=" * 80)
    print("🧹 CLEARING EXISTING CONNECTIONS FROM FIRESTORE")
    print("=" * 80)

    try:
        # Get all connections
        connections_ref = db.collection('connections')
        docs = list(connections_ref.stream())

        if len(docs) == 0:
            print("✅ No existing connections to clear")
            return True

        # Delete in batches
        batch = db.batch()
        count = 0

        for doc in docs:
            batch.delete(doc.reference)
            count += 1

            # Commit batch every 500 deletions
            if count % 500 == 0:
                batch.commit()
                batch = db.batch()
                print(f"  Deleted {count} connections...")

        # Commit remaining deletions
        if count % 500 != 0:
            batch.commit()

        print(f"✅ Successfully deleted {count} connections from Firestore\n")
        return True

    except Exception as e:
        print(f"❌ Failed to clear connections: {e}")
        logger.error(f"Clear error: {e}", exc_info=True)
        return False


def migrate_connections():
    """Migrate connections from Google Sheets to Firestore"""

    print("=" * 80)
    print("🚀 MIGRATING CONNECTIONS: GOOGLE SHEETS → FIRESTORE")
    print("=" * 80)

    # Step 1: Load from Google Sheets
    print("\n📥 Step 1: Loading connections from Google Sheets...")

    try:
        # Google Sheets scopes
        sheets_scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive',
        ]

        sheets_creds = Credentials.from_service_account_file('credentials.json', scopes=sheets_scopes)
        client = gspread.authorize(sheets_creds)

        spreadsheet_id = '1OH64Lt1dm-WqlhAXVvXEbFb8-PNvh_ODkD79SjaYkPs'
        spreadsheet = client.open_by_key(spreadsheet_id)

        # Get connections data (Sheet index 1)
        connections_sheet = spreadsheet.get_worksheet(1)
        connections_data = connections_sheet.get_all_records()

        print(f"✅ Loaded {len(connections_data)} connections from Google Sheets")

    except Exception as e:
        print(f"❌ Failed to load from Google Sheets: {e}")
        return False

    # Step 2: Initialize Firestore using Application Default Credentials
    print("\n🔥 Step 2: Connecting to Firestore (London)...")

    try:
        db = firestore.Client(project='smartstakeholdersearch')
        print("✅ Connected to Firestore in europe-west2 (London)")

    except Exception as e:
        print(f"❌ Failed to connect to Firestore: {e}")
        return False

    # Step 2.5: Clear existing connections
    if not clear_connections(db):
        print("❌ Failed to clear existing connections. Aborting migration.")
        return False

    # Step 3: Migrate connections
    print(f"\n📤 Step 3: Migrating {len(connections_data)} connections to Firestore...")

    batch_size = 500
    total_migrated = 0
    total_batches = (len(connections_data) + batch_size - 1) // batch_size

    try:
        for i in range(0, len(connections_data), batch_size):
            batch = db.batch()
            batch_connections = connections_data[i:i+batch_size]

            for conn_data in batch_connections:
                google_ldap = conn_data.get('Google Employee LDAP', '').strip().lower()
                qt_ldap = conn_data.get('QT Employee LDAP', '').strip().lower()

                if not google_ldap or not qt_ldap:
                    continue

                # Create unique document ID
                doc_id = f"{google_ldap}_{qt_ldap}"

                # Prepare connection document
                connection_doc = {
                    'google_employee_ldap': google_ldap,
                    'google_employee_name': conn_data.get('Google Employee Name', ''),
                    'google_employee_email': conn_data.get('Google Employee Email', ''),
                    'google_employee_department': conn_data.get('Google Employee Department', ''),
                    'qt_employee_ldap': qt_ldap,
                    'qt_employee_name': conn_data.get('QT Employee Name', ''),
                    'qt_employee_email': conn_data.get('QT Employee Email', ''),
                    'connection_strength': conn_data.get('Connection Strength', ''),
                    'connection_type': conn_data.get('Connection Type', ''),
                    'declared_by': conn_data.get('Declared by', 'System'),
                    'timestamp': conn_data.get('Timestamp', ''),
                }

                doc_ref = db.collection('connections').document(doc_id)
                batch.set(doc_ref, connection_doc, merge=True)
                total_migrated += 1

            # Commit batch
            batch.commit()
            batch_num = (i // batch_size) + 1
            print(f"  Batch {batch_num}/{total_batches}: Migrated {len(batch_connections)} connections")

        print(f"\n✅ Successfully migrated {total_migrated} connections to Firestore!")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        logger.error(f"Migration error: {e}", exc_info=True)
        return False

    # Step 4: Test the migration
    print("\n🧪 Step 4: Testing migration...")

    try:
        # Test query
        test_results = db.collection('connections').limit(5).stream()
        count = sum(1 for _ in test_results)
        print(f"✅ Test query successful: Found {count} connections")

        # Get sample connection
        sample_doc = db.collection('connections').limit(1).stream()
        for doc in sample_doc:
            sample_data = doc.to_dict()
            print(f"✅ Sample connection: {sample_data.get('google_employee_ldap')} → {sample_data.get('qt_employee_ldap')}")

    except Exception as e:
        print(f"⚠️  Test failed: {e}")

    print("\n" + "=" * 80)
    print("🎉 CONNECTIONS MIGRATION COMPLETE!")
    print("=" * 80)
    print("\n⚡ Hierarchy loading will now be instant!")
    print("\nNext steps:")
    print("  1. Update app.py to use Firestore for connections")
    print("  2. Redeploy to Cloud Run")
    print("\n" + "=" * 80)

    return True

if __name__ == "__main__":
    migrate_connections()
