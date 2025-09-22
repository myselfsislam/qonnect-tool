from flask import Flask, jsonify, request, render_template_string, send_from_directory
from flask_cors import CORS
import pandas as pd
import json
import os
import requests
from datetime import datetime, timedelta
import re
from typing import Dict, List, Optional, Tuple
import msal
import io
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

# Updated SharePoint Configuration with NEW file link
SHAREPOINT_CONFIG = {
    # Base SharePoint Details
    'site_url': 'https://olenick.sharepoint.com',
    'site_path': '/sites/Web-App-Demo',
    'organization_domain': 'olenick.com',  # Used for tenant discovery
    
    # Authentication Options (Multiple approaches - no tenant_id required)
    'tenant_id': None,  # Will be discovered automatically
    'client_id': '6d372aab-be8a-47ee-ac97-1fd2d606540f',  # Optional - only if you have Azure app
    'client_secret': 'c56ecb77-fe3b-4b0e-aaa2-7e974e962f33',  # Optional
    'username': 'demo.testaccount@olenick.com',  # Your actual Olenick email
    'password': 'L.872265176890uz',
    
    # Updated File Details for NEW file
    'document_id': 'DEC1873C-224C-431C-AF5F-06A04AF48645',  # NEW document ID
    'file_name': 'Profiles.xlsx',  # NEW filename
    'full_sharepoint_url': 'https://olenick.sharepoint.com/:x:/r/sites/Web-App-Demo/_layouts/15/Doc.aspx?sourcedoc=%7BDEC1873C-224C-431C-AF5F-06A04AF48645%7D&file=Profiles.xlsx&action=default&mobileredirect=true'
}

# Global data storage
employees_data = []
google_employees = []
core_team = []
processing_stats = {}
last_sync_time = None
discovered_tenant_id = None

class TenantDiscovery:
    """Discover tenant ID automatically using various methods"""
    
    @staticmethod
    def discover_tenant_from_domain(domain):
        """Method 1: Discover tenant ID from organization domain"""
        try:
            print(f"🔍 Discovering tenant ID for domain: {domain}")
            
            # Use OpenID Connect discovery endpoint
            discovery_url = f"https://login.microsoftonline.com/{domain}/.well-known/openid_configuration"
            response = requests.get(discovery_url, timeout=10)
            
            if response.status_code == 200:
                config = response.json()
                issuer = config.get('issuer', '')
                
                # Extract tenant ID from issuer URL
                # Format: https://login.microsoftonline.com/{tenant_id}/v2.0
                if '/v2.0' in issuer:
                    tenant_id = issuer.split('/')[-2]
                    print(f"✅ Discovered tenant ID: {tenant_id}")
                    return tenant_id
            
            return None
            
        except Exception as e:
            print(f"❌ Domain discovery failed: {e}")
            return None
    
    @staticmethod
    def discover_tenant_from_sharepoint_url(sharepoint_url):
        """Method 2: Discover tenant from SharePoint URL structure"""
        try:
            print(f"🔍 Discovering tenant from SharePoint URL...")
            
            # Extract organization name from SharePoint URL
            # https://olenick.sharepoint.com -> olenick
            parsed_url = urlparse(sharepoint_url)
            hostname = parsed_url.hostname
            
            if '.sharepoint.com' in hostname:
                org_name = hostname.split('.sharepoint.com')[0]
                
                # Try common tenant patterns
                possible_domains = [
                    f"{org_name}.com",
                    f"{org_name}.org", 
                    f"{org_name}.net",
                    f"{org_name}.onmicrosoft.com"
                ]
                
                for domain in possible_domains:
                    tenant_id = TenantDiscovery.discover_tenant_from_domain(domain)
                    if tenant_id:
                        return tenant_id
            
            return None
            
        except Exception as e:
            print(f"❌ SharePoint URL discovery failed: {e}")
            return None
    
    @staticmethod
    def discover_tenant_from_username(username):
        """Method 3: Discover tenant from user's email domain"""
        try:
            if '@' in username:
                domain = username.split('@')[1]
                print(f"🔍 Discovering tenant from email domain: {domain}")
                return TenantDiscovery.discover_tenant_from_domain(domain)
            
            return None
            
        except Exception as e:
            print(f"❌ Username discovery failed: {e}")
            return None

