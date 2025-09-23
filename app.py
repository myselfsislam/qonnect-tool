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

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
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
    'max_employees': 100000,
    'progress_interval': 1000,
    'memory_cleanup_interval': 5000
}

# Global data storage - Optimized
employees_data = []
google_employees = []
core_team = []
processing_stats = {}
last_sync_time = None

@lru_cache(maxsize=1000)
def get_employee_by_ldap(ldap: str):
    """Cached employee lookup by LDAP"""
    return next((emp for emp in employees_data if emp.get('ldap') == ldap), None)

class OptimizedGoogleSheetsConnector:
    """Optimized Google Sheets connector with better performance"""
    
    def __init__(self, config):
        self.config = config
        self.client = None
        self.spreadsheet = None
        
    def authenticate(self):
        """Optimized authentication with error handling"""
        try:
            logger.info("Authenticating with Google Sheets API...")
            
            if os.path.exists(self.config['service_account_file']):
                logger.info(f"Using service account file: {self.config['service_account_file']}")
                creds = Credentials.from_service_account_file(
                    self.config['service_account_file'],
                    scopes=self.config['scopes']
                )
                self.client = gspread.authorize(creds)
                logger.info("Authentication successful")
                return True
                
            elif 'GOOGLE_SERVICE_ACCOUNT_JSON' in os.environ:
                logger.info("Using service account from environment variable")
                service_account_info = json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON'])
                creds = Credentials.from_service_account_info(
                    service_account_info,
                    scopes=self.config['scopes']
                )
                self.client = gspread.authorize(creds)
                logger.info("Authentication successful with environment credentials")
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
        
        logger.info("Created 'credentials_template.json' template")
    
    def connect_to_spreadsheet(self):
        """Optimized spreadsheet connection"""
        try:
            logger.info(f"Connecting to spreadsheet: {self.config['spreadsheet_id']}")
            
            if not self.client:
                if not self.authenticate():
                    return False
            
            self.spreadsheet = self.client.open_by_key(self.config['spreadsheet_id'])
            logger.info(f"Connected to: {self.spreadsheet.title}")
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
            logger.info(f"Getting data from sheet: {sheet_name}")
            
            try:
                worksheet = self.spreadsheet.worksheet(sheet_name)
            except:
                worksheet = self.spreadsheet.sheet1
                logger.warning(f"Sheet '{sheet_name}' not found, using first sheet: {worksheet.title}")
            
            # Get all values at once (more efficient than row-by-row)
            all_values = worksheet.get_all_values()
            
            if not all_values or len(all_values) < 2:
                logger.error("No data found or insufficient data")
                return None
            
            # Safety check for large datasets
            if len(all_values) > self.config['max_employees']:
                logger.warning(f"Large dataset detected ({len(all_values)} rows), limiting to {self.config['max_employees']}")
                all_values = all_values[:self.config['max_employees']]
            
            logger.info(f"Retrieved {len(all_values)} rows from sheet")
            
            # Create DataFrame more efficiently
            headers = all_values[0]
            data_rows = all_values[1:]
            
            # Filter out completely empty rows upfront
            data_rows = [row for row in data_rows if any(cell.strip() for cell in row)]
            
            if not data_rows:
                logger.error("No valid data rows found")
                return None
            
            df = pd.DataFrame(data_rows, columns=headers)
            logger.info(f"Created DataFrame: {len(df)} rows, {len(df.columns)} columns")
            
            return df
                
        except Exception as e:
            logger.error(f"Error getting sheet data: {e}")
            return None
    
    def create_sample_data(self):
        """Create sample data based on actual Google Sheets structure"""
        logger.info("Creating sample data matching Google Sheets structure...")
        
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
            ["Lihi Segev", "Engineering Manager", "Engineering", "Israel", "lihi.segev", "", "", ""],
            ["Abhijeet Bagade", "Product Manager", "Product", "India", "abhijeet.bagade", "", "", ""],
            ["Omri Nissim", "Senior Developer", "Engineering", "Israel", "omri.nissim", "", "", ""],
            ["Kobi Kol", "Operations Manager", "Operations", "Israel", "kobi.kol", "", "", ""],
            ["Jillian OrRico", "Sales Director", "Sales", "USA", "jillian.orrico", "", "", ""],
            ["Michael Bush", "Marketing Manager", "Marketing", "USA", "michael.bush", "", "", ""],
            ["Mayank Arya", "Technical Lead", "Engineering", "India", "mayank.arya", "", "", ""],
        ]
        
        df = pd.DataFrame(sample_data[1:], columns=sample_data[0])
        logger.info(f"Created sample data matching Google Sheets: {len(df)} rows")
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
        
        logger.info(f"Analyzing {len(columns)} columns: {columns}")
        
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
        
        logger.info(f"Column mapping detected: {mapping}")
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
            
            # Generate avatar if not provided
            if not avatar_url or avatar_url in ['Unknown', '', 'N/A']:
                avatar_url = f"https://i.pravatar.cc/150?u={emp_id}"
            
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
            logger.info("Starting optimized Google Sheets processing...")
            
            # Get data with optimizations
            df = self.connector.get_sheet_data_optimized()
            
            if df is None:
                logger.warning("Could not access Google Sheets - using sample data")
                df = self.connector.create_sample_data()
                data_source = 'Sample Data (Google Sheets failed)'
            else:
                data_source = 'Google Sheets'
            
            # Optimized DataFrame cleaning
            logger.info("Cleaning DataFrame...")
            original_rows = len(df)
            
            # Remove empty rows more efficiently
            df = df.dropna(how='all')
            # Fix: Apply string operations correctly
            df = df[~df.apply(lambda row: all(str(cell).strip() == '' for cell in row), axis=1)]
            
            logger.info(f"Cleaned DataFrame: {len(df)} rows (removed {original_rows - len(df)} empty rows)")
            
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
            
            logger.info(f"Processing {len(df)} rows in {total_batches} batches of {batch_size}")
            
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
                
                # Progress logging (less frequent)
                if stats['processed_rows'] % self.config['progress_interval'] == 0:
                    logger.info(f"Processed {stats['processed_rows']:,} profiles...")
                
                # Memory cleanup every few batches
                if batch_num % 10 == 0:
                    gc.collect()
            
            # Final cleanup
            del df
            gc.collect()
            
            stats['processing_time'] = (datetime.now() - start_time).total_seconds()
            
            logger.info("Optimized processing complete!")
            logger.info(f"Total processed: {len(employees):,} profiles")
            logger.info(f"Google employees: {stats['google_employees']:,}")
            logger.info(f"Olenick employees: {stats['olenick_employees']:,}")
            logger.info(f"Other employees: {stats['other_employees']:,}")
            logger.info(f"Processing time: {stats['processing_time']:.2f} seconds")
            
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
        logger.info("Loading Google Sheets data with optimizations...")
        
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
        
        logger.info(f"Successfully loaded employee data:")
        logger.info(f"Total: {len(employees_data):,}")
        logger.info(f"Google: {len(google_employees):,}")
        logger.info(f"Olenick: {len(olenick_employees):,}")
        logger.info(f"Departments: {departments}")
        logger.info(f"Locations: {locations}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error loading optimized data: {e}")
        return False

