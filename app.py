from flask import Flask, jsonify, request, render_template_string, send_from_directory
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
from functools import lru_cache
import gc
import time

app = Flask(__name__)
CORS(app)

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
api_rate_limiter = APIRateLimiter(min_interval=2.0)  # 2 seconds between calls for quota safety

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

# Global data storage - Optimized
employees_data = []
google_employees = []
core_team = []
processing_stats = {}
last_sync_time = None

# Cached connections data to avoid quota issues
cached_connections_data = None
connections_cache_time = None
connections_cache_ttl = 300  # 5 minutes cache TTL

@lru_cache(maxsize=1000)
def get_employee_by_ldap(ldap: str):
    """Cached employee lookup by LDAP"""
    return next((emp for emp in employees_data if emp.get('ldap') == ldap), None)

def get_cached_connections_data():
    """Get cached connections data to avoid Google Sheets API quota issues"""
    global cached_connections_data, connections_cache_time

    current_time = time.time()

    # Check if cache is valid
    if (cached_connections_data is not None and
        connections_cache_time is not None and
        current_time - connections_cache_time < connections_cache_ttl):
        logger.debug(f"📋 Using cached connections data ({len(cached_connections_data)} records)")
        return cached_connections_data

    # Cache is stale or doesn't exist, fetch fresh data
    try:
        logger.debug("🔄 Refreshing connections cache from Google Sheets...")
        api_rate_limiter.wait_if_needed()  # Respect rate limits

        connections_sheet = sheet_writer.get_or_create_connections_sheet()
        if not connections_sheet:
            logger.warning("⚠️ Could not access Connections sheet, using empty cache")
            cached_connections_data = []
            connections_cache_time = current_time
            return cached_connections_data

        records = connections_sheet.get_all_records()
        cached_connections_data = records
        connections_cache_time = current_time

        logger.debug(f"✅ Cached {len(cached_connections_data)} connections records")
        return cached_connections_data

    except Exception as e:
        logger.error(f"❌ Error refreshing connections cache: {e}")
        # Return stale cache if available, otherwise empty list
        if cached_connections_data is not None:
            logger.warning("⚠️ Using stale cache due to API error")
            return cached_connections_data
        return []

def invalidate_connections_cache():
    """Invalidate the connections cache to force refresh on next access"""
    global cached_connections_data, connections_cache_time
    cached_connections_data = None
    connections_cache_time = None
    logger.debug("🗑️ Connections cache invalidated")

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
            
            # Handle QT team members (Olenick employees)
            qt_ldaps = ['lihi.segev', 'abhijeet.bagade', 'omri.nissim', 'kobi.kol', 
                       'jillian.orrico', 'michael.bush', 'mayank.arya']
            
            if emp_id.lower() in qt_ldaps:
                email = f"{emp_id}@olenick.com"
                organisation = 'Olenick' 
                company = 'OLENICK'
            
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
                'olenick_employees': 0,
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
                        elif employee['organisation'] == 'Olenick':
                            stats['olenick_employees'] += 1
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
            logger.debug(f"Olenick employees: {stats['olenick_employees']:,}")
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
    
    try:
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
        
        # Build organizational relationships from manager data
        build_organizational_hierarchy()
        
        # Optimized categorization using list comprehensions
        google_employees = [emp for emp in employees if emp.get('organisation') == 'Google']
        olenick_employees = [emp for emp in employees if emp.get('organisation') == 'Olenick']
        
        # Initialize core team (limited for performance)
        core_team = olenick_employees[:min(50, len(olenick_employees))]
        for team_member in core_team:
            team_member['connections'] = []
        
        # Calculate unique counts efficiently
        departments = len(set(emp.get('department', 'Unknown') for emp in employees))
        locations = len(set(emp.get('location', 'Unknown') for emp in employees))
        
        logger.debug(f"Successfully loaded employee data:")
        logger.debug(f"Total: {len(employees_data):,}")
        logger.debug(f"Google: {len(google_employees):,}")
        logger.debug(f"Olenick: {len(olenick_employees):,}")
        logger.debug(f"Departments: {departments}")
        logger.debug(f"Locations: {locations}")
        
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
    """Get the full hierarchy for an employee (manager chain and reportees)"""
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
        while current and current.get('manager_info'):
            manager = get_employee_by_ldap(current['manager_info']['ldap'])
            if manager:
                hierarchy['manager_chain'].append(manager)
                current = manager
            else:
                break
        
        # Count peers (people with same manager)
        if employee.get('manager_info'):
            manager = get_employee_by_ldap(employee['manager_info']['ldap'])
            if manager:
                hierarchy['peer_count'] = len(manager.get('reportees', [])) - 1  # Exclude self
        
        return hierarchy
        
    except Exception as e:
        logger.error(f"Error getting hierarchy for {employee_ldap}: {e}")
        return None