class NoTenantAuthenticator:
    """Handle SharePoint authentication WITHOUT requiring tenant_id"""
    
    def __init__(self, config):
        self.config = config
        self.access_token = None
        self.token_expiry = None
        self.discovered_tenant = None
        
    def discover_tenant_id(self):
        """Automatically discover tenant ID"""
        global discovered_tenant_id
        
        if discovered_tenant_id:
            return discovered_tenant_id
        
        print("🔍 Tenant ID not provided - attempting automatic discovery...")
        
        # Method 1: Try from organization domain
        if self.config.get('organization_domain'):
            tenant_id = TenantDiscovery.discover_tenant_from_domain(self.config['organization_domain'])
            if tenant_id:
                discovered_tenant_id = tenant_id
                return tenant_id
        
        # Method 2: Try from SharePoint URL
        tenant_id = TenantDiscovery.discover_tenant_from_sharepoint_url(self.config['site_url'])
        if tenant_id:
            discovered_tenant_id = tenant_id
            return tenant_id
        
        # Method 3: Try from username
        if self.config.get('username'):
            tenant_id = TenantDiscovery.discover_tenant_from_username(self.config['username'])
            if tenant_id:
                discovered_tenant_id = tenant_id
                return tenant_id
        
        # Method 4: Use 'common' endpoint as fallback
        print("⚠️ Could not discover tenant ID - using 'common' endpoint")
        discovered_tenant_id = 'common'
        return 'common'
    
    def authenticate_with_username_password(self):
        """Authenticate using username/password without tenant_id"""
        try:
            print("🔐 Authenticating with username/password (no tenant_id required)...")
            
            # Discover tenant
            tenant_id = self.discover_tenant_id()
            if not tenant_id:
                return None
            
            # Create MSAL app with discovered tenant
            authority = f"https://login.microsoftonline.com/{tenant_id}"
            
            # Use a public client application (doesn't require client_secret)
            app = msal.PublicClientApplication(
                client_id="04b07795-8ddb-461a-bbee-02f9e1bf7b46",  # Azure CLI client ID (public)
                authority=authority
            )
            
            # Try Resource Owner Password Credentials (ROPC) flow
            scopes = ["https://graph.microsoft.com/.default"]
            
            result = app.acquire_token_by_username_password(
                username=self.config['username'],
                password=self.config['password'],
                scopes=scopes
            )
            
            if "access_token" in result:
                self.access_token = result["access_token"]
                expires_in = result.get("expires_in", 3600)
                self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 300)
                
                print("✅ Successfully authenticated without tenant_id!")
                return self.access_token
            else:
                print(f"❌ Authentication failed: {result.get('error_description', 'Unknown error')}")
                return None
                
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            return None
    
    def authenticate_device_flow(self):
        """Alternative: Device flow authentication (no tenant_id, no password needed)"""
        try:
            print("🔐 Starting device flow authentication (no tenant_id needed)...")
            
            tenant_id = self.discover_tenant_id() or 'common'
            authority = f"https://login.microsoftonline.com/{tenant_id}"
            
            app = msal.PublicClientApplication(
                client_id="04b07795-8ddb-461a-bbee-02f9e1bf7b46",  # Azure CLI client ID
                authority=authority
            )
            
            scopes = ["https://graph.microsoft.com/.default"]
            
            # Initiate device flow
            flow = app.initiate_device_flow(scopes=scopes)
            
            if "user_code" not in flow:
                raise ValueError("Could not initiate device flow")
            
            print("\n" + "="*60)
            print("🔐 DEVICE AUTHENTICATION REQUIRED")
            print("="*60)
            print(flow["message"])
            print("="*60)
            print("After completing authentication in browser, press Enter...")
            input()
            
            # Complete the flow
            result = app.acquire_token_by_device_flow(flow)
            
            if "access_token" in result:
                self.access_token = result["access_token"]
                expires_in = result.get("expires_in", 3600)
                self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 300)
                
                print("✅ Device flow authentication successful!")
                return self.access_token
            else:
                print(f"❌ Device flow failed: {result.get('error_description')}")
                return None
                
        except Exception as e:
            print(f"❌ Device flow error: {e}")
            return None
    
    def get_access_token(self):
        """Get access token using best available method"""
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.access_token
        
        # Try username/password first
        if self.config.get('username') and self.config.get('password'):
            token = self.authenticate_with_username_password()
            if token:
                return token
        
        # Fallback to device flow if username/password fails
        print("💡 Falling back to device flow authentication...")
        return self.authenticate_device_flow()

