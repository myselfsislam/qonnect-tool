from flask import Flask, jsonify, request, render_template_string, send_from_directory, session, redirect, url_for, render_template, Blueprint
from flask_cors import CORS
import pandas as pd
import json
import os
import requests
from datetime import datetime, timedelta
import re
from typing import Dict, List, Optional, Tuple
import io
from urllib.parse import urlparse
import gspread
from google.oauth2.service_account import Credentials
import tempfile
import logging
from functools import lru_cache, wraps
import gc
import time
import secrets
import pickle
import hashlib
from google.cloud import storage
# Firestore removed - using Google Sheets only

app = Flask(__name__)
CORS(app)

# Create Blueprint with /smartstakeholdersearch prefix
bp = Blueprint('smartstakeholder', __name__, url_prefix='/smartstakeholdersearch')

# Configure session secret key
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # 30 days session lifetime
app.config['SESSION_REFRESH_EACH_REQUEST'] = True  # Refresh session on each request

# Rate limiter for Google Sheets API
class APIRateLimiter:
    def __init__(self, min_interval=1.0):
        self.min_interval = min_interval  # Minimum seconds between API calls
        self.last_call_time = 0

    def wait_if_needed(self):
        """Wait if needed to respect rate limit"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time

        if time_since_last_call < self.min_interval:
            sleep_time = self.min_interval - time_since_last_call
            time.sleep(sleep_time)

        self.last_call_time = time.time()

# Global rate limiter instance
api_rate_limiter = APIRateLimiter(min_interval=0.01)  # 0.01 seconds between calls - minimal delay while respecting quotas

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

            # Google Sheets Configuration - Optimized
GOOGLE_SHEETS_CONFIG = {
    'spreadsheet_id': '1OH64Lt1dm-WqlhAXVvXEbFb8-PNvh_ODkD79SjaYkPs',
    'spreadsheet_url': 'https://docs.google.com/spreadsheets/d/1OH64Lt1dm-WqlhAXVvXEbFb8-PNvh_ODkD79SjaYkPs/edit?gid=0#gid=0',
    'sheet_name': 'Sheet1',
    'service_account_file': 'credentials.json',
    'scopes': [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ],
    'batch_size': 1000,
    'max_employees': 200000, # Increased for debugging large datasets
    'progress_interval': 1000,
    'memory_cleanup_interval': 5000
}

# JSON Data Configuration - Hybrid Approach (for faster performance)
JSON_DATA_CONFIG = {
    'enabled': os.environ.get('USE_JSON_DATA', 'false').lower() == 'true',
    'local_dir': os.environ.get('JSON_DATA_DIR', '/tmp/qonnect_data'),
    'gcs_bucket': os.environ.get('JSON_GCS_BUCKET', 'smartstakeholdersearch-data'),
    'use_gcs': os.environ.get('USE_GCS', 'false').lower() == 'true',
    'fallback_to_sheets': True,  # Always fall back to Sheets if JSON fails
}

# Global data storage - Optimized
employees_data = []
google_employees = []
core_team = []
processing_stats = {}

# Performance: Search index for faster lookups
employee_search_index = {
    'by_name': {},
    'by_ldap': {},
    'by_email': {},
    'last_built': None
}
last_sync_time = None

# Cached connections data to avoid quota issues
cached_connections_data = None
connections_cache_time = None
connections_cache_ttl = 1800  # 30 minutes cache TTL - much longer to avoid frequent API calls

# Global cache for all sheet data to minimize API calls
global_employees_cache = None
global_employees_cache_time = None
employees_cache_ttl = 1800  # 30 minutes cache for employees

# Cache for computed connections per employee
connections_result_cache = {}
connections_result_cache_ttl = 3600  # 1 hour cache for computed connections

# Cache for employee hierarchy lookups
hierarchy_result_cache = {}
hierarchy_result_cache_ttl = 3600  # 1 hour cache for hierarchy

# Disk cache configuration (using /tmp for Cloud Run)
DISK_CACHE_DIR = '/tmp/qonnect_cache'
DISK_CACHE_TTL = 604800  # 1 week (7 days)

# GCS cache configuration for persistent storage
GCS_CACHE_ENABLED = os.environ.get('USE_GCS_CACHE', 'true').lower() == 'true'
GCS_CACHE_BUCKET = os.environ.get('GCS_CACHE_BUCKET', 'smartstakeholdersearch-data')
GCS_CACHE_PREFIX = 'cache/'
GCS_CACHE_TTL = 604800  # 1 week (7 days)

# Helper functions for disk caching
def get_disk_cache_path(cache_key):
    """Get file path for disk cache"""
    os.makedirs(DISK_CACHE_DIR, exist_ok=True)
    # Hash the cache key to create a safe filename
    key_hash = hashlib.md5(cache_key.encode()).hexdigest()
    return os.path.join(DISK_CACHE_DIR, f'{key_hash}.pkl')

def load_from_disk_cache(cache_key):
    """Load data from disk cache if valid"""
    try:
        cache_path = get_disk_cache_path(cache_key)
        if not os.path.exists(cache_path):
            return None

        # Check if cache is still valid
        cache_age = time.time() - os.path.getmtime(cache_path)
        if cache_age > DISK_CACHE_TTL:
            os.remove(cache_path)
            return None

        with open(cache_path, 'rb') as f:
            return pickle.load(f)
    except Exception as e:
        logger.debug(f"Error loading from disk cache: {e}")
        return None

def save_to_disk_cache(cache_key, data):
    """Save data to disk cache"""
    try:
        cache_path = get_disk_cache_path(cache_key)
        with open(cache_path, 'wb') as f:
            pickle.dump(data, f)
    except Exception as e:
        logger.debug(f"Error saving to disk cache: {e}")

# GCS cache helper functions
def get_gcs_cache_key(cache_key):
    """Get GCS object path for cache"""
    key_hash = hashlib.md5(cache_key.encode()).hexdigest()
    return f'{GCS_CACHE_PREFIX}{key_hash}.pkl'

def load_from_gcs_cache(cache_key):
    """Load data from GCS cache if valid"""
    if not GCS_CACHE_ENABLED:
        return None

    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_CACHE_BUCKET)
        blob_name = get_gcs_cache_key(cache_key)
        blob = bucket.blob(blob_name)

        if not blob.exists():
            return None

        # Check if cache is still valid
        blob.reload()
        cache_age = (datetime.now(blob.updated.tzinfo) - blob.updated).total_seconds()
        if cache_age > GCS_CACHE_TTL:
            blob.delete()
            logger.debug(f"GCS cache expired for {cache_key}")
            return None

        # Download and deserialize
        data_bytes = blob.download_as_bytes()
        data = pickle.loads(data_bytes)
        logger.debug(f"✓ Loaded from GCS cache: {cache_key}")
        return data
    except Exception as e:
        logger.debug(f"Error loading from GCS cache: {e}")
        return None

def save_to_gcs_cache(cache_key, data):
    """Save data to GCS cache"""
    if not GCS_CACHE_ENABLED:
        return

    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_CACHE_BUCKET)
        blob_name = get_gcs_cache_key(cache_key)
        blob = bucket.blob(blob_name)

        # Serialize and upload
        data_bytes = pickle.dumps(data)
        blob.upload_from_string(data_bytes, content_type='application/octet-stream')
        logger.debug(f"✓ Saved to GCS cache: {cache_key}")
    except Exception as e:
        logger.debug(f"Error saving to GCS cache: {e}")

# JSON Data Loading Functions (Hybrid Approach)
def load_json_from_local(filename):
    """Load JSON data from local filesystem"""
    try:
        filepath = os.path.join(JSON_DATA_CONFIG['local_dir'], filename)
        if not os.path.exists(filepath):
            logger.debug(f"Local JSON file not found: {filepath}")
            return None

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Check if data is fresh (within last 48 hours)
        if 'last_updated' in data:
            last_updated = datetime.fromisoformat(data['last_updated'])
            age_hours = (datetime.now() - last_updated).total_seconds() / 3600
            if age_hours > 48:
                logger.warning(f"⚠️ Local JSON data is {age_hours:.1f} hours old (stale)")

        logger.info(f"✅ Loaded {filename} from local filesystem ({len(json.dumps(data))} bytes)")
        return data

    except Exception as e:
        logger.error(f"Error loading local JSON {filename}: {e}")
        return None


def load_json_from_gcs(filename):
    """Load JSON data from Google Cloud Storage"""
    try:
        from google.cloud import storage

        storage_client = storage.Client()
        bucket = storage_client.bucket(JSON_DATA_CONFIG['gcs_bucket'])
        blob = bucket.blob(filename)

        if not blob.exists():
            logger.debug(f"GCS file not found: {filename}")
            return None

        json_string = blob.download_as_text()
        data = json.loads(json_string)

        logger.info(f"☁️ Loaded {filename} from Cloud Storage ({len(json_string)} bytes)")
        return data

    except ImportError:
        logger.warning("google-cloud-storage not installed, cannot use GCS")
        return None
    except Exception as e:
        logger.error(f"Error loading from GCS {filename}: {e}")
        return None


def load_json_data(filename):
    """
    Load JSON data with fallback strategy:
    1. Try Cloud Storage (if enabled)
    2. Try local filesystem
    3. Return None (caller should fall back to Google Sheets)
    """
    data = None

    # Try Cloud Storage first (if enabled)
    if JSON_DATA_CONFIG['use_gcs']:
        data = load_json_from_gcs(filename)
        if data:
            return data

    # Try local filesystem
    data = load_json_from_local(filename)
    if data:
        return data

    logger.debug(f"No JSON data found for {filename}, will fall back to Google Sheets")
    return None


def load_employees_from_json():
    """Load employee data from JSON with fallback to Google Sheets"""
    if not JSON_DATA_CONFIG['enabled']:
        logger.debug("JSON data source disabled, using Google Sheets")
        return None

    try:
        logger.info("📂 Attempting to load employees from JSON...")
        json_data = load_json_data('employees.json')

        if not json_data or 'employees' not in json_data:
            logger.warning("Invalid or missing employees data in JSON")
            return None

        employees = json_data['employees']
        stats = json_data.get('stats', {})
        last_updated = json_data.get('last_updated', 'Unknown')

        logger.info(f"✅ Loaded {len(employees)} employees from JSON (last updated: {last_updated})")
        return employees, stats

    except Exception as e:
        logger.error(f"Error loading employees from JSON: {e}")
        return None


def load_connections_from_json():
    """Load connections data from JSON with fallback to Google Sheets"""
    if not JSON_DATA_CONFIG['enabled']:
        logger.debug("JSON data source disabled, using Google Sheets")
        return None

    try:
        logger.info("🔗 Attempting to load connections from JSON...")
        json_data = load_json_data('connections.json')

        if not json_data or 'connections' not in json_data:
            logger.warning("Invalid or missing connections data in JSON")
            return None

        connections = json_data['connections']
        last_updated = json_data.get('last_updated', 'Unknown')

        logger.info(f"✅ Loaded {len(connections)} connections from JSON (last updated: {last_updated})")
        return connections

    except Exception as e:
        logger.error(f"Error loading connections from JSON: {e}")
        return None


def load_credentials_from_json():
    """Load credentials data from JSON with fallback to Google Sheets"""
    if not JSON_DATA_CONFIG['enabled']:
        logger.debug("JSON data source disabled, using Google Sheets")
        return None

    try:
        logger.info("🔐 Attempting to load credentials from JSON...")
        json_data = load_json_data('credentials.json')

        if not json_data or 'credentials' not in json_data:
            logger.warning("Invalid or missing credentials data in JSON")
            return None

        credentials = json_data['credentials']
        logger.info(f"✅ Loaded {len(credentials)} credentials from JSON")
        return credentials

    except Exception as e:
        logger.error(f"Error loading credentials from JSON: {e}")
        return None

# Application startup optimization - preload data
@lru_cache(maxsize=1)
def get_sheet_data_bulk():
    """Load all sheet data in one batch to minimize API calls"""
    try:
        # Load employee data from Google Sheets
        employees, stats = processor.process_google_sheets_data_optimized()

        # Load connections data from Google Sheets using cached function
        connections_data = get_cached_connections_data()

        logger.debug(f"🚀 Bulk loaded {len(employees) if employees else 0} employees, {len(connections_data) if connections_data else 0} connections from Google Sheets")
        return employees, connections_data

    except Exception as e:
        logger.error(f"❌ Bulk data load failed: {e}")
        return None, None

@lru_cache(maxsize=5000)  # Increased cache size for better performance
def get_employee_by_ldap(ldap: str):
    """Cached employee lookup by LDAP (case-insensitive) using Google Sheets"""
    if not ldap:
        return None

    # Search in the global employees_data cache
    if employees_data:
        ldap_lower = ldap.lower()
        for emp in employees_data:
            if emp.get('ldap', '').lower() == ldap_lower:
                return emp
    return None

def build_search_index():
    """Build search index for faster employee lookups"""
    global employee_search_index

    logger.debug("Building search index...")
    start_time = time.time()

    # Clear existing index
    employee_search_index['by_name'] = {}
    employee_search_index['by_ldap'] = {}
    employee_search_index['by_email'] = {}

    for emp in employees_data:
        ldap = emp.get('ldap', '').lower()
        name = emp.get('name', '').lower()
        email = emp.get('email', '').lower()

        # Index by LDAP (exact match)
        if ldap:
            if ldap not in employee_search_index['by_ldap']:
                employee_search_index['by_ldap'][ldap] = []
            employee_search_index['by_ldap'][ldap].append(emp)

        # Index by name tokens (for partial matching)
        if name:
            name_tokens = name.split()
            for token in name_tokens:
                if len(token) >= 2:  # Only index tokens with 2+ characters
                    if token not in employee_search_index['by_name']:
                        employee_search_index['by_name'][token] = []
                    employee_search_index['by_name'][token].append(emp)

        # Index by email prefix
        if email:
            email_prefix = email.split('@')[0].lower()
            if email_prefix not in employee_search_index['by_email']:
                employee_search_index['by_email'][email_prefix] = []
            employee_search_index['by_email'][email_prefix].append(emp)

    employee_search_index['last_built'] = datetime.now()
    elapsed = time.time() - start_time
    logger.debug(f"Search index built in {elapsed:.2f}s")

def get_cached_connections_data():
    """Get cached connections data from Google Sheets (with in-memory caching for performance)"""
    global cached_connections_data, connections_cache_time

    current_time = time.time()

    # Check disk cache first
    disk_data = load_from_disk_cache('connections_data')
    if disk_data:
        logger.debug(f"💾 Using disk-cached connections data ({len(disk_data)} records)")
        cached_connections_data = disk_data
        connections_cache_time = current_time
        return cached_connections_data

    # Check if cache is valid
    if (cached_connections_data is not None and
        connections_cache_time is not None and
        current_time - connections_cache_time < connections_cache_ttl):
        logger.debug(f"📋 Using cached connections data ({len(cached_connections_data)} records)")
        return cached_connections_data

    # Cache is stale or doesn't exist, fetch fresh data
    try:
        # Try loading from JSON first (hybrid approach for faster loading)
        json_connections = load_connections_from_json()
        if json_connections:
            logger.info(f"🚀 Loaded {len(json_connections)} connections from JSON (FAST PATH)")
            records = json_connections
        else:
            # Fall back to Google Sheets if JSON not available
            logger.debug("🔄 Refreshing connections cache from Google Sheets...")
            records = _read_connections_from_sheets_internal()

        cached_connections_data = records if records else []
        connections_cache_time = current_time

        # Save to disk cache
        save_to_disk_cache('connections_data', cached_connections_data)

        logger.debug(f"✅ Cached {len(cached_connections_data)} connections records (memory + disk)")
        return cached_connections_data

    except Exception as e:
        logger.error(f"❌ Error refreshing connections cache: {e}")
        # Return stale cache if available, otherwise empty list
        if cached_connections_data is not None:
            logger.warning("⚠️ Using stale cache due to error")
            return cached_connections_data
        return []

def invalidate_connections_cache():
    """Invalidate the connections cache to force refresh on next access"""
    global cached_connections_data, connections_cache_time, connections_result_cache, global_employees_cache, global_employees_cache_time
    cached_connections_data = None
    connections_cache_time = None
    connections_result_cache.clear()  # Clear computed connections cache
    global_employees_cache = None  # Clear employees cache to force reload with new connections
    global_employees_cache_time = None

    # Clear LRU caches
    get_sheet_data_bulk.cache_clear()  # Clear bulk data cache
    get_employee_by_ldap.cache_clear()  # Clear employee lookup cache

    logger.debug("🔄 All caches invalidated (including LRU caches) - next request will fetch fresh data")

def calculate_actual_organizational_path(from_employee_ldap, to_employee_ldap):
    """
    Calculate the actual number of intermediate employees between two employees in the org chart.
    Returns the count of intermediate employees (not including the from and to employees).
    """
    try:
        from_emp = get_employee_by_ldap(from_employee_ldap)
        to_emp = get_employee_by_ldap(to_employee_ldap)

        if not from_emp or not to_emp:
            logger.debug(f"    Path calc: Employee not found (from: {from_employee_ldap}, to: {to_employee_ldap})")
            return 1  # Default if employees not found

        from_name = from_emp.get('name', from_employee_ldap)
        to_name = to_emp.get('name', to_employee_ldap)

        # Build manager chains for both employees
        from_chain = []  # List of ldaps going up from from_emp
        to_chain = []    # List of ldaps going up to_emp

        # Build from_emp's manager chain (including placeholder managers)
        current = from_emp
        visited = set()
        max_depth = 20
        depth = 0
        while current and depth < max_depth:
            depth += 1
            manager_ldap = None

            # Try manager_info first
            if current.get('manager_info'):
                manager_ldap = current['manager_info']['ldap']
            # Fall back to manager field
            elif current.get('manager'):
                manager_email = current['manager']
                manager_ldap = manager_email.split('@')[0] if '@' in manager_email else manager_email

            if not manager_ldap or manager_ldap in visited:
                break

            visited.add(manager_ldap)
            from_chain.append(manager_ldap)
            current = get_employee_by_ldap(manager_ldap)
            # Continue even if employee not found (to count placeholder managers)

        # Build to_emp's manager chain (including placeholder managers)
        current = to_emp
        visited = set()
        depth = 0
        while current and depth < max_depth:
            depth += 1
            manager_ldap = None

            # Try manager_info first
            if current.get('manager_info'):
                manager_ldap = current['manager_info']['ldap']
            # Fall back to manager field
            elif current.get('manager'):
                manager_email = current['manager']
                manager_ldap = manager_email.split('@')[0] if '@' in manager_email else manager_email

            if not manager_ldap or manager_ldap in visited:
                break

            visited.add(manager_ldap)
            to_chain.append(manager_ldap)
            current = get_employee_by_ldap(manager_ldap)
            # Continue even if employee not found (to count placeholder managers)

        logger.debug(f"    Path calc: {from_name} chain length: {len(from_chain)}, {to_name} chain length: {len(to_chain)}")

        # Check if they're the same person
        if from_employee_ldap.lower() == to_employee_ldap.lower():
            logger.debug(f"    Path calc: Same person → 0 intermediates")
            return 0

        # Check if to_emp is from_emp's direct manager
        if from_chain and from_chain[0].lower() == to_employee_ldap.lower():
            # Path: from_emp -> to_emp (2 people total)
            # Excluding from_emp: 1 (just to_emp)
            logger.debug(f"    Path calc: {to_name} is direct manager of {from_name} → 1 person (excluding searched)")
            return 1

        # Check if from_emp is to_emp's direct manager
        if to_chain and to_chain[0].lower() == from_employee_ldap.lower():
            # Path: from_emp -> to_emp (2 people total)
            # Excluding from_emp: 1 (just to_emp)
            logger.debug(f"    Path calc: {from_name} is direct manager of {to_name} → 1 person (excluding searched)")
            return 1

        # Check if they share the same direct manager (peers/siblings)
        if from_chain and to_chain and from_chain[0].lower() == to_chain[0].lower():
            # Path: from_emp -> shared_manager -> to_emp (3 people total)
            # Excluding from_emp: 2 (shared_manager + to_emp)
            shared_mgr = get_employee_by_ldap(from_chain[0])
            logger.debug(f"    Path calc: Peers under {shared_mgr.get('name') if shared_mgr else from_chain[0]} → 2 people (excluding searched)")
            return 2

        # Check if to_emp is somewhere in from_emp's manager chain
        if to_employee_ldap.lower() in [m.lower() for m in from_chain]:
            position = [m.lower() for m in from_chain].index(to_employee_ldap.lower())
            # Path: from_emp -> manager1 -> ... -> to_emp
            # Total people: position + 2 (from_emp + position+1 managers including to_emp)
            # Excluding from_emp: position + 1
            count = position + 1
            logger.debug(f"    Path calc: {to_name} is at position {position} in {from_name}'s manager chain → {count} people (excluding searched)")
            return count

        # Check if from_emp is somewhere in to_emp's manager chain
        if from_employee_ldap.lower() in [m.lower() for m in to_chain]:
            position = [m.lower() for m in to_chain].index(from_employee_ldap.lower())
            # Path: from_emp -> managers down -> to_emp
            # Total people: position + 2
            # Excluding from_emp: position + 1
            count = position + 1
            logger.debug(f"    Path calc: {from_name} is at position {position} in {to_name}'s manager chain → {count} people (excluding searched)")
            return count

        # Find the lowest common manager (shared manager in the hierarchy)
        for i, from_manager in enumerate(from_chain):
            for j, to_manager in enumerate(to_chain):
                if from_manager.lower() == to_manager.lower():
                    # Path: from_emp -> i managers -> common_mgr -> j managers -> to_emp
                    # Total: 1 + i + 1 + j + 1 = i + j + 3
                    # Excluding from_emp: i + j + 2
                    shared_mgr = get_employee_by_ldap(from_manager)
                    shared_name = shared_mgr.get('name') if shared_mgr else from_manager
                    count = i + j + 2
                    logger.debug(f"    Path calc: Shared manager {shared_name} at positions ({i}, {j}) → {count} people (excluding searched)")
                    return count

        # No common manager found - they're in different hierarchies
        # Path: from_emp -> all from_chain -> all to_chain -> to_emp
        # Total: 1 + len(from_chain) + len(to_chain) + 1
        # Excluding from_emp: len(from_chain) + len(to_chain) + 1
        estimate = len(from_chain) + len(to_chain) + 1
        logger.debug(f"    Path calc: No common manager found → estimate {estimate} people (excluding searched)")
        return estimate

    except Exception as e:
        logger.warning(f"Error calculating organizational path: {e}")
        return 1

def calculate_path_length_to_qt_employee(google_ldap, qt_ldap, hierarchy, connection_strength=None):
    """Calculate the number of intermediate employees to traverse from Google employee to QT employee"""
    try:
        # Get the QT employee info
        qt_employee = next((emp for emp in core_team if emp.get('ldap') == qt_ldap), None)
        if not qt_employee:
            return 1  # Default if QT employee not found

        google_employee = get_employee_by_ldap(google_ldap)
        if not google_employee or not hierarchy:
            return 1  # Default if no hierarchy available

        # For declared connections in Google Sheets, path length depends on connection strength
        if connection_strength:
            strength = connection_strength.lower().strip()
            if strength == 'strong':
                return 0  # Direct working relationship, no intermediates
            elif strength == 'medium':
                return 1  # Connection through 1 intermediate (e.g., shared project/team)
            elif strength == 'weak':
                return 2  # Connection through 2+ intermediates (distant relationship)

        # Default case: assume direct relationship for declared connections
        return 0

    except Exception as e:
        logger.debug(f"Error calculating path length from {google_ldap} to {qt_ldap}: {e}")
        return 1  # Default to 1 intermediate employee on error

class OptimizedGoogleSheetsConnector:
    """Optimized Google Sheets connector with better performance"""
    
    def __init__(self, config):
        self.config = config
        self.client = None
        self.spreadsheet = None
        
    def authenticate(self):
        """Optimized authentication with error handling"""
        try:
            logger.debug("Authenticating with Google Sheets API...")
            
            if os.path.exists(self.config['service_account_file']):
                logger.debug(f"Using service account file: {self.config['service_account_file']}")
                creds = Credentials.from_service_account_file(
                    self.config['service_account_file'],
                    scopes=self.config['scopes']
                )
                self.client = gspread.authorize(creds)
                logger.debug("Authentication successful")
                return True
                
            elif 'GOOGLE_SERVICE_ACCOUNT_JSON' in os.environ:
                logger.debug("Using service account from environment variable")
                service_account_info = json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON'])
                creds = Credentials.from_service_account_info(
                    service_account_info,
                    scopes=self.config['scopes']
                )
                self.client = gspread.authorize(creds)
                logger.debug("Authentication successful with environment credentials")
                return True
                
            else:
                logger.error("No credentials found")
                self.create_sample_credentials_file()
                return False
                
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    def create_sample_credentials_file(self):
        """Create sample credentials template"""
        sample_creds = {
            "type": "service_account",
            "project_id": "your-project-id",
            "private_key_id": "your-private-key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY\n-----END PRIVATE KEY-----\n",
            "client_email": "your-service-account@your-project.iam.gserviceaccount.com",
            "client_id": "your-client-id",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/your-service-account%40your-project.iam.gserviceaccount.com"
        }
        
        with open('credentials_template.json', 'w') as f:
            json.dump(sample_creds, f, indent=2)
        
        logger.debug("Created 'credentials_template.json' template")
    
    def connect_to_spreadsheet(self):
        """Optimized spreadsheet connection"""
        try:
            logger.debug(f"Connecting to spreadsheet: {self.config['spreadsheet_id']}")
            
            if not self.client:
                if not self.authenticate():
                    return False
            
            self.spreadsheet = self.client.open_by_key(self.config['spreadsheet_id'])
            logger.debug(f"Connected to: {self.spreadsheet.title}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    def get_sheet_data_optimized(self, sheet_name=None):
        """Optimized data retrieval with batching"""
        try:
            if not self.spreadsheet:
                if not self.connect_to_spreadsheet():
                    return None
            
            sheet_name = sheet_name or self.config.get('sheet_name', 'Sheet1')
            logger.debug(f"Getting data from sheet: {sheet_name}")
            
            try:
                worksheet = self.spreadsheet.worksheet(sheet_name)
            except:
                worksheet = self.spreadsheet.sheet1
                logger.warning(f"Sheet '{sheet_name}' not found, using first sheet: {worksheet.title}")
            
            # Get all values at once (more efficient than row-by-row)
            # Apply rate limiting to prevent API quota errors
            api_rate_limiter.wait_if_needed()
            all_values = worksheet.get_all_values()
            logger.debug(f"Raw values retrieved from {sheet_name}: {len(all_values)} rows")
            
            if not all_values or len(all_values) < 2:
                logger.error("No data found or insufficient data")
                return None
            
            # Safety check for large datasets
            if len(all_values) > self.config['max_employees']:
                logger.warning(f"Large dataset detected ({len(all_values)} rows), limiting to {self.config['max_employees']}")
                all_values = all_values[:self.config['max_employees']]
            logger.debug(f"Values after max_employees check: {len(all_values)} rows")
            
            logger.debug(f"Retrieved {len(all_values)} rows from sheet")
            
            # Create DataFrame more efficiently
            headers = all_values[0]
            data_rows = all_values[1:]
            
            # Filter out completely empty rows upfront
            data_rows = [row for row in data_rows if any(cell.strip() for cell in row)]
            
            if not data_rows:
                logger.error("No valid data rows found")
                return None
            
            df = pd.DataFrame(data_rows, columns=headers)
            logger.debug(f"Created DataFrame: {len(df)} rows, {len(df.columns)} columns")
            
            return df
                
        except Exception as e:
            logger.error(f"Error getting sheet data: {e}")
            return None
    
    def create_sample_data(self):
        """Create sample data based on actual Google Sheets structure"""
        logger.debug("Creating sample data matching Google Sheets structure...")
        
        # Sample data that matches your actual Google Sheets columns and some real data
        sample_data = [
            ["Name", "Position", "Department", "Country", "LDAP", "MOMA URL", "Manager Email", "MOMA Photo URL"],
            
            # Real employees from your sheet
            ["Niko Repo", "CSRM Data Center Security Manager", "Operations - CSRM", "Finland", "nrepo", "", "", ""],
            ["Ashwin Kumar", "Senior Engineering Manager", "Engineering", "India", "ashwink", "", "sarah.wilson@google.com", ""],
            ["Chanda", "Support Team - GL", "Engineering - Core ML Infra", "N/A", "cdangi", "", "mutthar@google.com", ""],
            ["Hacker", "Analyst", "Engineering - Core ML Infra", "N/A", "hackerj", "", "ashwink@google.com", ""],
            ["Agave", "Earth Platforms Developer Advocate", "Engineering - Earth Platforms", "N/A", "agv", "", "ryanbateman@google.com", ""],
            
            # Managers
            ["Sarah Wilson", "VP Engineering", "Engineering", "USA", "sarah.wilson", "", "", ""],
            ["Mutthar", "Manager", "Engineering - Core ML Infra", "N/A", "mutthar", "", "sarah.wilson@google.com", ""],
            
            # QT Team members
            ["Lihi Segev", "Executive Vice President", "Account Management and Delivery", "Israel", "lihis", "", "", ""],
            ["Abhijeet Bagade", "Vice President", "Account Management and Delivery", "UK", "a.bagade", "", "", ""],
            ["Omri Nissim", "Vice President", "Account Management and Delivery", "Israel", "omrinis", "", "", ""],
            ["Kobi Kol", "Associate Vice President", "Account Management and Delivery", "Israel", "kobi.kol", "", "", ""],
            ["Jillian OrRico", "Vice President", "Sales", "USA", "jillian.orrico", "", "", ""],
            ["Michael Bush", "Associate Vice President", "Account Management and Delivery", "USA", "michael.bush", "", "", ""],
            ["Mayank Arya", "Associate Vice President", "Account Management and Delivery", "UK", "mayank.arya", "", "", ""],
        ]
        
        df = pd.DataFrame(sample_data[1:], columns=sample_data[0])
        logger.debug(f"Created sample data matching Google Sheets: {len(df)} rows")
        return df
        
class OptimizedGoogleSheetsProcessor:
    """Optimized processor with better memory management"""
    
    def __init__(self, config):
        self.config = config
        self.connector = OptimizedGoogleSheetsConnector(config)
        
    def detect_column_mapping(self, columns):
        """Optimized column mapping detection for actual Google Sheets structure"""
        mapping = {}
        columns_lower = [str(col).lower().strip() for col in columns]
        
        logger.debug(f"Analyzing {len(columns)} columns: {columns}")
        
        # Map based on your actual Google Sheets columns
        for i, col in enumerate(columns):
            col_lower = str(col).lower().strip()
            
            if col_lower in ['name']:
                mapping['name'] = col
            elif col_lower in ['position']:
                mapping['title'] = col
            elif col_lower in ['department']:
                mapping['department'] = col
            elif col_lower in ['country']:
                mapping['location'] = col
            elif col_lower in ['ldap']:
                mapping['id'] = col
            elif col_lower in ['manager email']:
                mapping['manager'] = col
            elif col_lower in ['moma photo url']:
                mapping['avatar'] = col
        
        logger.debug(f"Column mapping detected: {mapping}")
        return mapping
    
    def extract_employee_data_optimized(self, row, column_mapping, index):
        """Extract employee data based on actual Google Sheets structure"""
        try:
            # Quick validation - skip obviously invalid rows
            if all(str(val).strip() == '' for val in row.values):
                return None
            
            # Extract core data efficiently based on your Google Sheets columns
            name = self.safe_extract(row, column_mapping.get('name'), f'Employee {index}')
            emp_id = self.safe_extract(row, column_mapping.get('id'), f'emp{index:04d}')
            
            # Skip invalid entries early
            if not name or name == f'Employee {index}' or not emp_id:
                return None
            
            # Extract remaining fields based on your sheet structure
            position = self.safe_extract(row, column_mapping.get('title'), 'Unknown Position')
            department = self.safe_extract(row, column_mapping.get('department'), 'Unknown')
            country = self.safe_extract(row, column_mapping.get('location'), 'Unknown')
            manager_email = self.safe_extract(row, column_mapping.get('manager'), '')
            avatar_url = self.safe_extract(row, column_mapping.get('avatar'), '')
            
            # Generate email based on LDAP and determine organization
            email = f"{emp_id}@google.com"
            organisation = 'Google'
            company = 'GOOGLE'
            
            # Handle QT team members (Qualitest employees)
            qt_ldaps = ['lihi.segev', 'abhijeet.bagade', 'omri.nissim', 'kobi.kol', 
                       'jillian.orrico', 'michael.bush', 'mayank.arya']
            
            if emp_id.lower() in qt_ldaps:
                email = f"{emp_id}@qualitestgroup.com"
                organisation = 'Qualitest' 
                company = 'QUALITEST'
            
            # Only use avatar_url if it's a valid MOMA Photo URL, otherwise leave empty for initials fallback
            if not avatar_url or avatar_url in ['Unknown', '', 'N/A']:
                avatar_url = ''
            
            # Create employee object matching your data structure
            employee = {
                'ldap': str(emp_id).strip(),
                'name': str(name).strip(),
                'email': str(email).strip(),
                'company': str(company).strip().upper(),
                'designation': str(position).strip(),
                'department': str(department).strip(),
                'location': str(country).strip(),
                'manager': str(manager_email).strip(),  # Store manager email as is
                'organisation': organisation,
                'avatar': avatar_url,
                'connections': [],
                'row_index': index,
                'data_source': 'Google Sheets'
            }
            
            logger.debug(f"Processed employee: {name} ({emp_id}) - Manager: {manager_email}")
            return employee
            
        except Exception as e:
            logger.warning(f"Error processing row {index}: {e}")
            return None
    
    def safe_extract(self, row, column_name, default=''):
        """Optimized safe extraction"""
        if not column_name or column_name not in row.index:
            return default
        
        try:
            value = row[column_name]
            if pd.notna(value):
                cleaned = str(value).strip()
                if cleaned and cleaned.lower() not in ['nan', 'none', 'null', '#n/a', 'na', '', '-']:
                    return cleaned
        except:
            pass
        
        return default
    
    def process_google_sheets_data_optimized(self):
        """Optimized main processing with memory management"""
        start_time = datetime.now()
        
        try:
            logger.debug("Starting optimized Google Sheets processing...")
            
            # Get data from primary sheet (Sheet1)
            df_primary = self.connector.get_sheet_data_optimized(sheet_name=self.config.get('sheet_name', 'Sheet1'))
            
            # Get data from Connections sheet
            df_connections = None
            try:
                connections_sheet = self.connector.spreadsheet.worksheet('Connections')
                # Apply rate limiting to prevent API quota errors
                api_rate_limiter.wait_if_needed()
                all_connections_values = connections_sheet.get_all_values()
                if all_connections_values and len(all_connections_values) > 1:
                    headers = all_connections_values[0]
                    data_rows = all_connections_values[1:]
                    data_rows = [row for row in data_rows if any(cell.strip() for cell in row)]
                    if data_rows:
                        df_connections = pd.DataFrame(data_rows, columns=headers)
                        logger.debug(f"Retrieved {len(df_connections)} rows from Connections sheet")
            except gspread.WorksheetNotFound:
                logger.warning("Connections sheet not found, skipping employee data extraction from it.")
            except Exception as e:
                logger.error(f"Error reading Connections sheet for employee data: {e}")

            # Combine dataframes and extract unique Google Employee profiles from Connections sheet
            all_employees_df = df_primary.copy() if df_primary is not None else pd.DataFrame()

            if df_connections is not None and not df_connections.empty:
                # Extract unique Google Employee profiles from Connections sheet
                google_employees_from_connections = df_connections[[
                    'Google Employee LDAP',
                    'Google Employee Name',
                    'Google Employee Email',
                    'Google Employee Department'
                ]].drop_duplicates().rename(columns={
                    'Google Employee LDAP': 'LDAP',
                    'Google Employee Name': 'Name',
                    'Google Employee Email': 'Email',
                    'Google Employee Department': 'Department'
                })
                
                # Add missing columns to match primary sheet structure (e.g., Position, Country)
                for col in df_primary.columns:
                    if col not in google_employees_from_connections.columns:
                        google_employees_from_connections[col] = '' # Fill with empty string or appropriate default

                # Ensure column order matches for concatenation
                google_employees_from_connections = google_employees_from_connections[df_primary.columns]

                # Concatenate and drop duplicates based on LDAP
                all_employees_df = pd.concat([all_employees_df, google_employees_from_connections], ignore_index=True)
                all_employees_df.drop_duplicates(subset=['LDAP'], inplace=True)
                logger.debug(f"Merged employee data from primary and Connections sheets. Total unique employees: {len(all_employees_df)}")

            df = all_employees_df
            
            if df is None or df.empty:
                logger.warning("Could not access Google Sheets - using sample data")
                df = self.connector.create_sample_data()
                data_source = 'Sample Data (Google Sheets failed)'
            else:
                data_source = 'Google Sheets'
            
            # Optimized DataFrame cleaning
            logger.debug("Cleaning DataFrame...")
            original_rows = len(df)
            
            # Remove empty rows more efficiently
            df = df.dropna(how='all')
            # Fix: Apply string operations correctly
            df = df[~df.apply(lambda row: all(str(cell).strip() == '' for cell in row), axis=1)]
            
            logger.debug(f"Cleaned DataFrame: {len(df)} rows (removed {original_rows - len(df)} empty rows)")
            
            # Detect column mapping
            column_mapping = self.detect_column_mapping(df.columns)
            
            # Initialize processing stats
            stats = {
                'total_rows': len(df),
                'processed_rows': 0,
                'skipped_rows': 0,
                'google_employees': 0,
                'qualitest_employees': 0,
                'other_employees': 0,
                'source': data_source,
                'columns_found': list(df.columns),
                'column_mapping': column_mapping,
                'spreadsheet_id': self.config['spreadsheet_id'],
                'processing_method': 'Optimized Batch Processing'
            }
            
            # Process in batches for better memory management
            employees = []
            batch_size = self.config['batch_size']
            total_batches = (len(df) + batch_size - 1) // batch_size
            
            logger.debug(f"Processing {len(df)} rows in {total_batches} batches of {batch_size}")
            
            for batch_num in range(total_batches):
                batch_start = batch_num * batch_size
                batch_end = min(batch_start + batch_size, len(df))
                batch_df = df.iloc[batch_start:batch_end]
                
                # Process batch
                batch_employees = []
                for index, row in batch_df.iterrows():
                    employee = self.extract_employee_data_optimized(row, column_mapping, index)
                    if employee:
                        batch_employees.append(employee)
                        stats['processed_rows'] += 1
                        
                        # Update organization counts
                        if employee['organisation'] == 'Google':
                            stats['google_employees'] += 1
                        elif employee['organisation'] == 'Qualitest':
                            stats['qualitest_employees'] += 1
                        else:
                            stats['other_employees'] += 1
                    else:
                        stats['skipped_rows'] += 1
                
                # Add batch to main list
                employees.extend(batch_employees)
                
                # Progress logging disabled to reduce terminal output
                
                # Memory cleanup every few batches
                if batch_num % 10 == 0:
                    gc.collect()
            
            # Final cleanup
            del df
            gc.collect()
            
            stats['processing_time'] = (datetime.now() - start_time).total_seconds()
            
            logger.debug("Optimized processing complete!")
            logger.debug(f"Total processed: {len(employees):,} profiles")
            logger.debug(f"Google employees: {stats['google_employees']:,}")
            logger.debug(f"Qualitest employees: {stats['qualitest_employees']:,}")
            logger.debug(f"Other employees: {stats['other_employees']:,}")
            logger.debug(f"Processing time: {stats['processing_time']:.2f} seconds")
            
            return employees, stats
            
        except Exception as e:
            logger.error(f"Error in optimized processing: {e}")
            return None, None

# Initialize optimized processor
processor = OptimizedGoogleSheetsProcessor(GOOGLE_SHEETS_CONFIG)

def load_google_sheets_data_optimized():
    """Optimized data loading with proper organizational hierarchy building"""
    global employees_data, google_employees, core_team, processing_stats, last_sync_time
    global global_employees_cache, global_employees_cache_time

    try:
        # Check disk cache first (survives instance restarts)
        disk_data = load_from_disk_cache('employees_data_full')
        if disk_data:
            logger.debug(f"💾 Using disk-cached employee data ({len(disk_data['employees'])} records)")
            employees_data = disk_data['employees']
            google_employees = disk_data.get('google_employees', [])
            core_team = disk_data.get('core_team', [])
            processing_stats = disk_data.get('processing_stats', {})
            last_sync_time = disk_data.get('last_sync_time')
            global_employees_cache = employees_data
            global_employees_cache_time = time.time()
            build_search_index()
            return True

        # Check if we have cached data that's still valid
        current_time = time.time()
        if (global_employees_cache is not None and
            global_employees_cache_time is not None and
            current_time - global_employees_cache_time < employees_cache_ttl):
            logger.debug(f"📋 Using cached employee data ({len(global_employees_cache)} records)")
            employees_data = global_employees_cache
            return True

        # Try loading from JSON first (hybrid approach for faster loading)
        json_result = load_employees_from_json()
        if json_result:
            employees, stats = json_result
            logger.info(f"🚀 Loaded {len(employees)} employees from JSON (FAST PATH)")
        else:
            # Fall back to Google Sheets if JSON not available
            logger.debug("Loading Google Sheets data with optimizations...")
            employees, stats = processor.process_google_sheets_data_optimized()
        
        if not employees:
            logger.error("No employee data processed")
            return False
        
        # Clear cache before loading new data
        get_employee_by_ldap.cache_clear()
        
        # Store data efficiently
        employees_data = employees
        processing_stats = stats
        last_sync_time = datetime.now()

        # Cache the data for future requests
        global_employees_cache = employees
        global_employees_cache_time = current_time

        # Build search index for performance
        build_search_index()

        # Build organizational relationships from manager data
        build_organizational_hierarchy()
        
        # Optimized categorization using list comprehensions
        google_employees = [emp for emp in employees if emp.get('organisation') == 'Google']
        qualitest_employees = [emp for emp in employees if emp.get('organisation') == 'Qualitest']
        
        # Initialize core team (limited for performance)
        core_team = qualitest_employees[:min(50, len(qualitest_employees))]
        for team_member in core_team:
            team_member['connections'] = []
        
        # Calculate unique counts efficiently
        departments = len(set(emp.get('department', 'Unknown') for emp in employees))
        locations = len(set(emp.get('location', 'Unknown') for emp in employees))
        
        logger.debug(f"Successfully loaded employee data:")
        logger.debug(f"Total: {len(employees_data):,}")
        logger.debug(f"Google: {len(google_employees):,}")
        logger.debug(f"Qualitest: {len(qualitest_employees):,}")
        logger.debug(f"Departments: {departments}")
        logger.debug(f"Locations: {locations}")

        # Save to disk cache for faster subsequent loads
        save_to_disk_cache('employees_data_full', {
            'employees': employees_data,
            'google_employees': google_employees,
            'core_team': core_team,
            'processing_stats': processing_stats,
            'last_sync_time': last_sync_time
        })
        logger.debug("💾 Saved employee data to disk cache")

        return True
        
    except Exception as e:
        logger.error(f"Error loading optimized data: {e}")
        return False

def build_organizational_hierarchy():
    """Build proper manager-reportee relationships from Google Sheets data"""
    try:
        logger.debug("Building organizational hierarchy from manager email relationships...")
        
        # First, create a mapping of email to employee for faster lookup
        email_to_employee = {}
        for employee in employees_data:
            if employee.get('email'):
                email_to_employee[employee['email']] = employee
        
        # Now build the hierarchy relationships
        for employee in employees_data:
            manager_email = employee.get('manager', '').strip()
            
            if manager_email and manager_email in email_to_employee:
                manager = email_to_employee[manager_email]
                
                # Skip self-reporting relationships (like nrepo@google.com reporting to itself)
                if manager['ldap'] == employee['ldap']:
                    logger.debug(f"Skipping self-reporting relationship for {employee['name']}")
                    continue
                
                # Initialize reportees list if not exists
                if 'reportees' not in manager:
                    manager['reportees'] = []
                
                # Add this employee as a reportee
                manager['reportees'].append({
                    'ldap': employee.get('ldap'),
                    'name': employee.get('name'),
                    'email': employee.get('email'),
                    'department': employee.get('department'),
                    'designation': employee.get('designation'),
                    'avatar': employee.get('avatar')
                })
                
                # Set manager reference in employee
                employee['manager_info'] = {
                    'ldap': manager.get('ldap'),
                    'name': manager.get('name'),
                    'email': manager.get('email'),
                    'department': manager.get('department'),
                    'designation': manager.get('designation'),
                    'avatar': manager.get('avatar')
                }
                
                logger.debug(f"{employee['name']} reports to {manager['name']}")
        
        # Count managers and reportees for logging
        managers_count = len([emp for emp in employees_data if 'reportees' in emp and emp['reportees']])
        total_reportees = sum(len(emp.get('reportees', [])) for emp in employees_data)
        
        logger.debug(f"Built hierarchy: {managers_count} managers with {total_reportees} total reportees")
        
        # Log some examples for debugging
        for emp in employees_data[:5]:
            if emp.get('reportees'):
                logger.debug(f"Manager: {emp['name']} has {len(emp['reportees'])} reportees")
        
    except Exception as e:
        logger.error(f"Error building organizational hierarchy: {e}")

def get_employee_hierarchy(employee_ldap):
    """Get the full hierarchy for an employee (manager chain and reportees) - CACHED"""
    global hierarchy_result_cache

    # Check cache first (memory cache)
    current_time = time.time()
    cache_key = employee_ldap.lower() if employee_ldap else ''
    if cache_key in hierarchy_result_cache:
        cached_data, cache_time = hierarchy_result_cache[cache_key]
        if current_time - cache_time < hierarchy_result_cache_ttl:
            return cached_data

    # Check disk cache if not in memory
    disk_cache_key = f'hierarchy_result_{cache_key}'
    disk_cached = load_from_disk_cache(disk_cache_key)
    if disk_cached:
        logger.debug(f"✓ Using disk cached hierarchy for {employee_ldap}")
        # Also populate memory cache for faster subsequent access
        hierarchy_result_cache[cache_key] = (disk_cached, current_time)
        return disk_cached

    # Check GCS cache if not in disk
    gcs_cached = load_from_gcs_cache(disk_cache_key)
    if gcs_cached:
        logger.debug(f"✓ Using GCS cached hierarchy for {employee_ldap}")
        # Populate both disk and memory cache for faster subsequent access
        save_to_disk_cache(disk_cache_key, gcs_cached)
        hierarchy_result_cache[cache_key] = (gcs_cached, current_time)
        return gcs_cached

    try:
        employee = get_employee_by_ldap(employee_ldap)
        if not employee:
            return None

        hierarchy = {
            'employee': employee,
            'manager_chain': [],
            'reportees': employee.get('reportees', []),
            'peer_count': 0
        }
        
        # Build manager chain (going up)
        current = employee
        visited = set()  # Prevent infinite loops
        while current and current.get('manager_info'):
            manager_ldap = current['manager_info']['ldap']
            if manager_ldap in visited:
                break
            visited.add(manager_ldap)

            manager = get_employee_by_ldap(manager_ldap)
            if manager:
                hierarchy['manager_chain'].append(manager)
                current = manager
            else:
                # Manager not found - add Sundar as fallback CEO
                sundar = get_employee_by_ldap('sundar')
                if sundar and 'sundar' not in visited:
                    hierarchy['manager_chain'].append(sundar)
                break

        # If employee has manager email but no manager_info, add Sundar as fallback
        if not current.get('manager_info') and current.get('manager') and current['ldap'] == employee['ldap']:
            sundar = get_employee_by_ldap('sundar')
            if sundar and 'sundar' not in visited:
                hierarchy['manager_chain'].append(sundar)
        
        # Count peers (people with same manager)
        if employee.get('manager_info'):
            manager = get_employee_by_ldap(employee['manager_info']['ldap'])
            if manager:
                hierarchy['peer_count'] = len(manager.get('reportees', [])) - 1  # Exclude self

        # Cache the result (memory + disk + GCS)
        hierarchy_result_cache[cache_key] = (hierarchy, current_time)

        # Save to disk cache for persistence across restarts
        disk_cache_key = f'hierarchy_result_{cache_key}'
        save_to_disk_cache(disk_cache_key, hierarchy)
        logger.debug(f"✓ Saved hierarchy to disk cache for {employee_ldap}")

        # Save to GCS cache for long-term persistence (1 week)
        save_to_gcs_cache(disk_cache_key, hierarchy)

        return hierarchy

    except Exception as e:
        logger.error(f"Error getting hierarchy for {employee_ldap}: {e}")
        return None

# Authentication Functions
def get_credentials_from_sheet():
    """Get credentials from Google Sheets 'Credentials' tab (or JSON)"""
    try:
        # Try loading from JSON first (hybrid approach for faster loading)
        json_credentials = load_credentials_from_json()
        if json_credentials:
            logger.info(f"🚀 Loaded {len(json_credentials)} credentials from JSON (FAST PATH)")
            return json_credentials

        # Fall back to Google Sheets if JSON not available
        logger.debug("Loading credentials from Google Sheets...")

        # Get credentials data from Google Sheets
        connector = OptimizedGoogleSheetsConnector(GOOGLE_SHEETS_CONFIG)

        if not connector.connect_to_spreadsheet():
            logger.error("Failed to connect to spreadsheet")
            return None

        # Get data from 'Credentials' worksheet
        raw_data = connector.get_sheet_data_optimized('Credentials')

        if raw_data is None:
            logger.error("No credentials data found in sheet")
            return None

        credentials_data = []

        # Handle both DataFrame and list formats
        if isinstance(raw_data, pd.DataFrame):
            # Convert DataFrame to list of dicts
            logger.debug(f"Processing DataFrame with {len(raw_data)} rows")
            for _, row in raw_data.iterrows():
                cred = {}
                for col in raw_data.columns:
                    # Normalize column names: lowercase and replace spaces with underscores
                    key = col.lower().replace(' ', '_')
                    cred[key] = str(row[col]).strip() if pd.notna(row[col]) else ''
                credentials_data.append(cred)
        elif isinstance(raw_data, list):
            # Handle list format (legacy)
            if len(raw_data) < 2:
                logger.error("Credentials sheet is empty or has no data rows")
                return None

            headers = raw_data[0]
            for row in raw_data[1:]:
                if len(row) > 0:
                    cred = {}
                    for i, header in enumerate(headers):
                        cred[header.lower().replace(' ', '_')] = row[i] if i < len(row) else ''
                    credentials_data.append(cred)
        else:
            logger.error(f"Unexpected data type from sheet: {type(raw_data)}")
            return None

        logger.info(f"Loaded {len(credentials_data)} credentials from Google Sheets")
        logger.debug(f"Sample credential keys: {list(credentials_data[0].keys()) if credentials_data else 'No data'}")
        return credentials_data

    except Exception as e:
        logger.error(f"Error loading credentials from Google Sheets: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def verify_user_credentials(username, password):
    """Verify user credentials against Google Sheets"""
    try:
        credentials_data = get_credentials_from_sheet()

        if not credentials_data:
            return None, "Unable to load credentials"

        # Find matching user
        for cred in credentials_data:
            if cred.get('username', '').strip() == username.strip():
                # Check if active
                status = cred.get('active_inactive', '').strip().lower()
                if status != 'active':
                    return None, "Account is inactive. Please contact administrator."

                # Check password
                if cred.get('password', '').strip() == password:
                    return {
                        'username': username,
                        'qt_employee_name': cred.get('qt_employee_name', ''),
                        'qt_employee_ldap': cred.get('qt_employee_ldap', '')
                    }, None
                else:
                    return None, "Invalid username or password"

        return None, "Invalid username or password"

    except Exception as e:
        logger.error(f"Error verifying credentials: {e}")
        return None, "Authentication error. Please try again."

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('smartstakeholder.login'))
        return f(*args, **kwargs)
    return decorated_function

# Optimized Flask Routes
@bp.route('/')
@login_required
def index():
    try:
        with open('templates/index.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return render_fallback_dashboard()

def render_fallback_dashboard():
    """Optimized fallback dashboard"""
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Qonnect - Optimized Google Sheets</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 40px; background: #f5f5f5; }}
            .container {{ background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); max-width: 1200px; margin: 0 auto; }}
            .status {{ padding: 15px; border-radius: 8px; margin: 10px 0; }}
            .success {{ background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }}
            .warning {{ background: #fff3cd; border: 1px solid #ffeaa7; color: #856404; }}
            .info {{ background: #e2f3ff; border: 1px solid #bee5eb; color: #0c5460; }}
            .button {{ background: #2a2559; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; margin: 8px 8px 0 0; font-weight: 500; }}
            .button:hover {{ background: #1a1a40; }}
            .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin: 24px 0; }}
            .stat {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; border: 1px solid #e9ecef; }}
            .stat h3 {{ margin: 0; color: #2a2559; font-size: 2em; }}
            .stat p {{ margin: 8px 0 0; color: #666; font-size: 0.9em; }}
            .performance {{ background: #e8f5e8; padding: 15px; border-radius: 8px; border: 1px solid #4CAF50; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 Qonnect - Optimized Google Sheets</h1>
            
            {'<div class="status success">' if len(employees_data) > 0 else '<div class="status warning">'}
                <strong>📊 Status:</strong> {'Loaded ' + f'{len(employees_data):,}' + ' employee profiles' if employees_data else 'No data loaded'}<br>
                <strong>⚡ Performance:</strong> Optimized batch processing, memory management<br>
                <strong>🔗 Source:</strong> <a href="{GOOGLE_SHEETS_CONFIG['spreadsheet_url']}" target="_blank">Google Sheets</a>
            </div>
            
            <div class="performance">
                <strong>🎯 Optimizations Applied:</strong><br>
                ✅ Batch processing for large datasets<br>
                ✅ Memory management and garbage collection<br>
                ✅ Cached employee lookups<br>
                ✅ Optimized API endpoints<br>
                ✅ Reduced logging overhead
            </div>
            
            <div class="stats">
                <div class="stat">
                    <h3>{len(employees_data):,}</h3>
                    <p>Total Employees</p>
                </div>
                <div class="stat">
                    <h3>{len(google_employees):,}</h3>
                    <p>Google Employees</p>
                </div>
                <div class="stat">
                    <h3>{len(core_team):,}</h3>
                    <p>Core Team</p>
                </div>
                <div class="stat">
                    <h3>{processing_stats.get('processing_time', 0):.1f}s</h3>
                    <p>Processing Time</p>
                </div>
            </div>
            
            <a href="/api/sync-google-sheets" class="button">🔄 Sync Data</a>
            <a href="/api/stats" class="button">📊 Statistics</a>
            <a href="/declare" class="button">🤝 Declare</a>
            <a href="/search" class="button">🔍 Search</a>
        </div>
    </body>
    </html>
    '''

# Authentication Routes
@bp.route('/login', methods=['GET'])
def login():
    """Login page"""
    # If already logged in, redirect to home
    if 'user' in session:
        return redirect(url_for('smartstakeholder.index'))

    try:
        with open('templates/login.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return '<h1>Login page not found</h1>'

@bp.route('/api/login', methods=['POST'])
def api_login():
    """API endpoint for login"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        remember_me = data.get('remember_me', False)

        # Capture request metadata for logging
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        user_agent = request.headers.get('User-Agent', 'Unknown')

        if not username or not password:
            logger.warning(f"❌ LOGIN FAILED - Missing credentials | IP: {ip_address}")
            return jsonify({
                'success': False,
                'message': 'Username and password are required'
            }), 400

        # Verify credentials
        user_data, error = verify_user_credentials(username, password)

        if error:
            logger.warning(f"❌ LOGIN FAILED - {error} | Username: {username} | IP: {ip_address} | User-Agent: {user_agent}")
            return jsonify({
                'success': False,
                'message': error
            }), 401

        if user_data:
            # Create session
            session['user'] = user_data

            # Set session as permanent (30 days) only if Remember Me is checked
            # If not checked, session expires when browser closes
            session.permanent = remember_me

            # Detailed login success logging
            logger.info(f"✅ LOGIN SUCCESS | Username: {username} | Name: {user_data.get('qt_employee_name', 'N/A')} | Remember Me: {remember_me} | IP: {ip_address} | User-Agent: {user_agent}")

            return jsonify({
                'success': True,
                'message': 'Login successful',
                'user': {
                    'username': user_data['username'],
                    'name': user_data['qt_employee_name']
                },
                'remember_me': remember_me
            })

        # Invalid credentials fallback
        logger.warning(f"❌ LOGIN FAILED - Invalid credentials | Username: {username} | IP: {ip_address} | User-Agent: {user_agent}")
        return jsonify({
            'success': False,
            'message': 'Invalid credentials'
        }), 401

    except Exception as e:
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        logger.error(f"❌ LOGIN ERROR - Exception: {e} | IP: {ip_address}")
        return jsonify({
            'success': False,
            'message': 'An error occurred during login'
        }), 500