# Optimized Flask Routes
@app.route('/')
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

@app.route('/declare')
def declare():
    try:
        with open('templates/declare.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return '<h1>Declare page not found</h1><a href="/">Back to Home</a>'

@app.route('/search')
def search():
    try:
        with open('templates/search.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return '<h1>Search page not found</h1><a href="/">Back to Home</a>'

# FIXED API Endpoints

@app.route('/api/sync-google-sheets', methods=['POST'])
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

@app.route('/api/sync-sharepoint', methods=['POST'])
def sync_sharepoint():
    """Legacy endpoint - redirects to optimized Google Sheets sync"""
    return sync_google_sheets()

@app.route('/api/search-employees')
def search_employees():
    """FIXED: Employee search that finds actual employees, not their reportees"""
    # Auto-load data if not loaded yet
    if not employees_data:
        logger.debug("Data not loaded, loading now...")
        load_google_sheets_data_optimized()

    query = request.args.get('q', '').lower().strip()

    if len(query) < 2:
        return jsonify([])

    try:
        filtered = []
        max_results = 25
        seen_employees = set()  # Track unique employees by LDAP to avoid duplicates

        # Temporary check for epersitz
        epersitz_found_in_employees_data = any(emp.get('ldap') == 'epersitz' for emp in employees_data)
        logger.debug(f"DEBUG: 'epersitz' found in employees_data: {epersitz_found_in_employees_data}")

        for emp in employees_data:
            if len(filtered) >= max_results:
                break

            # Skip duplicate employees (same LDAP)
            employee_ldap = emp.get('ldap', '').lower().strip()
            if not employee_ldap or employee_ldap in seen_employees:
                continue

            score = 0
            
            # FIXED: Search the employee's own details, NOT manager relationships
            name = emp.get('name', '').lower()
            logger.debug(f"Search: Employee Name: '{name}', Query in Name: {query in name}")
            if query in name:
                score += 10
                if name.startswith(query):
                    score += 5
            
            email = emp.get('email', '').lower()
            logger.debug(f"Search: Employee Email: '{email}', Query in Email: {query in email}")
            if query in email:
                score += 8
                if email.startswith(query):
                    score += 3
            
            ldap = emp.get('ldap', '').lower()
            logger.debug(f"Search: Employee LDAP: '{ldap}', Query in LDAP: {query in ldap}")
            if query in ldap:
                score += 7
                if ldap.startswith(query):
                    score += 3
            
            logger.debug(f"Search: Employee '{emp.get('name')}' final score: {score}")

            if score == 0:
                # Check other fields only if no name/email/ldap match
                if query in emp.get('department', '').lower():
                    score += 4
                elif query in emp.get('designation', '').lower():
                    score += 3
            
            if score > 0:
                # Mark this employee as seen
                seen_employees.add(employee_ldap)

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
                    # Lazy loading - hierarchy and connections loaded on-demand via API calls
                    'reportees_count': 0,  # Will be loaded when needed
                    'manager_chain_length': 0,  # Will be loaded when needed
                    'has_reportees': False,  # Will be loaded when needed
                    'declared_connections': []  # Will be loaded when user clicks on employee
                }

                filtered.append(emp_copy)
        
        # Sort by score first, then alphabetically by name
        filtered.sort(key=lambda x: (
            x['_search_score'],
            x['name'].lower()
        ), reverse=True)
        return jsonify(filtered)

    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify([])

@app.route('/api/debug-get-employee-by-ldap/<ldap_id>')
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


@app.route('/api/search-google-employees')
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

@app.route('/api/google-employees')
def get_google_employees():
    """Get Google employees (optimized)"""
    # Auto-load data if not loaded yet
    if not employees_data:
        logger.debug("Data not loaded, loading now...")
        load_google_sheets_data_optimized()

    try:
        # Return lightweight employee objects
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
            for emp in google_employees
        ])
        
    except Exception as e:
        logger.error(f"Error getting Google employees: {e}")
        return jsonify([])