class DirectSharePointDownloader:
    """Download SharePoint files without complex Graph API setup"""
    
    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        
    def try_direct_download(self):
        """Method 1: Try direct download with session cookies"""
        try:
            print("📄 Attempting direct SharePoint download...")
            
            # Set user agent to mimic browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }
            
            # Try various direct download URLs for the NEW file
            urls_to_try = [
                self.config['full_sharepoint_url'].replace(':x:/', '/').replace('_layouts/15/Doc.aspx', '_layouts/15/download.aspx'),
                f"{self.config['full_sharepoint_url']}&download=1",
                self.config['full_sharepoint_url'].replace('Doc.aspx', 'download.aspx'),
                # Additional URL patterns for Profiles.xlsx
                f"https://olenick.sharepoint.com/sites/Web-App-Demo/_layouts/15/download.aspx?SourceUrl={self.config['site_url']}/sites/Web-App-Demo/Shared Documents/Profiles.xlsx"
            ]
            
            for url in urls_to_try:
                try:
                    print(f"   📄 Trying: {url[:80]}...")
                    response = self.session.get(url, headers=headers, timeout=30, allow_redirects=True)
                    
                    if response.status_code == 200:
                        content_type = response.headers.get('content-type', '').lower()
                        
                        # Check if we got Excel content
                        if ('excel' in content_type or 
                            'spreadsheet' in content_type or 
                            'application/vnd.openxmlformats' in content_type or
                            len(response.content) > 10000):  # Reasonable file size
                            
                            print(f"   ✅ Direct download successful! ({len(response.content):,} bytes)")
                            return response.content
                        else:
                            print(f"   ❌ Got HTML instead of Excel: {content_type}")
                            
                except requests.exceptions.RequestException as e:
                    print(f"   ❌ Request failed: {e}")
                    continue
            
            return None
            
        except Exception as e:
            print(f"❌ Direct download error: {e}")
            return None