def build_organizational_hierarchy():
    """Build proper manager-reportee relationships from Google Sheets data"""
    try:
        logger.info("Building organizational hierarchy from manager email relationships...")
        
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
        
        logger.info(f"Built hierarchy: {managers_count} managers with {total_reportees} total reportees")
        
        # Log some examples for debugging
        for emp in employees_data[:5]:
            if emp.get('reportees'):
                logger.info(f"Manager: {emp['name']} has {len(emp['reportees'])} reportees")
        
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
    query = request.args.get('q', '').lower().strip()
    
    if len(query) < 2:
        return jsonify([])
    
    try:
        filtered = []
        max_results = 25
        
        for emp in employees_data:
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
                # Get hierarchy information for this employee
                hierarchy = get_employee_hierarchy(emp['ldap'])
                
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
                    # Add hierarchy info for the search results
                    'reportees_count': len(hierarchy['reportees']) if hierarchy else 0,
                    'manager_chain_length': len(hierarchy['manager_chain']) if hierarchy else 0,
                    'has_reportees': len(hierarchy['reportees']) > 0 if hierarchy else False
                }
                filtered.append(emp_copy)
        
        # Sort by score
        filtered.sort(key=lambda x: x['_search_score'], reverse=True)
        return jsonify(filtered)
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify([])

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
def batch_update_connections():
    """Optimized connection updates"""
    try:
        data = request.get_json()
        google_ldap = data.get('googleLdap')
        connections = data.get('connections', {})
        
        # FIXED: Actually update the connections in the employee data
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
                else:
                    # Add new connection
                    qt_employee = get_employee_by_ldap(qt_ldap)
                    if qt_employee:
                        google_employee['connections'].append({
                            'ldap': qt_ldap,
                            'name': qt_employee.get('name'),
                            'connectionStrength': strength
                        })
        
        return jsonify({
            'success': True,
            'updated_count': len(connections),
            'message': 'Connections updated successfully',
            'google_employee': google_ldap
        })
        
    except Exception as e:
        logger.error(f"Connection update error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/connections/<employee_ldap>')
def get_connections(employee_ldap):
    """Get actual organizational connections and hierarchy for an employee"""
    try:
        hierarchy = get_employee_hierarchy(employee_ldap)
        
        if not hierarchy:
            return jsonify([])
        
        connections = []
        
        # Add connections to QT team members (Olenick employees) through manager chain
        for qt_emp in core_team[:5]:  # Limit to first 5 for performance
            if qt_emp.get('ldap') != employee_ldap:
                # Create connection path through organizational hierarchy
                path = [qt_emp.get('ldap')]
                
                # If the QT employee is in the manager chain, create direct path
                manager_ldaps = [mgr.get('ldap') for mgr in hierarchy['manager_chain']]
                if qt_emp.get('ldap') in manager_ldaps:
                    path.append(employee_ldap)
                    strength = 'strong'  # Direct reporting relationship
                else:
                    # Create path through common manager or department
                    if qt_emp.get('department') == hierarchy['employee'].get('department'):
                        path.append(employee_ldap)
                        strength = 'medium'  # Same department
                    else:
                        # Indirect connection
                        if hierarchy['manager_chain']:
                            path.append(hierarchy['manager_chain'][0].get('ldap'))
                        path.append(employee_ldap)
                        strength = 'weak'  # Indirect connection
                
                connections.append({
                    'qtLdap': qt_emp.get('ldap'),
                    'connectionStrength': strength,
                    'path': path
                })
        
        return jsonify(connections)
        
    except Exception as e:
        logger.error(f"Connections error for {employee_ldap}: {e}")
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
def debug_google_sheets():
    """Debug endpoint to test Google Sheets connectivity and permissions"""
    try:
        # Test if sheet_writer exists
        if 'sheet_writer' not in globals():
            return jsonify({
                'status': 'error',
                'issue': 'Google Sheets writer not initialized',
                'fix': 'Add the OptimizedGoogleSheetsWriter class and initialize sheet_writer'
            }), 500
        
        # Test basic authentication
        if not sheet_writer.connector.client:
            if not sheet_writer.connector.authenticate():
                return jsonify({
                    'status': 'error',
                    'issue': 'Authentication failed',
                    'fix': 'Check your credentials.json file and ensure it exists'
                }), 500
        
        # Test spreadsheet connection
        if not sheet_writer.connector.connect_to_spreadsheet():
            return jsonify({
                'status': 'error', 
                'issue': 'Cannot connect to spreadsheet',
                'fix': 'Verify spreadsheet ID and service account permissions'
            }), 500
        
        # Test creating/accessing Connections sheet
        try:
            connections_sheet = sheet_writer.get_or_create_connections_sheet()
            if not connections_sheet:
                return jsonify({
                    'status': 'error',
                    'issue': 'Cannot create or access Connections sheet',
                    'fix': 'Service account needs Editor permissions, not just Viewer'
                }), 500
        except Exception as e:
            return jsonify({
                'status': 'error',
                'issue': f'Connections sheet error: {str(e)}',
                'fix': 'Ensure service account has Editor permissions on the Google Sheet'
            }), 500
        
        # Test write capability with a simple test row (skip employee validation for debug)
        try:
            # Write a simple test row directly to the sheet
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            test_row = [
                timestamp,
                'debug.test',
                'Debug Test User',
                'debug.test@google.com',
                'debug.qt',
                'Debug QT User',
                'debug.qt@qualitest.com',
                'Medium',
                'Debug System',
                'Debug connectivity test'
            ]
            
            connections_sheet.append_row(test_row)
            logger.info("Successfully wrote debug test row to Google Sheets")
            
            return jsonify({
                'status': 'success',
                'message': 'Google Sheets integration is working correctly!',
                'details': {
                    'authentication': 'OK',
                    'spreadsheet_access': 'OK', 
                    'connections_sheet': 'OK',
                    'write_permissions': 'OK',
                    'test_record_written': 'Yes',
                    'sheet_id': connections_sheet.id,
                    'sheet_title': connections_sheet.title
                }
            })
                
        except Exception as e:
            return jsonify({
                'status': 'error',
                'issue': f'Write test failed: {str(e)}',
                'fix': 'Ensure service account has Editor permissions and proper API access'
            }), 500
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'issue': f'Unexpected error: {str(e)}',
            'fix': 'Check logs for detailed error information'
        }), 500