@app.route('/api/qt-team')
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

@app.route('/api/hierarchy/<employee_ldap>')
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

@app.route('/api/employees/<employee_id>')
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

@app.route('/api/departments')
def get_departments():
    """Optimized departments endpoint"""
    try:
        dept_counts = {}
        
        # Single pass through employees
        for emp in employees_data:
            dept = emp.get('department', 'Unknown')
            if dept not in dept_counts:
                dept_counts[dept] = {'count': 0, 'google': 0, 'olenick': 0, 'other': 0}
            
            dept_counts[dept]['count'] += 1
            org = emp.get('organisation', 'Other')
            if org == 'Google':
                dept_counts[dept]['google'] += 1
            elif org == 'Olenick':
                dept_counts[dept]['olenick'] += 1
            else:
                dept_counts[dept]['other'] += 1
        
        departments = [
            {
                'name': dept,
                'count': counts['count'],
                'google_count': counts['google'],
                'olenick_count': counts['olenick'],
                'other_count': counts['other']
            }
            for dept, counts in dept_counts.items()
        ]
        
        departments.sort(key=lambda x: x['count'], reverse=True)
        return jsonify(departments[:50])  # Limit results
        
    except Exception as e:
        logger.error(f"Error getting departments: {e}")
        return jsonify([])

@app.route('/api/locations')
def get_locations():
    """Optimized locations endpoint"""
    try:
        location_counts = {}
        
        # Single pass through employees
        for emp in employees_data:
            location = emp.get('location', 'Unknown')
            if location not in location_counts:
                location_counts[location] = {'count': 0, 'google': 0, 'olenick': 0, 'other': 0}
            
            location_counts[location]['count'] += 1
            org = emp.get('organisation', 'Other')
            if org == 'Google':
                location_counts[location]['google'] += 1
            elif org == 'Olenick':
                location_counts[location]['olenick'] += 1
            else:
                location_counts[location]['other'] += 1
        
        locations = [
            {
                'name': location,
                'count': counts['count'],
                'google_count': counts['google'],
                'olenick_count': counts['olenick'],
                'other_count': counts['other']
            }
            for location, counts in location_counts.items()
        ]
        
        locations.sort(key=lambda x: x['count'], reverse=True)
        return jsonify(locations[:50])  # Limit results
        
    except Exception as e:
        logger.error(f"Error getting locations: {e}")
        return jsonify([])