class FlexibleSharePointProcessor:
    """Process SharePoint data with multiple fallback methods"""
    
    def __init__(self, config):
        self.config = config
        self.auth = NoTenantAuthenticator(config)
        self.direct_downloader = DirectSharePointDownloader(config)
        
    def download_file_flexible(self):
        """Try multiple download methods"""
        print("📄 Starting flexible SharePoint file download...")
        
        # Method 1: Try direct download first (fastest)
        print("\n🔥 Method 1: Direct Download")
        file_content = self.direct_downloader.try_direct_download()
        if file_content:
            return file_content
        
        # Method 2: Try authenticated Graph API
        print("\n🔥 Method 2: Authenticated Graph API")
        try:
            token = self.auth.get_access_token()
            if token:
                # Simple Graph API call with discovered tenant
                headers = {'Authorization': f'Bearer {token}'}
                
                # Try to find and download the Profiles.xlsx file
                search_queries = [
                    "https://graph.microsoft.com/v1.0/me/drive/root/search(q='Profiles')",
                    f"https://graph.microsoft.com/v1.0/sites/olenick.sharepoint.com/sites/Web-App-Demo/drive/root/search(q='Profiles')",
                    "https://graph.microsoft.com/v1.0/me/drive/root/search(q='Profiles.xlsx')"
                ]
                
                for query_url in search_queries:
                    try:
                        response = requests.get(query_url, headers=headers)
                        if response.status_code == 200:
                            results = response.json().get('value', [])
                            
                            for item in results:
                                if 'profiles' in item.get('name', '').lower() and item.get('name', '').endswith('.xlsx'):
                                    download_url = item.get('@microsoft.graph.downloadUrl')
                                    if download_url:
                                        file_response = requests.get(download_url)
                                        if file_response.status_code == 200:
                                            print(f"   ✅ Graph API download successful! ({len(file_response.content):,} bytes)")
                                            return file_response.content
                    except:
                        continue
        except Exception as e:
            print(f"   ❌ Graph API method failed: {e}")
        
        # Method 3: Manual instructions
        print("\n🔥 Method 3: Manual Download Required")
        print("=" * 60)
        print("🔧 MANUAL DOWNLOAD REQUIRED")
        print("=" * 60)
        print("Since automatic download failed, please:")
        print(f"1. Open: {self.config['full_sharepoint_url']}")
        print("2. Login with your Olenick credentials")
        print("3. Click 'Download' and save as 'Profiles.xlsx'")
        print("4. Place the file in this project directory")
        print("5. Restart this application")
        print("=" * 60)
        
        return None
    
    def load_manual_file(self):
        """Load manually downloaded file"""
        possible_filenames = [
            'Profiles.xlsx',
            'profiles.xlsx',
            'Profiles.xls',
            'profiles.xls'
        ]
        
        for filename in possible_filenames:
            if os.path.exists(filename):
                try:
                    print(f"📁 Found manual file: {filename}")
                    df = pd.read_excel(filename)
                    print(f"✅ Loaded {len(df):,} rows from manual file")
                    return df
                except Exception as e:
                    print(f"❌ Error reading {filename}: {e}")
                    continue
        
        return None
    
    def process_sharepoint_file(self):
        """Main processing with multiple fallback methods - Enhanced for Profiles data"""
        start_time = datetime.now()
        
        try:
            # Try downloading the file
            file_content = self.download_file_flexible()
            
            if file_content:
                # Process downloaded content
                df = pd.read_excel(io.BytesIO(file_content), engine='openpyxl')
                print(f"✅ Processing {len(df):,} rows from SharePoint")
            else:
                # Try manual file
                df = self.load_manual_file()
                if df is None:
                    raise Exception("Could not download or find the Profiles.xlsx file")
            
            # Enhanced processing for employee profiles data
            employees = []
            stats = {
                'total_rows': len(df),
                'processed_rows': 0,
                'source': 'SharePoint_Profiles',
                'columns_found': list(df.columns)
            }
            
            print(f"📋 Available columns: {list(df.columns)}")
            
            # Smart column mapping based on common profile data patterns
            column_mapping = self.detect_column_mapping(df.columns)
            print(f"📊 Detected column mapping: {column_mapping}")
            
            # Process each row as an employee profile
            for index, row in df.iterrows():
                try:
                    employee = self.extract_employee_data(row, column_mapping, index)
                    if employee:
                        employees.append(employee)
                        stats['processed_rows'] += 1
                    
                    if stats['processed_rows'] % 100 == 0:
                        print(f"   📊 Processed {stats['processed_rows']:,} profiles...")
                        
                except Exception as e:
                    print(f"   ⚠️ Error processing row {index}: {e}")
                    continue
            
            stats['processing_time'] = (datetime.now() - start_time).total_seconds()
            
            print(f"✅ Processing complete: {len(employees):,} employee profiles processed")
            
            return employees, stats
            
        except Exception as e:
            print(f"❌ Error processing file: {e}")
            return None, None
    
    def detect_column_mapping(self, columns):
        """Intelligently detect which columns contain what data"""
        mapping = {}
        columns_lower = [col.lower().strip() for col in columns]
        
        # Common patterns for employee data
        name_patterns = ['name', 'full name', 'employee name', 'first name', 'last name', 'display name']
        email_patterns = ['email', 'mail', 'email address', 'e-mail', 'username', 'login']
        department_patterns = ['department', 'dept', 'division', 'team', 'group', 'unit']
        title_patterns = ['title', 'job title', 'position', 'role', 'designation', 'function']
        company_patterns = ['company', 'organization', 'org', 'employer', 'business unit']
        id_patterns = ['id', 'employee id', 'emp id', 'userid', 'user id', 'ldap', 'samaccountname']
        location_patterns = ['location', 'office', 'site', 'city', 'country', 'region']
        manager_patterns = ['manager', 'supervisor', 'reports to', 'boss']
        
        # Find best matches
        for i, col in enumerate(columns_lower):
            if any(pattern in col for pattern in name_patterns):
                mapping['name'] = columns[i]
            elif any(pattern in col for pattern in email_patterns):
                mapping['email'] = columns[i]
            elif any(pattern in col for pattern in department_patterns):
                mapping['department'] = columns[i]
            elif any(pattern in col for pattern in title_patterns):
                mapping['title'] = columns[i]
            elif any(pattern in col for pattern in company_patterns):
                mapping['company'] = columns[i]
            elif any(pattern in col for pattern in id_patterns):
                mapping['id'] = columns[i]
            elif any(pattern in col for pattern in location_patterns):
                mapping['location'] = columns[i]
            elif any(pattern in col for pattern in manager_patterns):
                mapping['manager'] = columns[i]
        
        # Fallback to first few columns if no patterns matched
        if not mapping.get('name') and len(columns) > 0:
            mapping['name'] = columns[0]
        if not mapping.get('id') and len(columns) > 1:
            mapping['id'] = columns[1]
        if not mapping.get('email') and len(columns) > 2:
            mapping['email'] = columns[2]
            
        return mapping
    
    def extract_employee_data(self, row, column_mapping, index):
        """Extract employee data from a row using intelligent mapping"""
        try:
            # Extract basic info with fallbacks
            name = self.safe_extract(row, column_mapping.get('name'), f'Employee {index}')
            emp_id = self.safe_extract(row, column_mapping.get('id'), f'emp{index}')
            email = self.safe_extract(row, column_mapping.get('email'), f'{emp_id}@olenick.com')
            
            # Extract optional fields
            department = self.safe_extract(row, column_mapping.get('department'), 'Unknown')
            title = self.safe_extract(row, column_mapping.get('title'), 'Employee')
            company = self.safe_extract(row, column_mapping.get('company'), 'OLENICK')
            location = self.safe_extract(row, column_mapping.get('location'), 'Unknown')
            manager = self.safe_extract(row, column_mapping.get('manager'), '')
            
            # Create employee object
            employee = {
                'ldap': str(emp_id).strip(),
                'name': str(name).strip(),
                'email': str(email).strip(),
                'company': str(company).strip(),
                'designation': str(title).strip(),
                'department': str(department).strip(),
                'location': str(location).strip(),
                'manager': str(manager).strip(),
                'organisation': 'Olenick',
                'avatar': f"https://i.pravatar.cc/150?u={emp_id}",
                'company_type': 'Primary' if 'olenick' in str(company).lower() else 'Other'
            }
            
            # Only return if we have meaningful data
            if employee['name'] != f'Employee {index}' or len(str(row.iloc[0]).strip()) > 0:
                return employee
                
            return None
            
        except Exception as e:
            print(f"   ⚠️ Error extracting employee data: {e}")
            return None
    
    def safe_extract(self, row, column_name, default=''):
        """Safely extract data from a pandas row"""
        try:
            if column_name and column_name in row.index:
                value = row[column_name]
                if pd.notna(value) and str(value).strip():
                    return str(value).strip()
            return default
        except:
            return default

