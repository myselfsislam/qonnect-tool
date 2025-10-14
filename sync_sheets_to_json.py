#!/usr/bin/env python3
"""
Sync Google Sheets data to JSON files for faster app performance.

This script reads data from Google Sheets and exports to JSON files.
Can run locally or as a Cloud Function.

Usage:
    python sync_sheets_to_json.py --output-dir /tmp/qonnect_data
    python sync_sheets_to_json.py --upload-to-gcs  # For Cloud Storage
"""

import json
import os
import sys
import argparse
from datetime import datetime
import logging

# Add parent directory to path to import from app.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import (
    processor,
    get_cached_connections_data,
    get_credentials_from_sheet,
    GOOGLE_SHEETS_CONFIG
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def sync_employees_to_json(output_dir):
    """Export employees data from Google Sheets to JSON"""
    try:
        logger.info("📊 Starting employee data sync from Google Sheets...")

        # Process Google Sheets data
        employees, stats = processor.process_google_sheets_data_optimized()

        if not employees:
            logger.error("❌ No employee data retrieved from Google Sheets")
            return None

        logger.info(f"✅ Retrieved {len(employees)} employees from Google Sheets")

        # Prepare JSON structure
        json_data = {
            'last_updated': datetime.now().isoformat(),
            'total_employees': len(employees),
            'sync_source': 'Google Sheets',
            'spreadsheet_id': GOOGLE_SHEETS_CONFIG['spreadsheet_id'],
            'stats': stats,
            'employees': employees
        }

        # Write to file
        output_file = os.path.join(output_dir, 'employees.json')
        os.makedirs(output_dir, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        file_size_mb = os.path.getsize(output_file) / (1024 * 1024)
        logger.info(f"✅ Employees data written to {output_file} ({file_size_mb:.2f} MB)")

        return output_file

    except Exception as e:
        logger.error(f"❌ Error syncing employees: {e}")
        return None


def sync_connections_to_json(output_dir):
    """Export connections data from Google Sheets to JSON"""
    try:
        logger.info("🔗 Starting connections data sync from Google Sheets...")

        # Get connections data (uses existing cache function)
        connections = get_cached_connections_data()

        if not connections:
            logger.warning("⚠️ No connections data retrieved")
            connections = []

        logger.info(f"✅ Retrieved {len(connections)} connection records from Google Sheets")

        # Prepare JSON structure
        json_data = {
            'last_updated': datetime.now().isoformat(),
            'total_connections': len(connections),
            'sync_source': 'Google Sheets',
            'spreadsheet_id': GOOGLE_SHEETS_CONFIG['spreadsheet_id'],
            'connections': connections
        }

        # Write to file
        output_file = os.path.join(output_dir, 'connections.json')
        os.makedirs(output_dir, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        file_size_kb = os.path.getsize(output_file) / 1024
        logger.info(f"✅ Connections data written to {output_file} ({file_size_kb:.2f} KB)")

        return output_file

    except Exception as e:
        logger.error(f"❌ Error syncing connections: {e}")
        return None


def sync_credentials_to_json(output_dir):
    """Export credentials data from Google Sheets to JSON"""
    try:
        logger.info("🔐 Starting credentials data sync from Google Sheets...")

        # Get credentials from Google Sheets
        credentials = get_credentials_from_sheet()

        if not credentials:
            logger.warning("⚠️ No credentials data retrieved")
            credentials = []

        logger.info(f"✅ Retrieved {len(credentials)} credential records from Google Sheets")

        # Prepare JSON structure
        json_data = {
            'last_updated': datetime.now().isoformat(),
            'total_credentials': len(credentials),
            'sync_source': 'Google Sheets',
            'spreadsheet_id': GOOGLE_SHEETS_CONFIG['spreadsheet_id'],
            'credentials': credentials
        }

        # Write to file
        output_file = os.path.join(output_dir, 'credentials.json')
        os.makedirs(output_dir, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        file_size_kb = os.path.getsize(output_file) / 1024
        logger.info(f"✅ Credentials data written to {output_file} ({file_size_kb:.2f} KB)")

        return output_file

    except Exception as e:
        logger.error(f"❌ Error syncing credentials: {e}")
        return None


def create_metadata(output_dir, files_created):
    """Create metadata file with sync information"""
    try:
        metadata = {
            'sync_timestamp': datetime.now().isoformat(),
            'sync_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'spreadsheet_id': GOOGLE_SHEETS_CONFIG['spreadsheet_id'],
            'spreadsheet_url': GOOGLE_SHEETS_CONFIG['spreadsheet_url'],
            'files_created': files_created,
            'sync_status': 'success'
        }

        output_file = os.path.join(output_dir, 'metadata.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Metadata written to {output_file}")
        return output_file

    except Exception as e:
        logger.error(f"❌ Error creating metadata: {e}")
        return None


def upload_to_gcs(local_dir, bucket_name='smartstakeholdersearch-data'):
    """Upload JSON files to Google Cloud Storage"""
    try:
        from google.cloud import storage

        logger.info(f"☁️ Uploading files to Cloud Storage bucket: {bucket_name}")

        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)

        uploaded_files = []
        for filename in os.listdir(local_dir):
            if filename.endswith('.json'):
                local_path = os.path.join(local_dir, filename)
                blob = bucket.blob(filename)
                blob.upload_from_filename(local_path)

                # Set cache control for performance
                blob.cache_control = 'public, max-age=300'  # 5 minutes
                blob.patch()

                uploaded_files.append(filename)
                logger.info(f"  ✅ Uploaded: {filename}")

        logger.info(f"☁️ Successfully uploaded {len(uploaded_files)} files to Cloud Storage")
        return True

    except Exception as e:
        logger.error(f"❌ Error uploading to Cloud Storage: {e}")
        return False


def main():
    """Main sync function"""
    parser = argparse.ArgumentParser(description='Sync Google Sheets to JSON files')
    parser.add_argument(
        '--output-dir',
        default='/tmp/qonnect_data',
        help='Directory to save JSON files (default: /tmp/qonnect_data)'
    )
    parser.add_argument(
        '--upload-to-gcs',
        action='store_true',
        help='Upload to Google Cloud Storage after creating JSON files'
    )
    parser.add_argument(
        '--bucket-name',
        default='smartstakeholdersearch-data',
        help='Cloud Storage bucket name (default: smartstakeholdersearch-data)'
    )

    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("🚀 QONNECT DATA SYNC - Google Sheets → JSON")
    logger.info("=" * 70)
    logger.info(f"Output directory: {args.output_dir}")
    logger.info(f"Spreadsheet: {GOOGLE_SHEETS_CONFIG['spreadsheet_url']}")
    logger.info("=" * 70)

    # Track created files
    files_created = {}

    # Sync employees
    logger.info("\n📊 Step 1/4: Syncing employees data...")
    employees_file = sync_employees_to_json(args.output_dir)
    if employees_file:
        files_created['employees'] = os.path.basename(employees_file)

    # Sync connections
    logger.info("\n🔗 Step 2/4: Syncing connections data...")
    connections_file = sync_connections_to_json(args.output_dir)
    if connections_file:
        files_created['connections'] = os.path.basename(connections_file)

    # Sync credentials
    logger.info("\n🔐 Step 3/4: Syncing credentials data...")
    credentials_file = sync_credentials_to_json(args.output_dir)
    if credentials_file:
        files_created['credentials'] = os.path.basename(credentials_file)

    # Create metadata
    logger.info("\n📝 Step 4/4: Creating metadata...")
    metadata_file = create_metadata(args.output_dir, files_created)
    if metadata_file:
        files_created['metadata'] = os.path.basename(metadata_file)

    # Upload to Cloud Storage if requested
    if args.upload_to_gcs:
        logger.info("\n☁️ Uploading to Cloud Storage...")
        upload_to_gcs(args.output_dir, args.bucket_name)

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("✅ SYNC COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Files created: {len(files_created)}")
    for key, filename in files_created.items():
        filepath = os.path.join(args.output_dir, filename)
        if os.path.exists(filepath):
            size_kb = os.path.getsize(filepath) / 1024
            logger.info(f"  • {filename} ({size_kb:.2f} KB)")
    logger.info(f"\nOutput directory: {args.output_dir}")
    logger.info("=" * 70)

    return len(files_created) > 0


# Cloud Function entry point (for GCP deployment)
def sync_to_cloud_storage(request=None):
    """
    Cloud Function entry point for automated sync.
    Triggered by Cloud Scheduler.
    """
    import tempfile

    logger.info("☁️ Cloud Function triggered - Starting sync...")

    # Create temporary directory for JSON files
    with tempfile.TemporaryDirectory() as temp_dir:
        # Sync all data to temp directory
        files_created = {}

        employees_file = sync_employees_to_json(temp_dir)
        if employees_file:
            files_created['employees'] = os.path.basename(employees_file)

        connections_file = sync_connections_to_json(temp_dir)
        if connections_file:
            files_created['connections'] = os.path.basename(connections_file)

        credentials_file = sync_credentials_to_json(temp_dir)
        if credentials_file:
            files_created['credentials'] = os.path.basename(credentials_file)

        metadata_file = create_metadata(temp_dir, files_created)
        if metadata_file:
            files_created['metadata'] = os.path.basename(metadata_file)

        # Upload to Cloud Storage
        success = upload_to_gcs(temp_dir)

        if success:
            return {'status': 'success', 'files': list(files_created.values())}, 200
        else:
            return {'status': 'error', 'message': 'Upload failed'}, 500


if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n\n⚠️ Sync interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\n❌ Fatal error: {e}")
        sys.exit(1)