@bp.route('/logout')
def logout():
    """Logout route"""
    # Capture user info before clearing session
    user_info = session.get('user', {})
    username = user_info.get('username', 'Unknown')
    name = user_info.get('qt_employee_name', 'N/A')
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)

    # Clear session
    session.pop('user', None)

    # Detailed logout logging
    logger.info(f"🚪 LOGOUT | Username: {username} | Name: {name} | IP: {ip_address}")

    return redirect(url_for('smartstakeholder.login'))

@bp.route('/declare')
@login_required
def declare():
    try:
        with open('templates/declare.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return '<h1>Declare page not found</h1><a href="/">Back to Home</a>'

@bp.route('/search')
@login_required
def search():
    try:
        with open('templates/search.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return '<h1>Search page not found</h1><a href="/">Back to Home</a>'

# FIXED API Endpoints

@bp.route('/api/sync-google-sheets', methods=['POST'])
def sync_google_sheets():
    """Optimized sync endpoint"""
    try:
        success = load_google_sheets_data_optimized()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Data synced successfully (optimized)',
                'stats': {
                    'total_employees': len(employees_data),
                    'google_employees': len(google_employees),
                    'core_team': len(core_team),
                    'processing_time': processing_stats.get('processing_time', 0),
                    'last_sync': last_sync_time.isoformat(),
                    'optimization': 'Batch processing enabled'
                }
            })
        else:
            return jsonify({'success': False, 'error': 'Optimized sync failed'}), 500
            
    except Exception as e:
        logger.error(f"Sync error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/sync-sharepoint', methods=['POST'])
def sync_sharepoint():
    """Legacy endpoint - redirects to optimized Google Sheets sync"""
    return sync_google_sheets()

@bp.route('/api/search-employees')
def search_employees():
    """OPTIMIZED: Employee search using search index for faster lookups"""
    # Auto-load data if not loaded yet
    if not employees_data:
        logger.debug("Data not loaded, loading now...")
        load_google_sheets_data_optimized()

    query = request.args.get('q', '').lower().strip()

    if len(query) < 2:
        return jsonify([])

    try:
        max_results = 25
        candidates = set()  # Use set to avoid duplicates

        # Use search index for faster lookups
        if employee_search_index['last_built']:
            # Try exact LDAP match first
            if query in employee_search_index['by_ldap']:
                candidates.update([emp['ldap'] for emp in employee_search_index['by_ldap'][query]])

            # Try email prefix match
            if query in employee_search_index['by_email']:
                candidates.update([emp['ldap'] for emp in employee_search_index['by_email'][query]])

            # Try name token matches
            for token in query.split():
                if len(token) >= 2:
                    # Partial match on token
                    for index_token, emps in employee_search_index['by_name'].items():
                        if token in index_token:
                            candidates.update([emp['ldap'] for emp in emps])
                            if len(candidates) >= max_results * 3:  # Get enough candidates
                                break

        # If index search didn't yield results, fall back to full scan
        if not candidates:
            for emp in employees_data[:500]:  # Limit fallback scan
                name = emp.get('name', '').lower()
                email = emp.get('email', '').lower()
                ldap = emp.get('ldap', '').lower()

                if (query in name or query in email or query in ldap or
                    query in emp.get('department', '').lower() or
                    query in emp.get('designation', '').lower()):
                    candidates.add(ldap)

        # Now score and filter the candidates
        filtered = []
        seen_employees = set()

        for ldap in candidates:
            emp = get_employee_by_ldap(ldap)
            if not emp or ldap in seen_employees:
                continue

            seen_employees.add(ldap)
            score = 0

            # Calculate relevance score
            name = emp.get('name', '').lower()
            email = emp.get('email', '').lower()
            emp_ldap = emp.get('ldap', '').lower()

            if query == emp_ldap:  # Exact LDAP match
                score += 20
            elif query in emp_ldap:
                score += 10

            if query in name:
                score += 10
                if name.startswith(query):
                    score += 5

            if query in email:
                score += 8

            if query in emp.get('department', '').lower():
                score += 4
            elif query in emp.get('designation', '').lower():
                score += 3

            if score > 0:
                emp_copy = {
                    'ldap': emp['ldap'],
                    'name': emp['name'],
                    'email': emp['email'],
                    'department': emp['department'],
                    'designation': emp['designation'],
                    'company': emp['company'],
                    'organisation': emp['organisation'],
                    'avatar': emp['avatar'],
                    'manager': emp.get('manager', ''),
                    'location': emp.get('location', ''),
                    '_search_score': score,
                    'declared_connections': []
                }
                filtered.append(emp_copy)

            if len(filtered) >= max_results:
                break

        # Sort by score first, then alphabetically by name
        filtered.sort(key=lambda x: (-x['_search_score'], x['name'].lower()))
        return jsonify(filtered[:max_results])

    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify([])

@bp.route('/api/debug-get-employee-by-ldap/<ldap_id>')
def debug_get_employee_by_ldap(ldap_id):
    """Debug endpoint to test get_employee_by_ldap function"""
    try:
        logger.debug(f"Debugging get_employee_by_ldap for LDAP: {ldap_id}")
        employee = get_employee_by_ldap(ldap_id)
        if employee:
            return jsonify(employee)
        else:
            return jsonify({'message': f'Employee with LDAP {ldap_id} not found.'}), 404
    except Exception as e:
        logger.error(f"Error in debug_get_employee_by_ldap: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/search-google-employees')
def search_google_employees():
    """FIXED: Google employee search - finds Google employees only"""
    query = request.args.get('q', '').lower().strip()
    
    if len(query) < 2:
        return jsonify([])
    
    try:
        filtered = []
        max_results = 25
        
        for emp in google_employees:  # Only search in Google employees
            if len(filtered) >= max_results:
                break
                
            score = 0
            
            # FIXED: Search the employee's own details, NOT manager relationships
            name = emp.get('name', '').lower()
            if query in name:
                score += 10
                if name.startswith(query):
                    score += 5
            
            email = emp.get('email', '').lower()
            if query in email:
                score += 8
                if email.startswith(query):
                    score += 3
            
            ldap = emp.get('ldap', '').lower()
            if query in ldap:
                score += 7
                if ldap.startswith(query):
                    score += 3
            
            if score == 0:
                # Check other fields only if no name/email/ldap match
                if query in emp.get('department', '').lower():
                    score += 4
                elif query in emp.get('designation', '').lower():
                    score += 3
            
            if score > 0:
                emp_copy = {
                    'ldap': emp['ldap'],
                    'name': emp['name'],
                    'email': emp['email'],
                    'department': emp['department'],
                    'designation': emp['designation'],
                    'company': emp['company'],
                    'organisation': emp['organisation'],
                    'avatar': emp['avatar'],
                    'manager': emp.get('manager', ''),
                    'location': emp.get('location', ''),
                    'connections': emp.get('connections', []),
                    '_search_score': score
                }
                
                # --- NEW: Add declared connections from Google Sheets ---
                declared_connections = get_connections_data(emp['ldap'])
                emp_copy['declared_connections'] = declared_connections

                filtered.append(emp_copy)
        
        # Sort by score
        filtered.sort(key=lambda x: x['_search_score'], reverse=True)
        return jsonify(filtered)
        
    except Exception as e:
        logger.error(f"Google employee search error: {e}")
        return jsonify([])

@bp.route('/api/google-employees')
def get_google_employees():
    """Get Google employees (optimized)"""
    # Auto-load data if not loaded yet
    if not employees_data:
        logger.debug("Data not loaded, loading now...")
        load_google_sheets_data_optimized()

    try:
        # Return minimal employee data without connections to reduce response size
        # Connections field can be 10-20MB, causing Cloud Run response size limit errors
        return jsonify([
            {
                'ldap': emp['ldap'],
                'name': emp['name'],
                'email': emp['email'],
                'department': emp['department'],
                'designation': emp['designation'],
                'company': emp['company'],
                'organisation': emp['organisation'],
                'avatar': emp['avatar'],
                'manager': emp.get('manager', ''),
                'location': emp.get('location', '')
                # connections field removed to keep response size under Cloud Run's 32MB limit
            }
            for emp in google_employees
        ])
        
    except Exception as e:
        logger.error(f"Error getting Google employees: {e}")
        return jsonify([])

@bp.route('/api/qt-team')
def get_qt_team():
    """Get QT team members (optimized)"""
    # Auto-load data if not loaded yet
    if not employees_data:
        logger.debug("Data not loaded, loading now...")
        load_google_sheets_data_optimized()

    try:
        return jsonify([
            {
                'ldap': emp['ldap'],
                'name': emp['name'],
                'email': emp['email'],
                'department': emp['department'],
                'designation': emp['designation'],
                'company': emp['company'],
                'organisation': emp['organisation'],
                'avatar': emp['avatar'],
                'manager': emp.get('manager', ''),
                'location': emp.get('location', ''),
                'connections': emp.get('connections', [])
            }
            for emp in core_team
        ])
        
    except Exception as e:
        logger.error(f"Error getting QT team: {e}")
        return jsonify([])

@bp.route('/api/hierarchy/<employee_ldap>')
def get_employee_hierarchy_api(employee_ldap):
    """Get organizational hierarchy for an employee (manager chain + reportees)"""
    try:
        hierarchy = get_employee_hierarchy(employee_ldap)

        if not hierarchy:
            return jsonify({'error': 'Employee not found'}), 404

        return jsonify({
            'employee': hierarchy['employee'],
            'manager_chain': hierarchy['manager_chain'],
            'reportees': hierarchy['reportees'],
            'peer_count': hierarchy['peer_count'],
            'total_reports': len(hierarchy['reportees']),
            'hierarchy_depth': len(hierarchy['manager_chain'])
        })

    except Exception as e:
        logger.error(f"Hierarchy API error for {employee_ldap}: {e}")
        return jsonify({'error': 'Failed to get hierarchy'}), 500

@bp.route('/api/organizational-path/<from_ldap>/<to_ldap>')
def get_organizational_path_api(from_ldap, to_ldap):
    """Get the actual organizational path between two employees"""
    try:
        from_emp = get_employee_by_ldap(from_ldap)
        to_emp = get_employee_by_ldap(to_ldap)

        if not from_emp or not to_emp:
            return jsonify({'error': 'Employee not found'}), 404

        # Build manager chains for both employees using manager_info
        from_chain = []
        to_chain = []

        # Build from_emp's manager chain
        current = from_emp
        visited = set()
        max_depth = 20  # Prevent infinite loops
        depth = 0
        while current and depth < max_depth:
            depth += 1
            manager = None
            manager_ldap = None

            # Only use manager_info to avoid including placeholder employees
            # that don't have validated organizational relationships
            if current.get('manager_info'):
                manager_ldap = current['manager_info']['ldap']
                if manager_ldap not in visited:
                    visited.add(manager_ldap)
                    manager = get_employee_by_ldap(manager_ldap)
                    if manager:
                        from_chain.append(manager)
                        current = manager
                    else:
                        # Manager not found - add Sundar as fallback CEO
                        sundar = get_employee_by_ldap('sundar')
                        if sundar and 'sundar' not in visited:
                            from_chain.append(sundar)
                        break
                else:
                    break
            else:
                # No manager_info - add Sundar as fallback CEO
                sundar = get_employee_by_ldap('sundar')
                if sundar and 'sundar' not in visited:
                    from_chain.append(sundar)
                break

        # Build to_emp's manager chain
        current = to_emp
        visited = set()
        depth = 0
        while current and depth < max_depth:
            depth += 1
            manager = None
            manager_ldap = None

            # Only use manager_info to avoid including placeholder employees
            # that don't have validated organizational relationships
            if current.get('manager_info'):
                manager_ldap = current['manager_info']['ldap']
                if manager_ldap not in visited:
                    visited.add(manager_ldap)
                    manager = get_employee_by_ldap(manager_ldap)
                    if manager:
                        to_chain.append(manager)
                        current = manager
                    else:
                        # Manager not found - add Sundar as fallback CEO
                        sundar = get_employee_by_ldap('sundar')
                        if sundar and 'sundar' not in visited:
                            to_chain.append(sundar)
                        break
                else:
                    break
            else:
                # No manager_info - add Sundar as fallback CEO
                sundar = get_employee_by_ldap('sundar')
                if sundar and 'sundar' not in visited:
                    to_chain.append(sundar)
                break

        # Now build the complete path
        path = []

        # Check if to_emp is in from_emp's manager chain
        for i, manager in enumerate(from_chain):
            if manager['ldap'].lower() == to_ldap.lower():
                # Path goes from from_emp up through managers to to_emp
                # Count excludes from_emp, so: i + 1 (managers including to_emp)
                path = [from_emp] + from_chain[:i+1]
                return jsonify({'path': path, 'intermediateCount': i + 1})

        # Check if from_emp is in to_emp's manager chain
        for i, manager in enumerate(to_chain):
            if manager['ldap'].lower() == from_ldap.lower():
                # Path goes from from_emp down to to_emp
                # Count excludes from_emp, so: i + 1 (managers down to to_emp)
                path = [from_emp] + list(reversed(to_chain[:i])) + [to_emp]
                return jsonify({'path': path, 'intermediateCount': i + 1})

        # Check if they share a common manager
        for i, from_manager in enumerate(from_chain):
            for j, to_manager in enumerate(to_chain):
                if from_manager['ldap'].lower() == to_manager['ldap'].lower():
                    # Found common manager - build path through them
                    # Path: from_emp -> i managers -> common_mgr -> j managers -> to_emp
                    # Count excludes from_emp, so: i + 1 (common) + j + 1 (to_emp) = i + j + 2
                    path_up = [from_emp] + from_chain[:i]
                    common_manager = from_manager
                    path_down = list(reversed(to_chain[:j])) + [to_emp]
                    path = path_up + [common_manager] + path_down
                    return jsonify({'path': path, 'intermediateCount': i + j + 2})

        # No relationship found - return estimate based on chain lengths
        # Path: from_emp -> all from_chain -> all to_chain -> to_emp
        # Count excludes from_emp, so: len(from_chain) + len(to_chain) + 1 (to_emp)
        estimate = len(from_chain) + len(to_chain) + 1
        path = [from_emp] + from_chain + list(reversed(to_chain)) + [to_emp]
        return jsonify({'path': path, 'intermediateCount': estimate})

    except Exception as e:
        logger.error(f"Organizational path API error for {from_ldap} -> {to_ldap}: {e}")
        return jsonify({'error': 'Failed to get organizational path'}), 500

@bp.route('/api/employees/<employee_id>')
def get_employee_details(employee_id):
    """Enhanced employee details with organizational hierarchy"""
    try:
        # Use cached lookup
        employee = get_employee_by_ldap(employee_id)
        
        if not employee:
            return jsonify({'error': 'Employee not found'}), 404
        
        # Get organizational hierarchy
        hierarchy = get_employee_hierarchy(employee_id)
        
        # Build details efficiently
        employee_details = employee.copy()
        
        # Add hierarchy information
        if hierarchy:
            employee_details.update({
                'manager_chain': hierarchy['manager_chain'],
                'reportees': hierarchy['reportees'],
                'peer_count': hierarchy['peer_count'],
                'total_reports': len(hierarchy['reportees']),
                'hierarchy_depth': len(hierarchy['manager_chain'])
            })
        
        # Find related employees efficiently
        same_dept = [emp for emp in employees_data 
                    if emp.get('department') == employee.get('department') 
                    and emp.get('ldap') != employee_id][:5]
        
        same_location = [emp for emp in employees_data 
                        if emp.get('location') == employee.get('location') 
                        and emp.get('ldap') != employee_id][:5]
        
        employee_details.update({
            'colleagues': same_dept,
            'location_peers': same_location,
            'total_colleagues': len([emp for emp in employees_data 
                                   if emp.get('department') == employee.get('department')]),
            'total_location_peers': len([emp for emp in employees_data 
                                       if emp.get('location') == employee.get('location')])
        })
        
        return jsonify(employee_details)

    except Exception as e:
        logger.error(f"Error getting employee details: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/api/employee/<employee_ldap>/connections')
def get_employee_connections_optimized(employee_ldap):
    """OPTIMIZED: Get all connections (direct + transitive) for an employee in one call"""
    try:
        employee = get_employee_by_ldap(employee_ldap)
        if not employee:
            return jsonify({'error': 'Employee not found'}), 404

        # Initialize result structure
        result = {
            'ldap': employee_ldap,
            'name': employee.get('name', ''),
            'organisation': employee.get('organisation', ''),
            'direct_connections': [],
            'transitive_connections': [],
            'manager_chain': [],
            'total_connections': 0
        }

        # Get connections data
        connections_data = get_cached_connections_data()

        # Build lookup maps for faster access
        connections_by_google = {}
        connections_by_qt = {}

        for conn in connections_data:
            google_ldap = conn.get('Google Employee', '').strip().lower()
            qt_ldap = conn.get('QT Employee', '').strip().lower()

            if google_ldap:
                if google_ldap not in connections_by_google:
                    connections_by_google[google_ldap] = []
                if qt_ldap:
                    connections_by_google[google_ldap].append(qt_ldap)

            if qt_ldap:
                if qt_ldap not in connections_by_qt:
                    connections_by_qt[qt_ldap] = []
                if google_ldap:
                    connections_by_qt[qt_ldap].append(google_ldap)

        # Get manager chain
        hierarchy = get_employee_hierarchy(employee_ldap)
        if hierarchy and hierarchy.get('manager_chain'):
            result['manager_chain'] = [
                {
                    'ldap': mgr.get('ldap'),
                    'name': mgr.get('name'),
                    'designation': mgr.get('designation'),
                    'avatar': mgr.get('avatar')
                }
                for mgr in hierarchy['manager_chain']
            ]

        # Determine if this is Google or QT employee
        is_google = employee.get('organisation', '').lower() == 'google'
        is_qt = employee.get('organisation', '').lower() == 'qualitest'

        # Find direct connections
        if is_google:
            # Google employee - find QT employees connected to them
            qt_ldaps = connections_by_google.get(employee_ldap.lower(), [])
            for qt_ldap in qt_ldaps:
                qt_emp = get_employee_by_ldap(qt_ldap)
                if qt_emp:
                    result['direct_connections'].append({
                        'ldap': qt_emp.get('ldap'),
                        'name': qt_emp.get('name'),
                        'designation': qt_emp.get('designation'),
                        'organisation': qt_emp.get('organisation'),
                        'avatar': qt_emp.get('avatar'),
                        'connection_type': 'direct'
                    })

        elif is_qt:
            # QT employee - find Google employees connected to them
            google_ldaps = connections_by_qt.get(employee_ldap.lower(), [])
            for google_ldap in google_ldaps:
                google_emp = get_employee_by_ldap(google_ldap)
                if google_emp:
                    result['direct_connections'].append({
                        'ldap': google_emp.get('ldap'),
                        'name': google_emp.get('name'),
                        'designation': google_emp.get('designation'),
                        'organisation': google_emp.get('organisation'),
                        'avatar': google_emp.get('avatar'),
                        'connection_type': 'direct'
                    })

        # Find transitive connections (through manager chain)
        transitive_qt_employees = set()

        if is_google:
            # For Google employees: check if any manager has QT connections
            for manager in hierarchy.get('manager_chain', [])[:5]:  # Limit to 5 levels
                mgr_ldap = manager.get('ldap', '').lower()
                qt_ldaps = connections_by_google.get(mgr_ldap, [])

                for qt_ldap in qt_ldaps:
                    # Skip if already in direct connections
                    if qt_ldap not in [dc['ldap'].lower() for dc in result['direct_connections']]:
                        if qt_ldap not in transitive_qt_employees:
                            transitive_qt_employees.add(qt_ldap)
                            qt_emp = get_employee_by_ldap(qt_ldap)
                            if qt_emp:
                                result['transitive_connections'].append({
                                    'ldap': qt_emp.get('ldap'),
                                    'name': qt_emp.get('name'),
                                    'designation': qt_emp.get('designation'),
                                    'organisation': qt_emp.get('organisation'),
                                    'avatar': qt_emp.get('avatar'),
                                    'connection_type': 'transitive',
                                    'via_manager': manager.get('name'),
                                    'via_manager_ldap': mgr_ldap
                                })

        result['total_connections'] = len(result['direct_connections']) + len(result['transitive_connections'])

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting connections for {employee_ldap}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/api/departments')
def get_departments():
    """Optimized departments endpoint"""
    try:
        dept_counts = {}
        
        # Single pass through employees
        for emp in employees_data:
            dept = emp.get('department', 'Unknown')
            if dept not in dept_counts:
                dept_counts[dept] = {'count': 0, 'google': 0, 'qualitest': 0, 'other': 0}
            
            dept_counts[dept]['count'] += 1
            org = emp.get('organisation', 'Other')
            if org == 'Google':
                dept_counts[dept]['google'] += 1
            elif org == 'Qualitest':
                dept_counts[dept]['qualitest'] += 1
            else:
                dept_counts[dept]['other'] += 1
        
        departments = [
            {
                'name': dept,
                'count': counts['count'],
                'google_count': counts['google'],
                'qualitest_count': counts['qualitest'],
                'other_count': counts['other']
            }
            for dept, counts in dept_counts.items()
        ]
        
        departments.sort(key=lambda x: x['count'], reverse=True)
        return jsonify(departments[:50])  # Limit results
        
    except Exception as e:
        logger.error(f"Error getting departments: {e}")
        return jsonify([])

@bp.route('/api/locations')
def get_locations():
    """Optimized locations endpoint"""
    try:
        location_counts = {}
        
        # Single pass through employees
        for emp in employees_data:
            location = emp.get('location', 'Unknown')
            if location not in location_counts:
                location_counts[location] = {'count': 0, 'google': 0, 'qualitest': 0, 'other': 0}
            
            location_counts[location]['count'] += 1
            org = emp.get('organisation', 'Other')
            if org == 'Google':
                location_counts[location]['google'] += 1
            elif org == 'Qualitest':
                location_counts[location]['qualitest'] += 1
            else:
                location_counts[location]['other'] += 1
        
        locations = [
            {
                'name': location,
                'count': counts['count'],
                'google_count': counts['google'],
                'qualitest_count': counts['qualitest'],
                'other_count': counts['other']
            }
            for location, counts in location_counts.items()
        ]
        
        locations.sort(key=lambda x: x['count'], reverse=True)
        return jsonify(locations[:50])  # Limit results
        
    except Exception as e:
        logger.error(f"Error getting locations: {e}")
        return jsonify([])

@bp.route('/api/stats')
def get_stats():
    """Optimized stats endpoint"""
    try:
        # Calculate stats efficiently
        total_employees = len(employees_data)
        google_count = len(google_employees)
        qualitest_count = len([e for e in employees_data if e.get('organisation') == 'Qualitest'])
        other_count = total_employees - google_count - qualitest_count
        
        # Get top items efficiently
        dept_counts = {}
        location_counts = {}
        
        for emp in employees_data:
            dept = emp.get('department', 'Unknown')
            location = emp.get('location', 'Unknown')
            
            dept_counts[dept] = dept_counts.get(dept, 0) + 1
            location_counts[location] = location_counts.get(location, 0) + 1
        
        return jsonify({
            'total_employees': total_employees,
            'google_employees': google_count,
            'qualitest_employees': qualitest_count,
            'other_employees': other_count,
            'qt_team_members': len(core_team),
            'total_connections': 0,
            'total_departments': len(dept_counts),
            'total_locations': len(location_counts),
            'top_departments': sorted(dept_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            'top_locations': sorted(location_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            'data_source': 'Google Sheets (Optimized)',
            'last_sync': last_sync_time.isoformat() if last_sync_time else None,
            'processing_stats': {
                k: v for k, v in processing_stats.items() 
                if k not in ['columns_found', 'column_mapping']  # Reduce payload
            } if processing_stats else {},
            'performance': {
                'optimization_level': 'High',
                'batch_processing': True,
                'memory_management': True,
                'caching_enabled': True
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': 'Stats unavailable'}), 500

# Connection management (optimized)
@bp.route('/api/batch-update-connections', methods=['POST'])
def batch_update_connections_fixed():
    """FIXED: Enhanced connection updates that actually write to Google Sheets"""
    try:
        data = request.get_json()
        google_ldap = data.get('googleLdap')
        connections = data.get('connections', {})
        declared_by = data.get('declaredBy', 'Qonnect User')
        
        logger.debug(f"🎯 Connection update request:")
        logger.debug(f"  Google LDAP: {google_ldap}")
        logger.debug(f"  Connections: {len(connections)} items")
        logger.debug(f"  Data: {connections}")
        
        if not google_ldap or not connections:
            logger.error("❌ Missing required data")
            return jsonify({
                'success': False, 
                'error': 'Missing required data (googleLdap or connections)'
            }), 400
        
        # Update in-memory data (existing functionality)
        logger.debug("💾 Updating in-memory data...")
        google_employee = get_employee_by_ldap(google_ldap)
        if google_employee:
            if 'connections' not in google_employee:
                google_employee['connections'] = []
            
            for qt_ldap, strength in connections.items():
                existing_conn = next((conn for conn in google_employee['connections'] 
                                    if conn.get('ldap') == qt_ldap), None)
                
                if existing_conn:
                    existing_conn['connectionStrength'] = strength
                    logger.debug(f"  ✏️ Updated: {qt_ldap} -> {strength}")
                else:
                    qt_employee = next((emp for emp in core_team if emp.get('ldap') == qt_ldap), None)
                    if qt_employee:
                        google_employee['connections'].append({
                            'ldap': qt_ldap,
                            'name': qt_employee.get('name'),
                            'connectionStrength': strength
                        })
                        logger.debug(f"  ➕ Added: {qt_ldap} -> {strength}")
        
        logger.debug("✅ In-memory data updated")

        # Write to Google Sheets
        logger.debug("📝 Writing directly to Google Sheets...")
        try:
            # Prepare data
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            connections_to_add = []
            successful_connections = []

            # Get Google employee details with fallback
            if not google_employee:
                google_employee = {
                    'ldap': google_ldap,
                    'name': google_ldap.replace('.', ' ').title(),
                    'email': f"{google_ldap}@google.com",
                    'department': 'Unknown'
                }

            for qt_ldap, strength in connections.items():
                # Find QT employee with fallback
                qt_emp = next((emp for emp in core_team if emp.get('ldap') == qt_ldap), None)
                if not qt_emp:
                    qt_emp = {
                        'ldap': qt_ldap,
                        'name': qt_ldap.replace('.', ' ').title(),
                        'email': f"{qt_ldap}@qualitestgroup.com",
                        'department': 'QT Team'
                    }

                connection_data = {
                    'timestamp': timestamp,
                    'google_employee_ldap': google_employee.get('ldap', ''),
                    'google_employee_name': google_employee.get('name', ''),
                    'google_employee_email': google_employee.get('email', ''),
                    'google_employee_department': google_employee.get('department', ''),
                    'qt_employee_ldap': qt_emp.get('ldap', ''),
                    'qt_employee_name': qt_emp.get('name', ''),
                    'qt_employee_email': qt_emp.get('email', ''),
                    'qt_employee_department': qt_emp.get('department', ''),
                    'connection_strength': strength.title(),
                    'declared_by': declared_by,
                    'notes': f"Connection declared via Qonnect app"
                }

                connections_to_add.append(connection_data)
                successful_connections.append(f"{qt_emp.get('name')} ({strength})")
                logger.debug(f"  📝 Prepared connection for {qt_emp.get('name')}")

            # Write to Google Sheets using the writer
            if connections_to_add:
                writer = OptimizedGoogleSheetsWriter(GOOGLE_SHEETS_CONFIG)
                success_message = writer.write_batch_connections_to_sheet(google_ldap, connections, declared_by)

                if success_message:
                    logger.debug(f"🎉 Successfully wrote {len(connections)} connections to Google Sheets!")

                    # Invalidate all caches to ensure fresh data on next search
                    invalidate_connections_cache()
                    logger.debug(f"🔄 Cache invalidated - search will show fresh data")

                    return jsonify({
                        'success': True,
                        'updated_count': len(connections),
                        'message': f"Successfully saved {len(connections)} connections to Google Sheets: {', '.join(successful_connections)}",
                        'google_employee': google_ldap,
                        'written_to_sheets': True,
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Failed to write to Google Sheets'
                    }), 500
            else:
                return jsonify({
                    'success': False,
                    'error': 'No valid connections to save'
                }), 400

        except Exception as sheets_error:
            logger.error(f"❌ Google Sheets write error: {sheets_error}")
            logger.error(f"Error type: {type(sheets_error).__name__}")
            logger.error(f"Error details: {str(sheets_error)}")

            # Return error
            return jsonify({
                'success': False,
                'error': f'Failed to save connections: {str(sheets_error)}',
                'google_employee': google_ldap,
                'written_to_sheets': False,
                'timestamp': datetime.now().isoformat(),
                'debug': {
                    'error_type': type(sheets_error).__name__,
                    'has_credentials': os.path.exists(GOOGLE_SHEETS_CONFIG['service_account_file'])
                }
            }), 500
        
    except Exception as e:
        logger.error(f"❌ API endpoint error: {e}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@bp.route('/api/test-sheet-write', methods=['POST'])
def test_sheet_write():
    """Test endpoint to verify Google Sheets writing works"""
    try:
        from datetime import datetime

        logger.debug("🧪 Testing direct Google Sheets write...")

        # Write test data to Google Sheets
        writer = OptimizedGoogleSheetsWriter(GOOGLE_SHEETS_CONFIG)
        test_connections = {
            'lihi.segev': 'strong'
        }

        success = writer.write_batch_connections_to_sheet('ashwink', test_connections, 'API Test')

        if success:
            return jsonify({
                'success': True,
                'message': 'Test write to Google Sheets successful!'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to write to Google Sheets'
            }), 500

    except Exception as e:
        logger.error(f"Test write failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def get_connections_data(employee_ldap):
    """Get actual organizational connections and hierarchy for an employee, including those from Google Sheets - INTERNAL VERSION"""
    global connections_result_cache

    # Check cache first (memory cache)
    current_time = time.time()
    cache_key = employee_ldap
    if cache_key in connections_result_cache:
        cached_data, cache_time = connections_result_cache[cache_key]
        if current_time - cache_time < connections_result_cache_ttl:
            logger.debug(f"✓ Using memory cached connections for {employee_ldap}")
            return cached_data

    # Check disk cache if not in memory
    disk_cache_key = f'connections_result_{employee_ldap}'
    disk_cached = load_from_disk_cache(disk_cache_key)
    if disk_cached:
        logger.debug(f"✓ Using disk cached connections for {employee_ldap}")
        # Also populate memory cache for faster subsequent access
        connections_result_cache[cache_key] = (disk_cached, current_time)
        return disk_cached

    # Check GCS cache if not in disk
    gcs_cached = load_from_gcs_cache(disk_cache_key)
    if gcs_cached:
        logger.debug(f"✓ Using GCS cached connections for {employee_ldap}")
        # Populate both disk and memory cache for faster subsequent access
        save_to_disk_cache(disk_cache_key, gcs_cached)
        connections_result_cache[cache_key] = (gcs_cached, current_time)
        return gcs_cached

    try:
        # Get hierarchy information
        hierarchy = get_employee_hierarchy(employee_ldap)

        if not hierarchy:
            logger.warning(f"No hierarchy found for {employee_ldap}")
            # Even if no hierarchy, we might still have declared connections
            employee_info = get_employee_by_ldap(employee_ldap)
            if not employee_info:
                return []
            hierarchy = {'employee': employee_info, 'manager_chain': [], 'reportees': []}

        # Initialize connections list
        connections = []

        # --- 1. Add connections from Google Sheets 'Connections' tab (cached) ---
        logger.debug(f"Reading declared connections for {employee_ldap} from cached data...")
        try:
            # Use cached connections data to avoid quota issues
            records = get_cached_connections_data()
            declared_connections = []
            for rec in records:
                if rec.get('Google Employee LDAP', '').lower() == employee_ldap.lower():
                    qt_ldap = rec.get('QT Employee LDAP')

                    # Calculate pathLength for this connection based on strength
                    connection_strength = rec.get('Connection Strength', '').lower()
                    path_length = calculate_path_length_to_qt_employee(employee_ldap, qt_ldap, hierarchy, connection_strength)

                    declared_connections.append({
                        'qtLdap': qt_ldap,
                        'qtName': rec.get('QT Employee Name'),
                        'qtEmail': rec.get('QT Employee Email'),
                        'connectionStrength': rec.get('Connection Strength', '').lower(),
                        'declaredBy': rec.get('Declared By'),
                        'timestamp': rec.get('Timestamp'),
                        'notes': rec.get('Notes'),
                        'source': 'Google Sheets',
                        'pathLength': path_length  # Add calculated path length
                    })
            logger.debug(f"✅ Found {len(declared_connections)} declared connections for {employee_ldap} from cache.")
            connections.extend(declared_connections)
        except Exception as e:
            logger.warning(f"⚠️ Could not load declared connections from cache: {e}")

        # --- 2. Add TRANSITIVE connections through other Google employees ---
        # If the employee has no direct connections, check if they can reach other Google employees who DO have connections
        if len(connections) == 0:
            logger.info(f"🔍 No direct connections found for {employee_ldap}, searching for transitive connections...")

            # Debug: Log employee info
            if hierarchy:
                emp_info = hierarchy.get('employee', {})
                logger.info(f"   Employee: {emp_info.get('name')} ({emp_info.get('email')})")
                logger.info(f"   Manager: {emp_info.get('manager')}")
                logger.info(f"   Department: {emp_info.get('department')}")
                logger.info(f"   Organisation: {emp_info.get('organisation')}")
                if emp_info.get('manager_info'):
                    logger.info(f"   Manager Info: {emp_info['manager_info'].get('name')} ({emp_info['manager_info'].get('email')})")
                logger.info(f"   Manager chain length: {len(hierarchy.get('manager_chain', []))}")

            try:
                # Get ALL connections from spreadsheet
                all_records = get_cached_connections_data()

                # Get unique Google employees who have QT connections (bridge employees)
                bridge_employees = {}
                for rec in all_records:
                    bridge_ldap = rec.get('Google Employee LDAP', '').lower()
                    if bridge_ldap and bridge_ldap != employee_ldap.lower():
                        if bridge_ldap not in bridge_employees:
                            bridge_employees[bridge_ldap] = []
                        bridge_employees[bridge_ldap].append({
                            'qtLdap': rec.get('QT Employee LDAP'),
                            'qtName': rec.get('QT Employee Name'),
                            'qtEmail': rec.get('QT Employee Email'),
                            'connectionStrength': rec.get('Connection Strength', '').lower(),
                            'declaredBy': rec.get('Declared By'),
                            'timestamp': rec.get('Timestamp'),
                            'notes': rec.get('Notes')
                        })

                logger.info(f"   Found {len(bridge_employees)} Google employees with QT connections to check")
                logger.info(f"   Bridge employees: {list(bridge_employees.keys())[:10]}")  # Log first 10

                # Check if current employee can reach any of these bridge employees
                # Build employee's manager chain for comparison (both emails and names)
                employee_manager_chain_emails = []
                employee_manager_chain_names = []
                if hierarchy and hierarchy.get('manager_chain'):
                    employee_manager_chain_emails = [mgr.get('email', '').lower() for mgr in hierarchy['manager_chain'] if mgr.get('email')]
                    employee_manager_chain_names = [mgr.get('name', '').lower() for mgr in hierarchy['manager_chain'] if mgr.get('name')]

                employee_email = hierarchy['employee'].get('email', '').lower() if hierarchy else ''
                employee_name = hierarchy['employee'].get('name', '').lower() if hierarchy else ''
                employee_department = hierarchy['employee'].get('department', '').lower() if hierarchy else ''
                employee_organisation = hierarchy['employee'].get('organisation', '').lower() if hierarchy else ''

                # Check each bridge employee
                transitive_found = 0
                for bridge_ldap, qt_connections in list(bridge_employees.items())[:100]:  # Increased from 50 to 100
                    try:
                        # Get bridge employee's info
                        bridge_emp = get_employee_by_ldap(bridge_ldap)
                        if not bridge_emp:
                            continue

                        bridge_email = bridge_emp.get('email', '').lower()
                        bridge_name = bridge_emp.get('name', '').lower()
                        bridge_manager = bridge_emp.get('manager', '').lower() if bridge_emp.get('manager') else ''
                        bridge_department = bridge_emp.get('department', '').lower() if bridge_emp.get('department') else ''
                        bridge_organisation = bridge_emp.get('organisation', '').lower() if bridge_emp.get('organisation') else ''

                        # Check if reachable through organizational hierarchy
                        is_reachable = False
                        intermediate_person = None
                        connection_method = None

                        # Get employee's manager (could be email or name)
                        employee_manager = hierarchy['employee'].get('manager', '').lower() if hierarchy else ''

                        # Check 1: Same manager by email (siblings)
                        if employee_manager and bridge_manager and employee_manager == bridge_manager:
                            is_reachable = True
                            intermediate_person = employee_manager
                            connection_method = "same_manager"
                            logger.debug(f"  ✓ {bridge_ldap} is a sibling (same manager: {employee_manager})")

                        # Check 2: Same manager by name lookup (siblings)
                        elif not is_reachable and employee_manager and bridge_manager:
                            # Try to match managers by looking up their names
                            emp_mgr_data = get_employee_by_ldap(employee_manager.split('@')[0]) if '@' in employee_manager else None
                            bridge_mgr_data = get_employee_by_ldap(bridge_manager.split('@')[0]) if '@' in bridge_manager else None

                            if emp_mgr_data and bridge_mgr_data:
                                emp_mgr_name = emp_mgr_data.get('name', '').lower()
                                bridge_mgr_name = bridge_mgr_data.get('name', '').lower()
                                if emp_mgr_name and bridge_mgr_name and emp_mgr_name == bridge_mgr_name:
                                    is_reachable = True
                                    intermediate_person = emp_mgr_name
                                    connection_method = "same_manager_name"
                                    logger.debug(f"  ✓ {bridge_ldap} is a sibling (same manager by name: {emp_mgr_name})")

                        # Check 3: Bridge employee is in the employee's manager chain (direct upline)
                        if not is_reachable and bridge_email and bridge_email in employee_manager_chain_emails:
                            is_reachable = True
                            intermediate_person = bridge_email
                            connection_method = "in_manager_chain"
                            logger.debug(f"  ✓ {bridge_ldap} is in manager chain")

                        # Check 4: Bridge employee name is in the employee's manager chain names
                        if not is_reachable and bridge_name and bridge_name in employee_manager_chain_names:
                            is_reachable = True
                            intermediate_person = bridge_name
                            connection_method = "in_manager_chain_name"
                            logger.debug(f"  ✓ {bridge_ldap} ({bridge_name}) is in manager chain by name")

                        # Check 5: Employee is the bridge's manager (direct report)
                        if not is_reachable and employee_email and bridge_manager and employee_email == bridge_manager:
                            is_reachable = True
                            intermediate_person = employee_email
                            connection_method = "direct_report"
                            logger.debug(f"  ✓ {bridge_ldap} is a direct report")

                        # Check 6: Employee name matches bridge's manager (direct report by name)
                        if not is_reachable and employee_name and bridge_manager:
                            bridge_mgr_data = get_employee_by_ldap(bridge_manager.split('@')[0]) if '@' in bridge_manager else None
                            if bridge_mgr_data:
                                bridge_mgr_name = bridge_mgr_data.get('name', '').lower()
                                if bridge_mgr_name and employee_name == bridge_mgr_name:
                                    is_reachable = True
                                    intermediate_person = employee_name
                                    connection_method = "direct_report_name"
                                    logger.debug(f"  ✓ {bridge_ldap} is a direct report (by name match)")

                        # Check 7: Shared manager in chain by email (cousins in org chart)
                        if not is_reachable and bridge_manager and bridge_manager in employee_manager_chain_emails:
                            is_reachable = True
                            intermediate_person = bridge_manager
                            connection_method = "shared_manager"
                            logger.debug(f"  ✓ {bridge_ldap} shares manager {bridge_manager}")

                        # Check 8: Shared manager in chain by name (cousins in org chart)
                        bridge_mgr_name_for_calc = None  # Store for later calculation
                        if not is_reachable and bridge_manager:
                            bridge_mgr_data = get_employee_by_ldap(bridge_manager.split('@')[0]) if '@' in bridge_manager else None
                            if bridge_mgr_data:
                                bridge_mgr_name = bridge_mgr_data.get('name', '').lower()
                                if bridge_mgr_name and bridge_mgr_name in employee_manager_chain_names:
                                    is_reachable = True
                                    intermediate_person = bridge_mgr_name
                                    connection_method = "shared_manager_name"
                                    bridge_mgr_name_for_calc = bridge_mgr_name  # Store for calculation
                                    logger.debug(f"  ✓ {bridge_ldap} shares manager by name: {bridge_mgr_name}")

                        # Check 9: Same department (colleagues)
                        if not is_reachable and employee_department and bridge_department and employee_department == bridge_department:
                            is_reachable = True
                            intermediate_person = employee_department
                            connection_method = "same_department"
                            logger.debug(f"  ✓ {bridge_ldap} in same department: {employee_department}")

                        # Check 10: Same organisation (colleagues)
                        if not is_reachable and employee_organisation and bridge_organisation and employee_organisation == bridge_organisation:
                            is_reachable = True
                            intermediate_person = employee_organisation
                            connection_method = "same_organisation"
                            logger.debug(f"  ✓ {bridge_ldap} in same organisation: {employee_organisation}")

                        # If reachable, add all their QT connections as transitive connections
                        if is_reachable:
                            # Calculate ACTUAL number of intermediate employees using proper org chart traversal
                            intermediate_count = calculate_actual_organizational_path(employee_ldap, bridge_ldap)

                            logger.debug(f"    → ACTUAL intermediate count for {bridge_emp.get('name')}: {intermediate_count} (method: {connection_method})")

                            for qt_conn in qt_connections:
                                connection_strength = qt_conn.get('connectionStrength', 'weak')

                                connections.append({
                                    'qtLdap': qt_conn['qtLdap'],
                                    'qtName': qt_conn.get('qtName'),
                                    'qtEmail': qt_conn.get('qtEmail'),
                                    'connectionStrength': connection_strength,
                                    'intermediatePerson': bridge_emp.get('name'),  # Bridge person's name
                                    'intermediateLdap': bridge_ldap,
                                    'source': 'Transitive',
                                    'pathLength': intermediate_count,  # Number of intermediate employees
                                    'declaredBy': qt_conn.get('declaredBy'),
                                    'notes': f"Via {bridge_emp.get('name', bridge_ldap)}"
                                })
                                transitive_found += 1
                    except Exception as e:
                        logger.warning(f"Error checking bridge employee {bridge_ldap}: {e}")
                        continue

                if transitive_found > 0:
                    logger.info(f"✅ Found {transitive_found} transitive connections for {employee_ldap}")
                else:
                    logger.info(f"⚠️  No transitive connections found for {employee_ldap}")
                    logger.info(f"   Checked {len(list(bridge_employees.items())[:100])} bridge employees")
                    logger.info(f"   Employee manager chain emails: {employee_manager_chain_emails[:3]}")
                    logger.info(f"   Employee manager chain names: {employee_manager_chain_names[:3]}")

            except Exception as e:
                logger.error(f"⚠️ Could not search for transitive connections: {e}", exc_info=True)

        # --- 3. Add connections to QT team members (Qualitest employees) through manager chain (existing logic) ---
        # This part can be kept if you want to infer connections based on hierarchy *in addition* to declared ones
        # Ensure no duplicates if a connection is both declared and inferred
        existing_qt_ldaps = {conn['qtLdap'] for conn in connections}

        # Limit core_team iteration for performance - only check first 20 members
        for qt_emp in core_team[:20]:  # Limited to 20 for performance
            qt_ldap = qt_emp.get('ldap')
            if qt_ldap == employee_ldap or qt_ldap in existing_qt_ldaps:
                continue # Skip self and already declared connections

            path = [qt_ldap]
            strength = 'weak' # Default to weak, then strengthen

            # Check for direct reporting relationship (manager chain)
            manager_ldaps = [mgr.get('ldap') for mgr in hierarchy['manager_chain']]
            if qt_ldap in manager_ldaps:
                path.append(employee_ldap)
                strength = 'strong'
            elif hierarchy['employee'].get('department') == qt_emp.get('department'):
                # Same department connection
                path.append(employee_ldap)
                strength = 'medium'
            else:
                # Indirect connection through a common manager (if any)
                if hierarchy['manager_chain']:
                    path.append(hierarchy['manager_chain'][0].get('ldap'))
                path.append(employee_ldap)
                strength = 'weak'

            connections.append({
                'qtLdap': qt_ldap,
                'connectionStrength': strength,
                'path': path,
                'source': 'Inferred'
            })

        # --- 3. Add TRANSITIVE connections through direct reports ---
        # DISABLED FOR PERFORMANCE: This was causing recursive lookups that slowed down the app significantly
        # If you need this feature, enable it only for specific users/cases
        # declared_connections_count = len([c for c in connections if c.get('source') == 'Google Sheets'])
        # if declared_connections_count == 0 and hierarchy and hierarchy['reportees']:
        #     # Transitive connection logic disabled for performance

        # --- 4. CROSS-ORGANIZATIONAL NETWORK EXPANSION ---
        # DISABLED FOR PERFORMANCE: This was searching through 1000+ employees per connection causing severe slowness
        # If you need this feature, implement it as an opt-in async operation
        # existing_qt_connections = [conn for conn in connections if conn.get('source') == 'Google Sheets']

        if False:  # Disabled - network expansion
            logger.debug(f"Found {len(existing_qt_connections)} QT connections to Google - exploring network expansion opportunities")
            network_expansion_connections = []

            # For each QT connection to a Google employee, explore their network
            for qt_conn in existing_qt_connections[:2]:  # Limit to 2 connections to avoid performance issues
                connected_googler_name = qt_conn.get('qtLdap', '')

                # Find this person in our Google employees data
                connected_googler = None
                for emp in employees_data[:1000]:  # Search first 1000 for performance
                    if (emp.get('name', '').lower() == connected_googler_name.lower() or
                        emp.get('ldap', '') == connected_googler_name or
                        connected_googler_name.lower() in emp.get('name', '').lower()):
                        connected_googler = emp
                        break

                if not connected_googler:
                    continue

                # Get their hierarchy to explore their network
                googler_hierarchy = get_employee_hierarchy(connected_googler['ldap'])
                if not googler_hierarchy:
                    continue

                # Explore network expansion through their colleagues and connections
                potential_contacts = []

                # Add their manager (senior person they can introduce you to)
                if googler_hierarchy.get('manager_chain'):
                    potential_contacts.extend(googler_hierarchy['manager_chain'][:2])

                # Add their direct reportees (people they manage)
                if googler_hierarchy.get('reportees'):
                    potential_contacts.extend(googler_hierarchy['reportees'][:3])

                # Create network expansion connections
                for contact in potential_contacts:
                    if contact.get('ldap') == employee_ldap:  # Skip self
                        continue

                    relationship = "manager" if contact in googler_hierarchy.get('manager_chain', []) else "reportee"

                    network_expansion_connections.append({
                        'qtLdap': contact.get('ldap'),
                        'connectionStrength': 'network_expansion',
                        'declaredBy': 'Network Analysis',
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'notes': f"Network expansion: {connected_googler.get('name')} can introduce you to their {relationship} {contact.get('name')}",
                        'source': 'Network_Expansion',
                        'expansion_path': {
                            'connector': connected_googler.get('name'),
                            'connector_ldap': connected_googler.get('ldap'),
                            'relationship': relationship,
                            'target': contact.get('name'),
                            'target_ldap': contact.get('ldap')
                        }
                    })

            # Limit network expansion results
            network_expansion_connections = network_expansion_connections[:8]

            if network_expansion_connections:
                logger.debug(f"Found {len(network_expansion_connections)} network expansion opportunities")
                connections.extend(network_expansion_connections)

        logger.debug(f"Found {len(connections)} total connections before deduplication for {employee_ldap}")

        # --- DEDUPLICATION: Keep only the shortest path for each unique QT employee ---
        qt_best_connections = {}  # Map of qtLdap -> connection with minimum pathLength

        for conn in connections:
            qt_ldap = conn.get('qtLdap')
            if not qt_ldap:
                continue

            path_length = conn.get('pathLength', 999)  # Default to high number if not specified

            # If this QT employee hasn't been seen, or this path is shorter, keep it
            if qt_ldap not in qt_best_connections:
                qt_best_connections[qt_ldap] = conn
            else:
                existing_path_length = qt_best_connections[qt_ldap].get('pathLength', 999)
                if path_length < existing_path_length:
                    logger.debug(f"  Replacing connection to {qt_ldap}: path {existing_path_length} -> {path_length}")
                    qt_best_connections[qt_ldap] = conn
                else:
                    logger.debug(f"  Skipping duplicate connection to {qt_ldap}: path {path_length} (keeping {existing_path_length})")

        # Convert back to list
        deduplicated_connections = list(qt_best_connections.values())

        logger.debug(f"After deduplication: {len(deduplicated_connections)} unique QT connections for {employee_ldap}")

        # Cache the result for future requests (memory + disk + GCS)
        connections_result_cache[cache_key] = (deduplicated_connections, current_time)

        # Save to disk cache for persistence across restarts
        disk_cache_key = f'connections_result_{employee_ldap}'
        save_to_disk_cache(disk_cache_key, deduplicated_connections)
        logger.debug(f"✓ Saved connections to disk cache for {employee_ldap}")

        # Save to GCS cache for long-term persistence (1 week)
        save_to_gcs_cache(disk_cache_key, deduplicated_connections)

        return deduplicated_connections

    except Exception as e:
        # Handle quota exceeded errors silently - don't spam logs
        if "Quota exceeded" in str(e) or "429" in str(e):
            # Return empty connections for quota exceeded (graceful degradation)
            return []
        logger.error(f"Connections error for {employee_ldap}: {e}")
        return []

@bp.route('/api/connections/<employee_ldap>')
def get_connections(employee_ldap):
    """API endpoint to get connections for an employee"""
    try:
        connections = get_connections_data(employee_ldap)
        return jsonify(connections)
    except Exception as e:
        # Handle quota exceeded errors silently - don't spam logs
        if "Quota exceeded" in str(e) or "429" in str(e):
            # Return empty connections for quota exceeded (graceful degradation)
            return jsonify([])
        logger.error(f"API Connections error for {employee_ldap}: {e}")
        return jsonify([])

@bp.route('/api/health')
def health_check():
    """Optimized health check"""
    try:
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'data_loaded': len(employees_data) > 0,
            'total_records': len(employees_data),
            'performance': {
                'optimization_level': 'High',
                'last_sync': last_sync_time.isoformat() if last_sync_time else None,
                'processing_time': processing_stats.get('processing_time', 0) if processing_stats else 0,
                'memory_management': 'Active',
                'caching': 'Enabled'
            }
        })
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

# Root route handler to redirect to main path
@app.route('/')
def root():
    return redirect('/smartstakeholdersearch/')

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

# Add this debug endpoint to your app.py to test Google Sheets write capability

# Replace the debug endpoint in your app.py with this fixed version:

@bp.route('/api/debug-google-sheets')
def debug_google_sheets_enhanced():
    """Enhanced debug endpoint to test Google Sheets connectivity and permissions"""
    try:
        logger.debug("🔍 Starting enhanced Google Sheets debug...")
        
        debug_info = {
            'timestamp': datetime.now().isoformat(),
            'config': {
                'spreadsheet_id': GOOGLE_SHEETS_CONFIG['spreadsheet_id'],
                'spreadsheet_url': GOOGLE_SHEETS_CONFIG['spreadsheet_url'],
                'service_account_file': GOOGLE_SHEETS_CONFIG['service_account_file'],
                'file_exists': os.path.exists(GOOGLE_SHEETS_CONFIG['service_account_file']),
                'env_var_exists': 'GOOGLE_SERVICE_ACCOUNT_JSON' in os.environ
            },
            'tests': {},
            'recommendations': []
        }
        
        # Test 1: Basic authentication
        logger.debug("🔐 Testing authentication...")
        if not sheet_writer.connector.client:
            auth_success = sheet_writer.connector.authenticate()
            debug_info['tests']['authentication'] = {
                'success': auth_success,
                'message': 'Authentication successful' if auth_success else 'Authentication failed'
            }
            
            if not auth_success:
                debug_info['recommendations'].append('Check your credentials.json file or GOOGLE_SERVICE_ACCOUNT_JSON environment variable')
                return jsonify({
                    'status': 'error',
                    'issue': 'Authentication failed',
                    'debug': debug_info
                }), 500
        else:
            debug_info['tests']['authentication'] = {
                'success': True,
                'message': 'Already authenticated'
            }
        
        # Test 2: Spreadsheet connection
        logger.debug("📊 Testing spreadsheet connection...")
        if not sheet_writer.connector.connect_to_spreadsheet():
            debug_info['tests']['spreadsheet_connection'] = {
                'success': False,
                'message': 'Cannot connect to spreadsheet'
            }
            debug_info['recommendations'].append('Share the Google Sheet with your service account email')
            debug_info['recommendations'].append('Verify the spreadsheet ID is correct')
            return jsonify({
                'status': 'error',
                'issue': 'Cannot connect to spreadsheet',
                'debug': debug_info
            }), 500
        
        debug_info['tests']['spreadsheet_connection'] = {
            'success': True,
            'message': f'Connected to: {sheet_writer.connector.spreadsheet.title}',
            'available_sheets': [ws.title for ws in sheet_writer.connector.spreadsheet.worksheets()]
        }
        
        # Test 3: Connections sheet access/creation
        logger.debug("📋 Testing Connections sheet access...")
        connections_sheet = sheet_writer.get_or_create_connections_sheet()
        if not connections_sheet:
            debug_info['tests']['connections_sheet'] = {
                'success': False,
                'message': 'Cannot access or create Connections sheet'
            }
            debug_info['recommendations'].append('Ensure service account has Editor permissions, not just Viewer')
            return jsonify({
                'status': 'error',
                'issue': 'Cannot access Connections sheet',
                'debug': debug_info
            }), 500
        
        debug_info['tests']['connections_sheet'] = {
            'success': True,
            'message': 'Connections sheet accessible',
            'sheet_id': connections_sheet.id,
            'sheet_title': connections_sheet.title,
            'sheet_url': f"{GOOGLE_SHEETS_CONFIG['spreadsheet_url']}&gid={connections_sheet.id}",
            'row_count': connections_sheet.row_count,
            'col_count': connections_sheet.col_count,
            'headers': connections_sheet.row_values(1) if connections_sheet.row_count > 0 else []
        }
        
        # Test 4: Write capability test
        logger.debug("✏️ Testing write capability...")
        try:
            # Write a simple test row
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            test_row = [
                timestamp,
                'debug.test',
                'Debug Test User',
                'debug.test@google.com',
                'Test Department',
                'debug.qt',
                'Debug QT User',
                'debug.qt@qualitestgroup.com',
                'QT Test',
                'Medium',
                'Debug System',
                'Automated debug test - safe to delete'
            ]
            
            connections_sheet.append_row(test_row)
            logger.debug("✅ Write test successful!")
            
            debug_info['tests']['write_capability'] = {
                'success': True,
                'message': 'Write test successful - test row added to Connections sheet',
                'test_data_written': True
            }
            
            return jsonify({
                'status': 'success',
                'message': 'All Google Sheets tests passed! Your integration is working correctly.',
                'debug': debug_info,
                'next_steps': [
                    'Try declaring connections from the declare.html page',
                    'Check the Connections sheet for new data',
                    'The debug test row can be safely deleted'
                ]
            })
                
        except Exception as write_error:
            debug_info['tests']['write_capability'] = {
                'success': False,
                'message': f'Write test failed: {str(write_error)}'
            }
            
            if "permission" in str(write_error).lower():
                debug_info['recommendations'].append('Service account needs Editor permissions to write data')
            
            return jsonify({
                'status': 'error',
                'issue': 'Write test failed',
                'debug': debug_info
            }), 500
        
    except Exception as e:
        logger.error(f"❌ Debug endpoint error: {e}")
        return jsonify({
            'status': 'error',
            'issue': f'Debug failed: {str(e)}',
            'error_type': type(e).__name__,
            'timestamp': datetime.now().isoformat()
        }), 500

@bp.route('/api/read-connections-sheet')
def read_connections_sheet():
    """Reads and returns the content of the 'Connections' sheet (cached)."""
    try:
        logger.debug("📖 Reading connections from cache...")

        # Use cached connections data to avoid quota issues
        records = get_cached_connections_data()

        logger.debug(f"✅ Retrieved {len(records)} connection records from cache")

        return jsonify({
            'connections': records,
            'total_count': len(records),
            'sheet_url': f"{GOOGLE_SHEETS_CONFIG['spreadsheet_url']}",
            'last_updated': datetime.now().isoformat(),
            'cached': True,
            'cache_age_seconds': int(time.time() - (connections_cache_time or 0))
        })
        
    except Exception as e:
        logger.error(f"❌ Error getting connections from sheets: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/debug-employees-data')
def debug_employees_data():
    """Debug endpoint to inspect the first few entries of employees_data"""
    try:
        if not employees_data:
            return jsonify({'message': 'employees_data is empty. Data might not have been loaded yet.'}), 200
        
        # Return first 10 employees for inspection
        return jsonify(employees_data[:10])
    except Exception as e:
        logger.error(f"Error in debug_employees_data: {e}")
        return jsonify({'error': str(e)}), 500


class OptimizedGoogleSheetsWriter:
    """Enhanced connector that can both read and write to Google Sheets - FIXED VERSION"""
    
    def __init__(self, config):
        self.config = config
        self.connector = OptimizedGoogleSheetsConnector(config)
        self._connections_sheet = None
        
    def get_or_create_connections_sheet(self):
        """FIXED: Get the Connections sheet or create it if it doesn't exist"""
        try:
            # Use cached sheet if available
            if self._connections_sheet:
                return self._connections_sheet
                
            if not self.connector.spreadsheet:
                if not self.connector.connect_to_spreadsheet():
                    logger.error("❌ Cannot connect to spreadsheet")
                    return None
            
            logger.debug("🔍 Looking for 'Connections' sheet...")
            
            # Try to get existing Connections sheet
            try:
                connections_sheet = self.connector.spreadsheet.worksheet('Connections')
                logger.debug("✅ Found existing 'Connections' sheet")
                self._connections_sheet = connections_sheet
                return connections_sheet
            except gspread.WorksheetNotFound:
                logger.debug("📄 'Connections' sheet not found, will create new one...")
            except Exception as e:
                logger.warning(f"⚠️ Error accessing Connections sheet: {e}")
            
            # Create new sheet
            try:
                logger.debug("🆕 Creating new 'Connections' sheet...")
                connections_sheet = self.connector.spreadsheet.add_worksheet(
                    title='Connections', 
                    rows=1000, 
                    cols=12
                )
                
                # Add comprehensive headers
                headers = [
                    'Timestamp',
                    'Google Employee LDAP',
                    'Google Employee Name', 
                    'Google Employee Email',
                    'Google Employee Department',
                    'QT Employee LDAP',
                    'QT Employee Name',
                    'QT Employee Email', 
                    'QT Employee Department',
                    'Connection Strength',
                    'Declared By',
                    'Notes'
                ]
                
                connections_sheet.append_row(headers)
                logger.debug("✅ Created new 'Connections' sheet with headers")
                self._connections_sheet = connections_sheet
                return connections_sheet
                
            except Exception as create_error:
                error_msg = str(create_error)
                logger.error(f"❌ Failed to create Connections sheet: {error_msg}")
                
                if "permission" in error_msg.lower():
                    logger.error("💡 SOLUTION: Service account needs Editor permissions!")
                    logger.error("📧 Share the Google Sheet with your service account email")
                elif "quota" in error_msg.lower():
                    logger.error("💡 SOLUTION: API quota exceeded, wait a moment")
                
                return None
                
        except Exception as e:
            logger.error(f"❌ Unexpected error in get_or_create_connections_sheet: {e}")
            return None
    
    def write_connection_to_sheet(self, google_employee_ldap, qt_employee_ldap, connection_strength, declared_by="System"):
        """Write a single connection to Google Sheet"""
        try:
            # Get employee details with better fallback handling
            google_emp = get_employee_by_ldap(google_employee_ldap)
            if not google_emp:
                google_emp = {
                    'ldap': google_employee_ldap,
                    'name': google_employee_ldap.replace('.', ' ').title(),
                    'email': f"{google_employee_ldap}@google.com",
                    'department': 'Unknown'
                }

            qt_emp = next((emp for emp in core_team if emp.get('ldap') == qt_employee_ldap), None)
            if not qt_emp:
                qt_emp = {
                    'ldap': qt_employee_ldap,
                    'name': qt_employee_ldap.replace('.', ' ').title(),
                    'email': f"{qt_employee_ldap}@qualitestgroup.com",
                    'department': 'QT Team'
                }

            # Get or create Connections sheet
            connections_sheet = self.get_or_create_connections_sheet()
            if not connections_sheet:
                logger.error("Failed to get Connections sheet")
                return False

            # Prepare row data
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            row_data = [
                timestamp,
                google_emp.get('ldap', ''),
                google_emp.get('name', ''),
                google_emp.get('email', ''),
                google_emp.get('department', ''),
                qt_emp.get('ldap', ''),
                qt_emp.get('name', ''),
                qt_emp.get('email', ''),
                qt_emp.get('department', ''),
                connection_strength.title(),
                declared_by,
                "Connection declared via Qonnect app"
            ]

            # Write to Google Sheets
            api_rate_limiter.wait_if_needed()
            connections_sheet.append_row(row_data)
            logger.debug(f"✅ Successfully wrote connection: {google_emp.get('name')} <-> {qt_emp.get('name')} ({connection_strength})")
            return True

        except Exception as e:
            logger.error(f"❌ Error writing connection to Google Sheets: {e}")
            return False
    
    def write_batch_connections_to_sheet(self, google_employee_ldap, connections_dict, declared_by="System"):
        """Write multiple connections to Google Sheet"""
        try:
            logger.debug(f"📝 Starting batch write: {len(connections_dict)} connections for {google_employee_ldap}")

            # Get Google employee with enhanced fallback
            google_emp = get_employee_by_ldap(google_employee_ldap)
            if not google_emp:
                logger.warning(f"⚠️ Google employee {google_employee_ldap} not found in data")
                google_emp = {
                    'ldap': google_employee_ldap,
                    'name': google_employee_ldap.replace('.', ' ').title(),
                    'email': f"{google_employee_ldap}@google.com",
                    'department': 'Unknown'
                }

            logger.debug(f"📋 Google employee: {google_emp.get('name')} ({google_emp.get('ldap')})")

            # Prepare batch data
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            connections_to_add = []
            successful_connections = []

            logger.debug(f"🔄 Processing {len(connections_dict)} connections...")

            for qt_ldap, strength in connections_dict.items():
                logger.debug(f"  Processing: {qt_ldap} -> {strength}")

                # Find QT employee with enhanced fallback
                qt_emp = next((emp for emp in core_team if emp.get('ldap') == qt_ldap), None)
                if not qt_emp:
                    logger.warning(f"    ⚠️ QT employee {qt_ldap} not found in core_team")
                    qt_emp = {
                        'ldap': qt_ldap,
                        'name': qt_ldap.replace('.', ' ').title(),
                        'email': f"{qt_ldap}@qualitestgroup.com",
                        'department': 'QT Team'
                    }

                logger.debug(f"    📋 QT employee: {qt_emp.get('name')}")

                connection_data = {
                    'timestamp': timestamp,
                    'google_employee_ldap': google_emp.get('ldap', ''),
                    'google_employee_name': google_emp.get('name', ''),
                    'google_employee_email': google_emp.get('email', ''),
                    'google_employee_department': google_emp.get('department', ''),
                    'qt_employee_ldap': qt_emp.get('ldap', ''),
                    'qt_employee_name': qt_emp.get('name', ''),
                    'qt_employee_email': qt_emp.get('email', ''),
                    'qt_employee_department': qt_emp.get('department', ''),
                    'connection_strength': strength.title(),
                    'declared_by': declared_by,
                    'notes': f"Batch connection declared via Qonnect app"
                }

                connections_to_add.append(connection_data)
                successful_connections.append(f"{qt_emp.get('name')} ({strength})")
                logger.debug(f"    ✅ Connection prepared for {qt_emp.get('name')}")

            if connections_to_add:
                logger.debug(f"📤 Writing {len(connections_to_add)} connections to Google Sheets...")
                try:
                    # Get or create Connections sheet
                    connections_sheet = self.get_or_create_connections_sheet()
                    if not connections_sheet:
                        logger.error("Failed to get Connections sheet")
                        return False, "Failed to access Google Sheets"

                    # Write all connections as rows
                    rows_to_add = []
                    for conn_data in connections_to_add:
                        row = [
                            conn_data.get('timestamp', ''),
                            conn_data.get('google_employee_ldap', ''),
                            conn_data.get('google_employee_name', ''),
                            conn_data.get('google_employee_email', ''),
                            conn_data.get('google_employee_department', ''),
                            conn_data.get('qt_employee_ldap', ''),
                            conn_data.get('qt_employee_name', ''),
                            conn_data.get('qt_employee_email', ''),
                            conn_data.get('qt_employee_department', ''),
                            conn_data.get('connection_strength', ''),
                            conn_data.get('declared_by', ''),
                            conn_data.get('notes', '')
                        ]
                        rows_to_add.append(row)

                    # Write in batch for better performance
                    api_rate_limiter.wait_if_needed()
                    connections_sheet.append_rows(rows_to_add)
                    logger.debug(f"🎉 Successfully wrote {len(rows_to_add)} connections to Google Sheets!")

                    success_message = f"Successfully saved {len(rows_to_add)} connections to Google Sheets: {', '.join(successful_connections)}"
                    return success_message

                except Exception as write_error:
                    error_msg = str(write_error)
                    logger.error(f"❌ Write operation failed: {error_msg}")
                    return None
            else:
                return None

        except Exception as e:
            logger.error(f"❌ Unexpected error in batch write: {e}")
            return False, f"Unexpected error: {str(e)}"

# Initialize the writer
sheet_writer = OptimizedGoogleSheetsWriter(GOOGLE_SHEETS_CONFIG)

# Enhanced API endpoint for batch connection updates
@bp.route('/api/batch-update-connections', methods=['POST'])
def batch_update_connections_enhanced():
    """FIXED: Enhanced connection updates that write to Google Sheets"""
    try:
        data = request.get_json()
        google_ldap = data.get('googleLdap')
        connections = data.get('connections', {})
        declared_by = data.get('declaredBy', 'Qonnect User')
        
        logger.debug(f"🎯 Connection update request received:")
        logger.debug(f"  Google LDAP: {google_ldap}")
        logger.debug(f"  Connections: {len(connections)} items")
        logger.debug(f"  Data: {connections}")
        
        if not google_ldap or not connections:
            logger.error("❌ Missing required data")
            return jsonify({
                'success': False, 
                'error': 'Missing required data (googleLdap or connections)',
                'received_data': {
                    'googleLdap': google_ldap,
                    'connections': connections,
                    'declaredBy': declared_by
                }
            }), 400
        
        # Update in-memory data (existing functionality)
        logger.debug("💾 Updating in-memory data...")
        google_employee = get_employee_by_ldap(google_ldap)
        if google_employee:
            # Initialize connections if not exists
            if 'connections' not in google_employee:
                google_employee['connections'] = []
            
            # Update connections
            for qt_ldap, strength in connections.items():
                # Find existing connection
                existing_conn = next((conn for conn in google_employee['connections'] 
                                    if conn.get('ldap') == qt_ldap), None)
                
                if existing_conn:
                    existing_conn['connectionStrength'] = strength
                    logger.debug(f"  ✏️ Updated existing connection: {qt_ldap} -> {strength}")
                else:
                    # Add new connection
                    qt_employee = next((emp for emp in core_team if emp.get('ldap') == qt_ldap), None)
                    if qt_employee:
                        google_employee['connections'].append({
                            'ldap': qt_ldap,
                            'name': qt_employee.get('name'),
                            'connectionStrength': strength
                        })
                        logger.debug(f"  ➕ Added new connection: {qt_ldap} -> {strength}")
        
        logger.debug("✅ In-memory data updated successfully")
        
        # Write to Google Sheets with enhanced error handling
        logger.debug("📝 Attempting to write to Google Sheets...")
        try:
            success, message = sheet_writer.write_batch_connections_to_sheet(
                google_ldap, 
                connections, 
                declared_by
            )
            
            if success:
                logger.debug(f"🎉 Google Sheets write successful!")
                # Invalidate cache since we just wrote new data
                invalidate_connections_cache()
                return jsonify({
                    'success': True,
                    'updated_count': len(connections),
                    'message': message,
                    'google_employee': google_ldap,
                    'written_to_sheets': True,
                    'sheets_url': f"{GOOGLE_SHEETS_CONFIG['spreadsheet_url']}&gid=0",
                    'timestamp': datetime.now().isoformat(),
                    'connections_saved': connections
                })
            else:
                logger.warning(f"⚠️ Google Sheets write failed: {message}")
                # Still return success for in-memory update
                return jsonify({
                    'success': True,
                    'updated_count': len(connections),
                    'message': f'Connections updated in memory. Google Sheets error: {message}',
                    'google_employee': google_ldap,
                    'written_to_sheets': False,
                    'sheets_error': message,
                    'timestamp': datetime.now().isoformat(),
                    'fallback_mode': True
                })
                
        except Exception as e:
            logger.error(f"❌ Google Sheets write error: {e}")
            # Still return success for in-memory update
            return jsonify({
                'success': True,
                'updated_count': len(connections),
                'message': f'Connections updated in memory. Google Sheets unavailable: {str(e)}',
                'google_employee': google_ldap,
                'written_to_sheets': False,
                'sheets_error': str(e),
                'timestamp': datetime.now().isoformat(),
                'fallback_mode': True
            })
        
    except Exception as e:
        logger.error(f"❌ API endpoint error: {e}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# Internal function to read connections data from Google Sheets
def _read_connections_from_sheets_internal():
    """Internal function to read connections directly from Google Sheets (returns list)"""
    try:
        if not processor.connector.spreadsheet:
            if not processor.connector.connect_to_spreadsheet():
                logger.error("Cannot connect to spreadsheet")
                return []

        connections_sheet = processor.connector.spreadsheet.worksheet('Connections')
        api_rate_limiter.wait_if_needed()
        all_values = connections_sheet.get_all_values()

        if not all_values or len(all_values) <= 1:
            logger.debug("Connections sheet is empty or has no data")
            return []

        headers = all_values[0]
        data_rows = all_values[1:]
        # Filter out empty rows
        data_rows = [row for row in data_rows if any(cell.strip() for cell in row)]

        if not data_rows:
            return []

        # Convert to list of dicts
        records = []
        for row in data_rows:
            # Pad row to match headers length
            padded_row = row + [''] * (len(headers) - len(row))
            record = dict(zip(headers, padded_row))
            records.append(record)

        logger.debug(f"✅ Read {len(records)} connection records from Google Sheets")
        return records

    except gspread.WorksheetNotFound:
        logger.warning("Connections sheet not found")
        return []
    except Exception as e:
        logger.error(f"Error reading connections from Google Sheets: {e}")
        return []

# New endpoint to view connections from Google Sheets
@bp.route('/api/connections-from-sheets')
def get_connections_from_sheets():
    """Get all connections from the Google Sheets Connections tab (cached) - API ENDPOINT"""
    try:
        logger.debug("📖 Getting connections from cache...")

        # Use cached data to avoid API quota issues
        records = get_cached_connections_data()

        logger.debug(f"✅ Retrieved {len(records)} connection records from cache")

        return jsonify({
            'connections': records,
            'total_count': len(records),
            'sheet_url': f"{GOOGLE_SHEETS_CONFIG['spreadsheet_url']}",
            'last_updated': datetime.now().isoformat(),
            'cached': True,
            'cache_age_seconds': int(time.time() - (connections_cache_time or 0))
        })

    except Exception as e:
        logger.error(f"❌ Error getting connections: {e}")
        return jsonify({
            'error': str(e),
            'connections': [],
            'total_count': 0,
            'cached': False
        }), 500

# New endpoint to get connection statistics
@bp.route('/api/connection-stats')
def get_connection_stats():
    """Get statistics about declared connections (cached)"""
    try:
        # Use cached data to avoid API quota issues
        records = get_cached_connections_data()
        
        # Calculate statistics
        stats = {
            'total_connections': len(records),
            'unique_google_employees': len(set(r.get('Google Employee LDAP', '') for r in records if r.get('Google Employee LDAP'))),
            'unique_qt_employees': len(set(r.get('QT Employee LDAP', '') for r in records if r.get('QT Employee LDAP'))),
            'strength_breakdown': {
                'strong': len([r for r in records if r.get('Connection Strength', '').lower() == 'strong']),
                'medium': len([r for r in records if r.get('Connection Strength', '').lower() == 'medium']),
                'weak': len([r for r in records if r.get('Connection Strength', '').lower() == 'weak'])
            },
            'recent_connections': len([r for r in records if r.get('Timestamp', '') and 
                                    datetime.now() - datetime.strptime(r['Timestamp'], '%Y-%m-%d %H:%M:%S') < timedelta(days=7)])
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting connection stats: {e}")
        return jsonify({'error': str(e)}), 500

def startup_cache_warmup():
    """Pre-warm the cache on application startup - AGGRESSIVE MODE"""
    try:
        logger.debug("🔥 Warming up cache on startup...")

        # 1. Load employee data (includes disk cache, search index, org hierarchy)
        load_google_sheets_data_optimized()

        # 2. Load connections data (includes disk cache)
        get_cached_connections_data()

        # 3. Pre-compute hierarchies for core team members (most likely to be searched)
        if core_team:
            logger.debug(f"🎯 Pre-computing hierarchies for {len(core_team)} core team members...")
            for member in core_team[:20]:  # Pre-warm top 20 core team members
                ldap = member.get('ldap')
                if ldap:
                    try:
                        get_employee_hierarchy(ldap)
                    except Exception as e:
                        logger.debug(f"Error pre-computing hierarchy for {ldap}: {e}")

        # 4. Pre-populate LRU cache with common employee lookups
        if employees_data:
            logger.debug(f"🎯 Pre-populating LRU cache with {min(100, len(employees_data))} employees...")
            for emp in employees_data[:100]:  # Pre-warm top 100 employees
                ldap = emp.get('ldap')
                if ldap:
                    try:
                        get_employee_by_ldap(ldap)
                    except Exception as e:
                        logger.debug(f"Error pre-loading employee {ldap}: {e}")

        logger.debug("✅ Cache warmed up successfully")
    except Exception as e:
        logger.error(f"❌ Cache warmup failed: {e}")

# Register blueprint
app.register_blueprint(bp)

# Warmup cache on module load (for Gunicorn with --preload)
# This runs once when the app is loaded, before workers are forked
if os.environ.get('ENABLE_STARTUP_WARMUP', 'true').lower() == 'true':
    print("🔥 Starting cache warmup on app load...")
    try:
        startup_cache_warmup()
        print("✅ Cache warmup complete - ready to serve requests")
    except Exception as e:
        print(f"⚠️ Cache warmup failed: {e}")
        print("⚡ Will load data on first request instead")

if __name__ == '__main__':
    # Get port from environment variable (Cloud Run) or use 8080 as default
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 Qonnect - Starting on port {port}")

    # Enable cache warmup for better first-request performance
    print("🔥 Starting cache warmup...")
    startup_cache_warmup()
    print("✅ Cache warmup complete - ready to serve requests")

    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)