# Initialize processor (no tenant_id required)
processor = FlexibleSharePointProcessor(SHAREPOINT_CONFIG)

def load_sharepoint_data_no_tenant():
    """Load SharePoint data WITHOUT tenant_id"""
    global employees_data, google_employees, core_team, processing_stats, last_sync_time
    
    try:
        print("🔍 Loading SharePoint Profiles data WITHOUT tenant_id...")
        
        employees, stats = processor.process_sharepoint_file()
        
        if not employees:
            return False
        
        # Store globally
        employees_data = employees
        processing_stats = stats
        last_sync_time = datetime.now()
        
        # Enhanced categorization for profiles data
        google_employees = [emp for emp in employees if 'google' in emp.get('company', '').lower()]
        olenick_employees = [emp for emp in employees if 'olenick' in emp.get('company', '').lower()]
        
        # Initialize core team (Olenick employees)
        core_team = []
        for emp in olenick_employees[:50]:  # Limit to first 50 for demo
            team_member = emp.copy()
            team_member['connections'] = []
            core_team.append(team_member)
        
        print(f"✅ Successfully loaded {len(employees_data):,} employee profiles")
        print(f"   📊 Olenick employees: {len(olenick_employees):,}")
        print(f"   📊 Google employees: {len(google_employees):,}")
        print(f"   📊 Core team members: {len(core_team):,}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return False

# Flask Routes (updated for profiles data)
@app.route('/')
def index():
    try:
        with open('templates/index.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Qonnect - Employee Profiles</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .status {{ padding: 15px; border-radius: 5px; margin: 10px 0; }}
                .success {{ background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }}
                .info {{ background: #e2f3ff; border: 1px solid #bee5eb; color: #0c5460; }}
                .button {{ background: #2a2559; color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 10px 5px 0 0; }}
                .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
                .stat {{ background: #f8f9fa; padding: 15px; border-radius: 5px; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🔧 Qonnect - Employee Profiles System</h1>
                
                <div class="status success">
                    <strong>📄 File:</strong> Profiles.xlsx<br>
                    <strong>📊 Status:</strong> Loaded {len(employees_data):,} employee profiles<br>
                    <strong>🔍 Tenant Discovery:</strong> {'✅ Found: ' + str(discovered_tenant_id) if discovered_tenant_id else '❌ Not discovered'}
                </div>
                
                <div class="stats">
                    <div class="stat">
                        <h3>{len(employees_data):,}</h3>
                        <p>Total Employees</p>
                    </div>
                    <div class="stat">
                        <h3>{len([e for e in employees_data if 'olenick' in e.get('company', '').lower()]):,}</h3>
                        <p>Olenick Employees</p>
                    </div>
                    <div class="stat">
                        <h3>{len(core_team):,}</h3>
                        <p>Core Team Members</p>
                    </div>
                    <div class="stat">
                        <h3>{len(set([e.get('department', 'Unknown') for e in employees_data])):,}</h3>
                        <p>Departments</p>
                    </div>
                </div>
                
                <div class="info">
                    <strong>📋 SharePoint URL:</strong><br>
                    <small>{SHAREPOINT_CONFIG['full_sharepoint_url'][:100]}...</small>
                </div>
                
                <a href="/api/sync-sharepoint" class="button">🔄 Sync Now</a>
                <a href="/api/stats" class="button">📊 View Stats</a>
                
                <h3>📋 Sample Data</h3>
                <div style="max-height: 300px; overflow-y: auto; background: #f8f9fa; padding: 15px; border-radius: 5px; font-family: monospace; font-size: 12px;">
                    {json.dumps(employees_data[:3], indent=2) if employees_data else "No data loaded"}
                </div>
            </div>
        </body>
        </html>
        '''

@app.route('/api/sync-sharepoint', methods=['POST'])
def sync_sharepoint():
    try:
        success = load_sharepoint_data_no_tenant()
        
        if success:
            return jsonify({'success': False, 'error': 'Sync failed'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/search-employees')
def search_employees():
    """Search employees with enhanced profile data"""
    query = request.args.get('q', '').lower()
    
    if len(query) < 2:
        return jsonify([])
    
    # Enhanced search across multiple fields
    filtered = []
    for emp in employees_data:
        if (query in emp.get('name', '').lower() or 
            query in emp.get('ldap', '').lower() or 
            query in emp.get('email', '').lower() or 
            query in emp.get('department', '').lower() or 
            query in emp.get('designation', '').lower() or 
            query in emp.get('location', '').lower()):
            filtered.append(emp)
            if len(filtered) >= 20:  # Limit results
                break
    
    return jsonify(filtered)

@app.route('/api/search-google-employees')
def search_google_employees():
    """Backward compatibility - search Google employees"""
    return search_employees()

@app.route('/api/employees/<employee_id>')
def get_employee_details(employee_id):
    """Get detailed information for a specific employee"""
    employee = next((emp for emp in employees_data if emp.get('ldap') == employee_id), None)
    
    if not employee:
        return jsonify({'error': 'Employee not found'}), 404
    
    # Add additional context
    employee_details = employee.copy()
    
    # Find colleagues in same department
    colleagues = [emp for emp in employees_data 
                 if emp.get('department') == employee.get('department') 
                 and emp.get('ldap') != employee_id][:5]
    
    employee_details['colleagues'] = colleagues
    employee_details['total_colleagues'] = len([emp for emp in employees_data 
                                               if emp.get('department') == employee.get('department')])
    
    return jsonify(employee_details)

@app.route('/api/departments')
def get_departments():
    """Get list of all departments with employee counts"""
    dept_counts = {}
    
    for emp in employees_data:
        dept = emp.get('department', 'Unknown')
        dept_counts[dept] = dept_counts.get(dept, 0) + 1
    
    departments = [{'name': dept, 'count': count} 
                  for dept, count in sorted(dept_counts.items(), key=lambda x: x[1], reverse=True)]
    
    return jsonify(departments)

@app.route('/api/locations')
def get_locations():
    """Get list of all locations with employee counts"""
    location_counts = {}
    
    for emp in employees_data:
        location = emp.get('location', 'Unknown')
        location_counts[location] = location_counts.get(location, 0) + 1
    
    locations = [{'name': location, 'count': count} 
                for location, count in sorted(location_counts.items(), key=lambda x: x[1], reverse=True)]
    
    return jsonify(locations)

@app.route('/api/stats')
def get_stats():
    """Enhanced stats for employee profiles"""
    # Calculate various statistics
    total_employees = len(employees_data)
    olenick_employees = len([e for e in employees_data if 'olenick' in e.get('company', '').lower()])
    google_employees = len([e for e in employees_data if 'google' in e.get('company', '').lower()])
    
    # Department distribution
    departments = {}
    for emp in employees_data:
        dept = emp.get('department', 'Unknown')
        departments[dept] = departments.get(dept, 0) + 1
    
    # Location distribution
    locations = {}
    for emp in employees_data:
        loc = emp.get('location', 'Unknown')
        locations[loc] = locations.get(loc, 0) + 1
    
    # Company distribution
    companies = {}
    for emp in employees_data:
        comp = emp.get('company', 'Unknown')
        companies[comp] = companies.get(comp, 0) + 1
    
    return jsonify({
        'total_employees': total_employees,
        'olenick_employees': olenick_employees,
        'google_employees': google_employees,
        'qt_team_members': len(core_team),
        'total_departments': len(departments),
        'total_locations': len(locations),
        'total_companies': len(companies),
        'top_departments': sorted(departments.items(), key=lambda x: x[1], reverse=True)[:10],
        'top_locations': sorted(locations.items(), key=lambda x: x[1], reverse=True)[:10],
        'top_companies': sorted(companies.items(), key=lambda x: x[1], reverse=True)[:10],
        'data_source': 'SharePoint Profiles.xlsx',
        'discovered_tenant': discovered_tenant_id,
        'last_sync': last_sync_time.isoformat() if last_sync_time else None,
        'processing_stats': processing_stats
    })

@app.route('/api/export-csv')
def export_csv():
    """Export employee data as CSV"""
    try:
        if not employees_data:
            return jsonify({'error': 'No data to export'}), 400
        
        # Create DataFrame
        df = pd.DataFrame(employees_data)
        
        # Generate CSV
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_content = csv_buffer.getvalue()
        
        # Return as downloadable file
        from flask import Response
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=employee_profiles_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'}
        )
        
    except Exception as e:
        return jsonify({'error': f'Export failed: {str(e)}'}), 500

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'data_loaded': len(employees_data) > 0,
        'total_records': len(employees_data),
        'file': 'Profiles.xlsx',
        'tenant_discovered': discovered_tenant_id is not None
    })

if __name__ == '__main__':
    print("🚀 Qonnect - Employee Profiles System")
    print("=" * 60)
    print("📄 NEW FILE: Profiles.xlsx")
    print("🔍 NO TENANT ID REQUIRED!")
    print("   • Automatic tenant discovery from domain")
    print("   • Username/password authentication")
    print("   • Device flow authentication fallback")
    print("   • Direct download attempts")
    print("   • Manual download support")
    print("   • Enhanced profile data processing")
    print()
    print("📄 SharePoint File Details:")
    print(f"   Document ID: {SHAREPOINT_CONFIG['document_id']}")
    print(f"   File: {SHAREPOINT_CONFIG['file_name']}")
    print(f"   URL: {SHAREPOINT_CONFIG['full_sharepoint_url'][:80]}...")
    print()
    print("🏢 Organization:")
    print(f"   Domain: {SHAREPOINT_CONFIG['organization_domain']}")
    print(f"   Username: {SHAREPOINT_CONFIG['username']}")
    print()
    
    # Try to load data on startup
    print("📄 Attempting to load Profiles.xlsx without tenant_id...")
    success = load_sharepoint_data_no_tenant()
    
    if success:
        print("🎉 Ready! Employee profiles loaded without requiring tenant_id")
        print(f"   📊 Total employees: {len(employees_data):,}")
        print(f"   📊 Olenick employees: {len([e for e in employees_data if 'olenick' in e.get('company', '').lower()]):,}")
        print(f"   📊 Departments: {len(set([e.get('department', 'Unknown') for e in employees_data])):,}")
        print(f"   📊 Locations: {len(set([e.get('location', 'Unknown') for e in employees_data])):,}")
        if discovered_tenant_id:
            print(f"   🔍 Discovered tenant: {discovered_tenant_id}")
        
        # Show sample data
        if employees_data:
            print(f"\n📋 Sample employee data:")
            sample = employees_data[0]
            for key, value in sample.items():
                print(f"   {key}: {value}")
                
    else:
        print("⚠️ Could not load employee profiles automatically")
        print("💡 Try manual download or check credentials")
        print("📄 Expected file: Profiles.xlsx")
    
    print(f"\n🌐 Starting Flask app on http://localhost:8080")
    print("🔧 Available endpoints:")
    print("   • GET  /                     - Main dashboard")
    print("   • POST /api/sync-sharepoint  - Sync data from SharePoint")
    print("   • GET  /api/search-employees - Search employees")
    print("   • GET  /api/employees/<id>   - Get employee details")
    print("   • GET  /api/departments      - List departments")
    print("   • GET  /api/locations        - List locations")
    print("   • GET  /api/stats            - System statistics")
    print("   • GET  /api/export-csv       - Export data as CSV")
    print("   • GET  /api/health           - Health check")
    
    app.run(debug=True, port=8080)