class OptimizedGoogleSheetsWriter:
    """Enhanced connector that can both read and write to Google Sheets"""
    
    def __init__(self, config):
        self.config = config
        self.connector = OptimizedGoogleSheetsConnector(config)
        
    def get_or_create_connections_sheet(self):
        """Get the Connections sheet or create it if it doesn't exist"""
        try:
            if not self.connector.spreadsheet:
                if not self.connector.connect_to_spreadsheet():
                    return None
            
            # Try to get existing Connections sheet
            try:
                connections_sheet = self.connector.spreadsheet.worksheet('Connections')
                logger.info("Found existing 'Connections' sheet")
                return connections_sheet
            except:
                logger.info("'Connections' sheet not found, creating new one...")
                
                # Create new sheet
                connections_sheet = self.connector.spreadsheet.add_worksheet(
                    title='Connections', 
                    rows=1000, 
                    cols=10
                )
                
                # Add headers
                headers = [
                    'Timestamp',
                    'Google Employee LDAP',
                    'Google Employee Name', 
                    'Google Employee Email',
                    'QT Employee LDAP',
                    'QT Employee Name',
                    'QT Employee Email', 
                    'Connection Strength',
                    'Declared By',
                    'Notes'
                ]
                
                connections_sheet.append_row(headers)
                logger.info("Created new 'Connections' sheet with headers")
                return connections_sheet
                
        except Exception as e:
            logger.error(f"Error getting/creating Connections sheet: {e}")
            return None
    
    def write_connection_to_sheet(self, google_employee_ldap, qt_employee_ldap, connection_strength, declared_by="System"):
        """Write a single connection to the Google Sheet"""
        try:
            connections_sheet = self.get_or_create_connections_sheet()
            if not connections_sheet:
                return False
            
            # Get employee details
            google_emp = get_employee_by_ldap(google_employee_ldap)
            qt_emp = next((emp for emp in core_team if emp.get('ldap') == qt_employee_ldap), None)
            
            if not google_emp or not qt_emp:
                logger.error(f"Employee not found: Google={google_employee_ldap}, QT={qt_employee_ldap}")
                return False
            
            # Prepare row data
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            row_data = [
                timestamp,
                google_emp.get('ldap', ''),
                google_emp.get('name', ''),
                google_emp.get('email', ''),
                qt_emp.get('ldap', ''),
                qt_emp.get('name', ''),
                qt_emp.get('email', ''),
                connection_strength.title(),
                declared_by,
                f"Connection declared via Qonnect app"
            ]
            
            # Write to sheet
            connections_sheet.append_row(row_data)
            logger.info(f"Successfully wrote connection: {google_emp.get('name')} <-> {qt_emp.get('name')} ({connection_strength})")
            return True
            
        except Exception as e:
            logger.error(f"Error writing connection to sheet: {e}")
            return False
    
    def write_batch_connections_to_sheet(self, google_employee_ldap, connections_dict, declared_by="System"):
        """Write multiple connections to the Google Sheet"""
        try:
            connections_sheet = self.get_or_create_connections_sheet()
            if not connections_sheet:
                return False, "Could not access Connections sheet"
            
            google_emp = get_employee_by_ldap(google_employee_ldap)
            if not google_emp:
                return False, f"Google employee {google_employee_ldap} not found"
            
            # Prepare batch data
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            rows_to_add = []
            successful_connections = []
            
            for qt_ldap, strength in connections_dict.items():
                qt_emp = next((emp for emp in core_team if emp.get('ldap') == qt_ldap), None)
                if qt_emp:
                    row_data = [
                        timestamp,
                        google_emp.get('ldap', ''),
                        google_emp.get('name', ''),
                        google_emp.get('email', ''),
                        qt_emp.get('ldap', ''),
                        qt_emp.get('name', ''),
                        qt_emp.get('email', ''),
                        strength.title(),
                        declared_by,
                        f"Batch connection declared via Qonnect app"
                    ]
                    rows_to_add.append(row_data)
                    successful_connections.append(f"{qt_emp.get('name')} ({strength})")
            
            if rows_to_add:
                # Write all rows at once for better performance
                connections_sheet.append_rows(rows_to_add)
                logger.info(f"Successfully wrote {len(rows_to_add)} connections for {google_emp.get('name')}")
                return True, f"Successfully saved {len(rows_to_add)} connections: {', '.join(successful_connections)}"
            else:
                return False, "No valid connections to save"
                
        except Exception as e:
            logger.error(f"Error writing batch connections: {e}")
            return False, f"Error saving to Google Sheets: {str(e)}"