@app.route('/api/stats')
def get_stats():
    """Optimized stats endpoint"""
    try:
        # Calculate stats efficiently
        total_employees = len(employees_data)
        google_count = len(google_employees)
        olenick_count = len([e for e in employees_data if e.get('organisation') == 'Olenick'])
        other_count = total_employees - google_count - olenick_count
        
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
            'olenick_employees': olenick_count,
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
@app.route('/api/batch-update-connections', methods=['POST'])
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
        
        # FIXED: Direct Google Sheets writing without relying on sheet_writer object
        logger.debug("📝 Writing directly to Google Sheets...")
        try:
            # Create a fresh connector instance
            from google.oauth2.service_account import Credentials
            import gspread
            import os
            import json
            from datetime import datetime
            
            # Authenticate directly
            if os.path.exists(GOOGLE_SHEETS_CONFIG['service_account_file']):
                creds = Credentials.from_service_account_file(
                    GOOGLE_SHEETS_CONFIG['service_account_file'],
                    scopes=GOOGLE_SHEETS_CONFIG['scopes']
                )
            elif 'GOOGLE_SERVICE_ACCOUNT_JSON' in os.environ:
                service_account_info = json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON'])
                creds = Credentials.from_service_account_info(
                    service_account_info,
                    scopes=GOOGLE_SHEETS_CONFIG['scopes']
                )
            else:
                raise Exception("No credentials available")
            
            # Connect to spreadsheet
            client = gspread.authorize(creds)
            # Apply rate limiting to prevent API quota errors
            api_rate_limiter.wait_if_needed()
            spreadsheet = client.open_by_key(GOOGLE_SHEETS_CONFIG['spreadsheet_id'])
            logger.debug(f"✅ Connected to spreadsheet: {spreadsheet.title}")
            
            # Get or create Connections sheet
            try:
                connections_sheet = spreadsheet.worksheet('Connections')
                logger.debug("✅ Found existing Connections sheet")
            except gspread.WorksheetNotFound:
                logger.debug("📄 Creating new Connections sheet...")
                connections_sheet = spreadsheet.add_worksheet(title='Connections', rows=1000, cols=12)
                
                # Add headers
                headers = [
                    'Timestamp', 'Google Employee LDAP', 'Google Employee Name', 
                    'Google Employee Email', 'Google Employee Department',
                    'QT Employee LDAP', 'QT Employee Name', 'QT Employee Email', 
                    'QT Employee Department', 'Connection Strength', 'Declared By', 'Notes'
                ]
                connections_sheet.append_row(headers)
                logger.debug("✅ Added headers to new sheet")
            
            # Prepare data rows
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            rows_to_add = []
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
                        'email': f"{qt_ldap}@qualitest.com",
                        'department': 'QT Team'
                    }
                
                row_data = [
                    timestamp,
                    google_employee.get('ldap', ''),
                    google_employee.get('name', ''),
                    google_employee.get('email', ''),
                    google_employee.get('department', ''),
                    qt_emp.get('ldap', ''),
                    qt_emp.get('name', ''),
                    qt_emp.get('email', ''),
                    qt_emp.get('department', ''),
                    strength.title(),
                    declared_by,
                    f"Connection declared via Qonnect app"
                ]
                
                rows_to_add.append(row_data)
                successful_connections.append(f"{qt_emp.get('name')} ({strength})")
                logger.debug(f"  📝 Prepared row for {qt_emp.get('name')}")
            
            # Write all rows to Google Sheets
            if rows_to_add:
                connections_sheet.append_rows(rows_to_add)
                logger.debug(f"🎉 Successfully wrote {len(rows_to_add)} rows to Google Sheets!")
                
                return jsonify({
                    'success': True,
                    'updated_count': len(connections),
                    'message': f"Successfully saved {len(rows_to_add)} connections to Google Sheets 'Connections' tab: {', '.join(successful_connections)}",
                    'google_employee': google_ldap,
                    'written_to_sheets': True,
                    'sheets_url': f"{GOOGLE_SHEETS_CONFIG['spreadsheet_url']}&gid={connections_sheet.id}",
                    'timestamp': datetime.now().isoformat()
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'No valid connections to save'
                }), 400
                
        except Exception as sheets_error:
            logger.error(f"❌ Google Sheets write error: {sheets_error}")
            logger.error(f"Error type: {type(sheets_error).__name__}")
            logger.error(f"Error details: {str(sheets_error)}")
            
            # Return success for in-memory but show sheets error
            return jsonify({
                'success': True,
                'updated_count': len(connections),
                'message': f'Connections updated in memory. Google Sheets error: {str(sheets_error)}',
                'google_employee': google_ldap,
                'written_to_sheets': False,
                'sheets_error': str(sheets_error),
                'timestamp': datetime.now().isoformat(),
                'debug': {
                    'error_type': type(sheets_error).__name__,
                    'spreadsheet_id': GOOGLE_SHEETS_CONFIG['spreadsheet_id'],
                    'has_credentials': os.path.exists(GOOGLE_SHEETS_CONFIG['service_account_file'])
                }
            })
        
    except Exception as e:
        logger.error(f"❌ API endpoint error: {e}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/test-sheet-write', methods=['POST'])
def test_sheet_write():
    """Test endpoint to verify Google Sheets writing works"""
    try:
        from google.oauth2.service_account import Credentials
        import gspread
        import os
        import json
        from datetime import datetime
        
        logger.debug("🧪 Testing direct Google Sheets write...")
        
        # Authenticate
        if os.path.exists(GOOGLE_SHEETS_CONFIG['service_account_file']):
            creds = Credentials.from_service_account_file(
                GOOGLE_SHEETS_CONFIG['service_account_file'],
                scopes=GOOGLE_SHEETS_CONFIG['scopes']
            )
        else:
            return jsonify({'success': False, 'error': 'No credentials file found'}), 500
        
        # Connect
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(GOOGLE_SHEETS_CONFIG['spreadsheet_id'])
        
        # Get/create sheet
        try:
            sheet = spreadsheet.worksheet('Connections')
        except:
            sheet = spreadsheet.add_worksheet(title='Connections', rows=100, cols=10)
            sheet.append_row(['Timestamp', 'Test', 'Data', 'From', 'API'])
        
        # Write test data
        test_row = [datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'TEST', 'ashwink', 'lihi.segev', 'strong', 'API Test']
        sheet.append_row(test_row)
        
        return jsonify({
            'success': True,
            'message': 'Test write successful!',
            'sheet_url': f"{GOOGLE_SHEETS_CONFIG['spreadsheet_url']}&gid={sheet.id}"
        })
        
    except Exception as e:
        logger.error(f"Test write failed: {e}")
        return jsonify({
            'success': False, 
            'error': str(e)
        }), 500


def get_connections_data(employee_ldap):
    """Get actual organizational connections and hierarchy for an employee, including those from Google Sheets - INTERNAL VERSION"""
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
            declared_connections = [
                {
                    'qtLdap': rec.get('QT Employee LDAP'),
                    'connectionStrength': rec.get('Connection Strength', '').lower(),
                    'declaredBy': rec.get('Declared By'),
                    'timestamp': rec.get('Timestamp'),
                    'notes': rec.get('Notes'),
                    'source': 'Google Sheets'
                }
                for rec in records
                if rec.get('Google Employee LDAP') == employee_ldap
            ]
            logger.debug(f"✅ Found {len(declared_connections)} declared connections for {employee_ldap} from cache.")
            connections.extend(declared_connections)
        except Exception as e:
            logger.warning(f"⚠️ Could not load declared connections from cache: {e}")

        # --- 2. Add connections to QT team members (Olenick employees) through manager chain (existing logic) ---
        # This part can be kept if you want to infer connections based on hierarchy *in addition* to declared ones
        # Ensure no duplicates if a connection is both declared and inferred
        existing_qt_ldaps = {conn['qtLdap'] for conn in connections}

        for qt_emp in core_team:  # Iterate through all core_team, not just first 5
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
        # If employee has no direct/declared connections, check if their direct reports have connections
        declared_connections_count = len([c for c in connections if c.get('source') == 'Google Sheets'])
        if declared_connections_count == 0 and hierarchy and hierarchy['reportees']:
            logger.info(f"No direct connections found for {employee_ldap}, checking transitive connections through {len(hierarchy['reportees'])} direct reports...")

            transitive_connections = []
            checked_reports = 0
            max_reports_to_check = 10  # Limit to avoid performance issues

            for reportee in hierarchy['reportees'][:max_reports_to_check]:
                reportee_ldap = reportee.get('ldap')
                if reportee_ldap:
                    # Get connections for this direct report (recursive call, but limited)
                    reportee_connections = get_connections_data(reportee_ldap)
                    checked_reports += 1

                    # Add transitive connections through this reportee
                    for conn in reportee_connections:
                        if conn.get('source') == 'Google Sheets':  # Only include declared connections
                            transitive_connections.append({
                                'qtLdap': conn['qtLdap'],
                                'connectionStrength': conn.get('connectionStrength', 'weak'),  # Inherit original strength
                                'declaredBy': conn.get('declaredBy', ''),
                                'timestamp': conn.get('timestamp', ''),
                                'notes': f"Via {reportee.get('name', reportee_ldap)} → {conn.get('notes', '')}",
                                'source': 'Transitive',
                                'intermediatePerson': {
                                    'ldap': reportee_ldap,
                                    'name': reportee.get('name'),
                                    'email': reportee.get('email')
                                }
                            })

            if transitive_connections:
                logger.info(f"Found {len(transitive_connections)} transitive connections for {employee_ldap} through {checked_reports} direct reports")
                connections.extend(transitive_connections)

        # --- 4. CROSS-ORGANIZATIONAL NETWORK EXPANSION ---
        # If we have QT connections to Google employees, leverage Google's internal network
        # to find potential paths to ANY Google employee through internal connections
        existing_qt_connections = [conn for conn in connections if conn.get('source') == 'Google Sheets']

        if len(existing_qt_connections) > 0:
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

        logger.debug(f"Returning {len(connections)} total connections for {employee_ldap}")
        return connections

    except Exception as e:
        # Handle quota exceeded errors silently - don't spam logs
        if "Quota exceeded" in str(e) or "429" in str(e):
            # Return empty connections for quota exceeded (graceful degradation)
            return []
        logger.error(f"Connections error for {employee_ldap}: {e}")
        return []

@app.route('/api/connections/<employee_ldap>')
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

@app.route('/api/health')
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

@app.route('/api/debug-google-sheets')
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
                'debug.qt@olenick.com',
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

@app.route('/api/read-connections-sheet')
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


@app.route('/api/debug-employees-data')
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
        """Write a single connection to the Google Sheet"""
        try:
            connections_sheet = self.get_or_create_connections_sheet()
            if not connections_sheet:
                return False
            
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
                    'email': f"{qt_employee_ldap}@olenick.com",
                    'department': 'QT Team'
                }
            
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
                f"Connection declared via Qonnect app"
            ]
            
            # Write to sheet
            connections_sheet.append_row(row_data)
            logger.debug(f"✅ Successfully wrote connection: {google_emp.get('name')} <-> {qt_emp.get('name')} ({connection_strength})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error writing connection to sheet: {e}")
            return False
    
    def write_batch_connections_to_sheet(self, google_employee_ldap, connections_dict, declared_by="System"):
        """FIXED: Write multiple connections to the Google Sheet"""
        try:
            logger.debug(f"📝 Starting batch write: {len(connections_dict)} connections for {google_employee_ldap}")
            
            connections_sheet = self.get_or_create_connections_sheet()
            if not connections_sheet:
                return False, "Could not access or create Connections sheet"
            
            logger.debug("✅ Connections sheet accessible")
            
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
            rows_to_add = []
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
                        'email': f"{qt_ldap}@olenick.com",
                        'department': 'QT Team'
                    }
                
                logger.debug(f"    📋 QT employee: {qt_emp.get('name')}")
                
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
                    strength.title(),
                    declared_by,
                    f"Batch connection declared via Qonnect app"
                ]
                
                rows_to_add.append(row_data)
                successful_connections.append(f"{qt_emp.get('name')} ({strength})")
                logger.debug(f"    ✅ Row prepared for {qt_emp.get('name')}")
            
            if rows_to_add:
                logger.debug(f"📤 Writing {len(rows_to_add)} rows to Google Sheets...")
                try:
                    # Write all rows at once for better performance
                    connections_sheet.append_rows(rows_to_add)
                    logger.debug(f"🎉 Successfully wrote {len(rows_to_add)} connections to Google Sheets!")
                    
                    success_message = f"Successfully saved {len(rows_to_add)} connections to Google Sheets 'Connections' tab: {', '.join(successful_connections)}"
                    return True, success_message
                    
                except Exception as write_error:
                    error_msg = str(write_error)
                    logger.error(f"❌ Write operation failed: {error_msg}")
                    
                    if "permission" in error_msg.lower():
                        return False, "Permission denied - service account needs Editor access to the Google Sheet"
                    elif "quota" in error_msg.lower():
                        return False, "API quota exceeded - please wait a moment and try again"
                    elif "not found" in error_msg.lower():
                        return False, "Spreadsheet or sheet not found - check your configuration"
                    else:
                        return False, f"Write failed: {error_msg}"
            else:
                return False, "No valid connections to save"
                
        except Exception as e:
            logger.error(f"❌ Unexpected error in batch write: {e}")
            return False, f"Unexpected error: {str(e)}"

# Initialize the writer
sheet_writer = OptimizedGoogleSheetsWriter(GOOGLE_SHEETS_CONFIG)

# Enhanced API endpoint for batch connection updates
@app.route('/api/batch-update-connections', methods=['POST'])
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

# New endpoint to view connections from Google Sheets
@app.route('/api/connections-from-sheets')
def get_connections_from_sheets():
    """Get all connections from the Google Sheets Connections tab (cached)"""
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
@app.route('/api/connection-stats')
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

if __name__ == '__main__':
    print("🚀 Qonnect - Starting on http://localhost:8080")
    
    app.run(debug=True, port=8080, threaded=True)