# Initialize the writer
sheet_writer = OptimizedGoogleSheetsWriter(GOOGLE_SHEETS_CONFIG)

# Enhanced API endpoint for batch connection updates
@app.route('/api/batch-update-connections', methods=['POST'])
def batch_update_connections_enhanced():
    """Enhanced connection updates that write to Google Sheets"""
    try:
        data = request.get_json()
        google_ldap = data.get('googleLdap')
        connections = data.get('connections', {})
        declared_by = data.get('declaredBy', 'Qonnect User')
        
        if not google_ldap or not connections:
            return jsonify({'success': False, 'error': 'Missing required data'}), 400
        
        # Update in-memory data (existing functionality)
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
                else:
                    # Add new connection
                    qt_employee = next((emp for emp in core_team if emp.get('ldap') == qt_ldap), None)
                    if qt_employee:
                        google_employee['connections'].append({
                            'ldap': qt_ldap,
                            'name': qt_employee.get('name'),
                            'connectionStrength': strength
                        })
        
        # Write to Google Sheets
        try:
            success, message = sheet_writer.write_batch_connections_to_sheet(
                google_ldap, 
                connections, 
                declared_by
            )
            
            if success:
                return jsonify({
                    'success': True,
                    'updated_count': len(connections),
                    'message': message,
                    'google_employee': google_ldap,
                    'written_to_sheets': True,
                    'sheets_url': f"{GOOGLE_SHEETS_CONFIG['spreadsheet_url']}&gid=CONNECTIONS_SHEET_ID"
                })
            else:
                # Even if sheets write fails, return success for in-memory update
                return jsonify({
                    'success': True,
                    'updated_count': len(connections),
                    'message': f'Connections updated in memory. Google Sheets error: {message}',
                    'google_employee': google_ldap,
                    'written_to_sheets': False,
                    'sheets_error': message
                })
                
        except Exception as e:
            logger.error(f"Google Sheets write error: {e}")
            # Still return success for in-memory update
            return jsonify({
                'success': True,
                'updated_count': len(connections),
                'message': f'Connections updated in memory. Google Sheets unavailable: {str(e)}',
                'google_employee': google_ldap,
                'written_to_sheets': False,
                'sheets_error': str(e)
            })
        
    except Exception as e:
        logger.error(f"Connection update error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# New endpoint to view connections from Google Sheets
@app.route('/api/connections-from-sheets')
def get_connections_from_sheets():
    """Get all connections from the Google Sheets Connections tab"""
    try:
        connections_sheet = sheet_writer.get_or_create_connections_sheet()
        if not connections_sheet:
            return jsonify({'error': 'Could not access Connections sheet'}), 500
        
        # Get all records
        records = connections_sheet.get_all_records()
        
        return jsonify({
            'connections': records,
            'total_count': len(records),
            'sheet_url': f"{GOOGLE_SHEETS_CONFIG['spreadsheet_url']}&gid={connections_sheet.id}"
        })
        
    except Exception as e:
        logger.error(f"Error getting connections from sheets: {e}")
        return jsonify({'error': str(e)}), 500

# New endpoint to get connection statistics
@app.route('/api/connection-stats')
def get_connection_stats():
    """Get statistics about declared connections"""
    try:
        connections_sheet = sheet_writer.get_or_create_connections_sheet()
        if not connections_sheet:
            return jsonify({'error': 'Could not access Connections sheet'}), 500
        
        records = connections_sheet.get_all_records()
        
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
    print("🚀 Qonnect - FIXED Google Sheets System")
    print("=" * 60)
    print("🔧 CRITICAL FIXES APPLIED:")
    print("   ✅ FIXED search to find actual employees (not their reportees)")
    print("   ✅ FIXED hierarchy building with manager email relationships")
    print("   ✅ Enhanced sample data with proper organizational structure")
    print("   ✅ Fixed all API endpoints for proper data flow")
    print("   ✅ Improved error handling and data validation")
    print()
    print("🎯 OPTIMIZATIONS ENABLED:")
    print("   ✅ Batch processing for large datasets")
    print("   ✅ Memory management and garbage collection")
    print("   ✅ Cached employee lookups (LRU cache)")
    print("   ✅ Optimized API endpoints with reduced payloads")
    print("   ✅ Efficient data structures and algorithms")
    print()
    print("📊 HIERARCHY STRUCTURE:")
    print("   Manager Email → Reports to this manager")
    print("   Search 'ashwink' → Returns ashwink (not his reports)")
    print("   Click ashwink → Shows hierarchy with his reportees")
    print()
    print("📄 Google Sheets Configuration:")
    print(f"   Spreadsheet: {GOOGLE_SHEETS_CONFIG['spreadsheet_id']}")
    print(f"   Credentials: {'✅ Found' if os.path.exists(GOOGLE_SHEETS_CONFIG['service_account_file']) else '❌ Not found'}")
    print()
    
    # Load data with optimizations
    print("📊 Loading data with optimizations...")
    success = load_google_sheets_data_optimized()
    
    if success:
        print("🎉 Fixed loading complete!")
        print(f"   📊 Total employees: {len(employees_data):,}")
        print(f"   📊 Google employees: {len(google_employees):,}")
        print(f"   📊 Processing time: {processing_stats.get('processing_time', 0):.2f}s")
        print(f"   📊 Processing rate: {len(employees_data) / max(processing_stats.get('processing_time', 1), 0.1):,.0f} records/sec")
        
        # Test hierarchy for ashwink
        ashwin_hierarchy = get_employee_hierarchy('ashwink')
        if ashwin_hierarchy:
            print(f"   📊 Ashwin has {len(ashwin_hierarchy['reportees'])} direct reports")
    else:
        print("⚠️ Using sample data for testing")
    
    print(f"\n🌐 Starting FIXED Flask app on http://localhost:8080")
    print("🔧 Key endpoints:")
    print("   • GET  /                         - Dashboard")
    print("   • GET  /search                   - FIXED hierarchy search")
    print("   • GET  /declare                  - Declare connections")
    print("   • GET  /api/search-employees     - FIXED employee search")
    print("   • GET  /api/hierarchy/<ldap>     - Get employee hierarchy")
    
    app.run(debug=True, port=8080, threaded=True)