# Qonnect - GCP Architecture Documentation

**Project:** smartstakeholdersearch
**Region:** europe-west2 (London)
**Production URL:** https://qualitest.info
**Last Updated:** October 22, 2025

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Component Details](#component-details)
3. [Traffic Flow](#traffic-flow)
4. [Data Flow](#data-flow)
5. [Security Configuration](#security-configuration)
6. [Cost Breakdown](#cost-breakdown)
7. [Deployment Process](#deployment-process)
8. [Monitoring & Logging](#monitoring--logging)

---

## 🏗️ Architecture Overview

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          INTERNET / USERS                               │
│                    https://qualitest.info                               │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                │ DNS Resolution (GoDaddy)
                                │ qualitest.info → 34.110.166.7
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     GOOGLE CLOUD LOAD BALANCER                          │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐    │
│  │  Forwarding Rule: qualitest-https-rule                        │    │
│  │  IP Address: 34.110.166.7                                     │    │
│  │  Protocol: HTTPS (Port 443)                                   │    │
│  └───────────────────────────────────────────────────────────────┘    │
│                                │                                        │
│                                ▼                                        │
│  ┌───────────────────────────────────────────────────────────────┐    │
│  │  SSL Termination: qualitest-letsencrypt                       │    │
│  │  Certificate: Let's Encrypt (Self-Managed)                    │    │
│  └───────────────────────────────────────────────────────────────┘    │
│                                │                                        │
│                                ▼                                        │
│  ┌───────────────────────────────────────────────────────────────┐    │
│  │  URL Map: qualitest-urlmap                                    │    │
│  │  Path-based routing:                                          │    │
│  │    • /smartstakeholdersearch/* → Cloud Run                    │    │
│  │    • /defense-site/*           → Cloud Storage                │    │
│  │    • Default (/)               → Cloud Storage                │    │
│  └───────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                    │                                │
                    │                                │
        ┌───────────┴───────────┐       ┌──────────┴─────────────┐
        │                       │       │                        │
        ▼                       │       ▼                        │
┌──────────────────┐            │   ┌─────────────────────────┐ │
│  BACKEND SERVICE │            │   │  BACKEND BUCKET         │ │
│  qonnect-backend │            │   │  defense-site-backend   │ │
└────────┬─────────┘            │   └───────────┬─────────────┘ │
         │                      │               │               │
         │                      │               │               │
         ▼                      │               ▼               │
┌──────────────────┐            │   ┌─────────────────────────┐ │
│ Network Endpoint │            │   │  Cloud Storage Bucket   │ │
│ Group (NEG)      │            │   │  defense-site-static-*  │ │
│ qonnect-neg-*    │            │   │  CDN Enabled: Yes       │ │
└────────┬─────────┘            │   └─────────────────────────┘ │
         │                      │                               │
         │                      │                               │
         ▼                      │                               │
┌──────────────────────────────────────────────────┐           │
│          CLOUD RUN SERVICE                       │           │
│          qonnect-tool                            │           │
│  ┌────────────────────────────────────────────┐  │           │
│  │  Region: europe-west2                      │  │           │
│  │  Min Instances: 1                          │  │           │
│  │  Max Instances: 10                         │  │           │
│  │  CPU: 1 vCPU                               │  │           │
│  │  Memory: 1 GB                              │  │           │
│  │  Concurrency: 80 requests/container        │  │           │
│  │  Timeout: 300 seconds                      │  │           │
│  │  Container Port: 8080                      │  │           │
│  └────────────────────────────────────────────┘  │           │
│                                                  │           │
│  Environment Variables:                          │           │
│  • SECRET_KEY: 65e800c33f0966fdbb401d...        │           │
│                                                  │           │
│  Service Account:                                │           │
│  • 167154731583-compute@developer.g...          │           │
└──────────────────────────────────────────────────┘           │
         │                                                     │
         │  Reads/Writes Application Data                     │
         │                                                     │
         ▼                                                     │
┌──────────────────────────────────────────────────┐           │
│          CLOUD STORAGE BUCKET                    │           │
│          smartstakeholdersearch-data             │           │
│  ┌────────────────────────────────────────────┐  │           │
│  │  Location: europe-west2                    │  │           │
│  │  Storage Class: STANDARD                   │  │           │
│  │  Size: ~3.4 GB                             │  │           │
│  │  Objects: 190,053+ files                   │  │           │
│  └────────────────────────────────────────────┘  │           │
│                                                  │           │
│  Contents:                                       │           │
│  • employees.json         (Employee data)        │           │
│  • connections.json       (Network connections)  │           │
│  • credentials.json       (Service credentials)  │           │
│  • metadata.json          (System metadata)      │           │
│  • cache/                 (Hierarchy cache)      │           │
│  •   └── 190,053 files    (Employee hierarchies) │           │
│  • scripts/               (Utility scripts)      │           │
└──────────────────────────────────────────────────┘           │
                                                               │
┌──────────────────────────────────────────────────────────────┘
│                    SUPPORTING SERVICES
└──────────────────────────────────────────────────┐
                                                   │
    ┌──────────────────┬──────────────────────────┴─────────┐
    │                  │                                     │
    ▼                  ▼                                     ▼
┌─────────────┐  ┌──────────────┐              ┌────────────────────┐
│   LOGGING   │  │  MONITORING  │              │  ARTIFACT REGISTRY │
│             │  │              │              │                    │
│ Cloud       │  │ Cloud        │              │ Container Images:  │
│ Logging API │  │ Monitoring   │              │ europe-west2-*     │
│             │  │ API          │              │                    │
│ Stores all  │  │ Metrics &    │              │ qonnect-tool:      │
│ application │  │ uptime       │              │ sha256:3ede5bbc... │
│ logs        │  │ monitoring   │              │                    │
└─────────────┘  └──────────────┘              └────────────────────┘
```

---

## 🔧 Component Details

### 1. DNS Configuration (GoDaddy)

**Domain:** qualitest.info

| Record Type | Host | Value | TTL |
|-------------|------|-------|-----|
| A | @ | 34.110.166.7 | 600 |
| CNAME | www | qualitest.info | 600 |

**Purpose:** Routes traffic from domain to GCP Load Balancer

---

### 2. Load Balancer Components

#### 2.1 Forwarding Rule
```yaml
Name: qualitest-https-rule
IP Address: 34.110.166.7 (Static External IP)
Protocol: HTTPS
Port: 443
Target: qualitest-https-proxy
Load Balancing Scheme: EXTERNAL
```

#### 2.2 SSL Certificate
```yaml
Name: qualitest-letsencrypt
Type: SELF_MANAGED (Let's Encrypt)
Domains: qualitest.info
Protocol: TLS 1.2, TLS 1.3
```

#### 2.3 URL Map (qualitest-urlmap)
```yaml
Name: qualitest-urlmap
Default Service: defense-site-backend (Cloud Storage)

Route Rules:
  1. Path: /smartstakeholdersearch/*
     Service: qonnect-backend (Cloud Run)
     Priority: High

  2. Path: /defense-site/*
     Service: defense-site-backend (Cloud Storage)
     Priority: Medium

  3. Default: /
     Service: defense-site-backend (Cloud Storage)
     Priority: Low
```

#### 2.4 Backend Service
```yaml
Name: qonnect-backend
Protocol: HTTP
Load Balancing Scheme: EXTERNAL_MANAGED
Backend: qonnect-neg-london (Network Endpoint Group)
Region: europe-west2
Health Check: Automatic (Cloud Run)
Session Affinity: None
Timeout: 30 seconds
```

#### 2.5 Backend Bucket
```yaml
Name: defense-site-backend
Bucket: defense-site-static-qualitest
CDN Enabled: Yes
Cache Mode: CACHE_ALL_STATIC
Default TTL: 3600 seconds
```

---

### 3. Cloud Run Service

#### Service Configuration
```yaml
Service Name: qonnect-tool
Region: europe-west2
Platform: Managed (GKE)
Execution Environment: gen2

Container:
  Image: europe-west2-docker.pkg.dev/smartstakeholdersearch/
         cloud-run-source-deploy/qonnect-tool@sha256:3ede5bbcef...
  Port: 8080
  Protocol: HTTP/1

Resources:
  CPU: 1 vCPU
  Memory: 1 GB (1024 Mi)

Scaling:
  Min Instances: 1
  Max Instances: 10
  Concurrency: 80 requests per container

Timeout:
  Request Timeout: 300 seconds (5 minutes)
  Startup Probe: 240 seconds

Environment Variables:
  SECRET_KEY: 65e800c33f0966fdbb401d6de6f0a614bdb023960d88833f43f9ffe6515baf8a

Service Account:
  167154731583-compute@developer.gserviceaccount.com

Ingress: All traffic allowed
Traffic: 100% to latest revision
```

#### Current Revision
```yaml
Revision: qonnect-tool-00026-xxm
Created: 2025-10-22 13:59:24 UTC
Status: Active (100% traffic)
Generation: 26
```

#### Container Image Build
```yaml
Build Location: gs://run-sources-smartstakeholdersearch-europe-west2/
Build ID: 6be65d19-0c0a-4588-9a05-b2ddc94553c1
Source: Local directory (deployed via gcloud)
Dockerfile: Automatically generated by Cloud Run
```

---

### 4. Cloud Storage Buckets

#### 4.1 Application Data Bucket

**Bucket Name:** smartstakeholdersearch-data
**Location:** europe-west2
**Storage Class:** STANDARD
**Total Size:** ~3.4 GB (3,566,904,963 bytes)
**Total Objects:** 190,053+ files

**Directory Structure:**
```
gs://smartstakeholdersearch-data/
├── employees.json              (~60 KB)
│   └── All Qualitest employee data
│
├── connections.json            (~60 KB)
│   └── Network connection declarations
│
├── credentials.json            (Service account credentials)
│   └── Google Sheets API access
│
├── metadata.json               (System metadata)
│   └── Last sync times, version info
│
├── cache/                      (~3.4 GB, 190,053 files)
│   ├── employee_1.json         (Hierarchy for employee 1)
│   ├── employee_2.json         (Hierarchy for employee 2)
│   ├── ...
│   └── employee_94672.json     (Hierarchy for employee 94,672)
│   └── Purpose: Pre-computed Google employee hierarchies
│       Format: JSON with full reporting structure
│       Cache Hit Rate: ~100% after warm-up
│
└── scripts/                    (Utility scripts)
    ├── cache_warmup.py
    └── retry_failed_cache.py
```

**Access Control:**
- Project Owners: OWNER
- Compute Service Account: READ/WRITE
- Public Access: None (private)

**Cache Configuration:**
```yaml
Cache-Control Header: public, max-age=300
Purpose: Stores pre-computed employee hierarchies
Update Frequency: On-demand or via cache warming script
Cache Warmup: 587 employees cached in 5.3 minutes
Performance: Sub-second retrieval for 94,672 employees
```

#### 4.2 Defense Site Bucket

**Bucket Name:** defense-site-static-qualitest
**Location:** Global
**Storage Class:** STANDARD
**CDN Enabled:** Yes
**Public Access:** Yes (via Load Balancer)

**Purpose:** Hosts static defense/placeholder website

---

### 5. Network Configuration

#### Network Endpoint Group (NEG)
```yaml
Name: qonnect-neg-london
Type: Serverless NEG (Cloud Run)
Region: europe-west2
Target: Cloud Run service (qonnect-tool)
Purpose: Connects Load Balancer to Cloud Run
```

#### IP Addressing
```yaml
External IP: 34.110.166.7 (Static)
Type: Global EXTERNAL
Assigned To: qualitest-https-rule (Load Balancer)
DNS: qualitest.info → 34.110.166.7
```

---

### 6. IAM & Service Accounts

#### Service Accounts

**Default Compute Service Account:**
```yaml
Email: 167154731583-compute@developer.gserviceaccount.com
Display Name: Default compute service account
Used By: Cloud Run service
Permissions:
  - Cloud Storage: Read/Write to smartstakeholdersearch-data
  - Cloud Logging: Write logs
  - Cloud Monitoring: Write metrics
```

**Firebase Admin Service Account:**
```yaml
Email: firebase-adminsdk-fbsvc@smartstakeholdersearch.iam.gserviceaccount.com
Display Name: firebase-adminsdk
Status: Active (not currently used)
```

---

### 7. Enabled GCP Services

| Service | Purpose |
|---------|---------|
| **compute.googleapis.com** | Load Balancer, NEG, IP addresses |
| **run.googleapis.com** | Cloud Run service hosting |
| **storage.googleapis.com** | Cloud Storage buckets |
| **logging.googleapis.com** | Application and infrastructure logs |
| **monitoring.googleapis.com** | Metrics, uptime monitoring, alerts |
| **bigquerystorage.googleapis.com** | BigQuery integration (if needed) |
| **runtimeconfig.googleapis.com** | Runtime configuration |

---

## 🌊 Traffic Flow

### 1. User Request Flow

```
┌──────────────────────────────────────────────────────────────┐
│ Step 1: DNS Resolution                                       │
└──────────────────────────────────────────────────────────────┘

User Browser
    │
    │ DNS Query: qualitest.info
    │
    ▼
GoDaddy DNS Servers
    │
    │ Returns: 34.110.166.7 (A record)
    │
    ▼
User Browser (has IP address)


┌──────────────────────────────────────────────────────────────┐
│ Step 2: HTTPS Request to Load Balancer                      │
└──────────────────────────────────────────────────────────────┘

User Browser
    │
    │ HTTPS GET https://qualitest.info/smartstakeholdersearch/
    │ Destination: 34.110.166.7:443
    │
    ▼
Google Cloud Load Balancer (Forwarding Rule)
    │
    │ Receives: HTTPS request on port 443
    │
    ▼


┌──────────────────────────────────────────────────────────────┐
│ Step 3: SSL Termination                                     │
└──────────────────────────────────────────────────────────────┘

HTTPS Proxy (qualitest-https-proxy)
    │
    │ Decrypts: Using qualitest-letsencrypt certificate
    │ Validates: TLS 1.2/1.3 handshake
    │
    ▼
Decrypted HTTP request


┌──────────────────────────────────────────────────────────────┐
│ Step 4: URL Routing (Path Matching)                         │
└──────────────────────────────────────────────────────────────┘

URL Map (qualitest-urlmap)
    │
    │ Path: /smartstakeholdersearch/*
    │
    ├─ Match: /smartstakeholdersearch/*
    │  └─> Route to: qonnect-backend (Cloud Run)
    │
    ├─ Match: /defense-site/*
    │  └─> Route to: defense-site-backend (Cloud Storage)
    │
    └─ Default: /*
       └─> Route to: defense-site-backend (Cloud Storage)


┌──────────────────────────────────────────────────────────────┐
│ Step 5: Backend Service Processing                          │
└──────────────────────────────────────────────────────────────┘

Backend Service (qonnect-backend)
    │
    │ Selects: Available Cloud Run instance
    │ Load Balancing: Round-robin across instances
    │
    ▼
Network Endpoint Group (qonnect-neg-london)
    │
    │ Forwards: HTTP request to Cloud Run
    │
    ▼


┌──────────────────────────────────────────────────────────────┐
│ Step 6: Cloud Run Request Processing                        │
└──────────────────────────────────────────────────────────────┘

Cloud Run Service (qonnect-tool)
    │
    │ Container receives: HTTP request on port 8080
    │ Request path: /smartstakeholdersearch/
    │
    ▼
Flask Application (app.py)
    │
    ├─ Session check: Verify user authentication
    │  └─ Cookie: session (Flask secure cookie)
    │
    ├─ Route matching: @bp.route('/')
    │  └─ Handler: index()
    │
    ├─ Template rendering: templates/index.html
    │
    └─ Response: HTML page


┌──────────────────────────────────────────────────────────────┐
│ Step 7: Response Path (Back to User)                        │
└──────────────────────────────────────────────────────────────┘

Flask Application
    │
    │ Generates: HTML response
    │
    ▼
Cloud Run Service
    │
    │ Returns: HTTP 200 with HTML body
    │
    ▼
Network Endpoint Group → Backend Service → URL Map
    │
    │ Response propagates back
    │
    ▼
HTTPS Proxy
    │
    │ Encrypts: Response using TLS
    │
    ▼
Load Balancer Forwarding Rule
    │
    │ Sends: HTTPS response to 34.110.166.7
    │
    ▼
User Browser
    │
    │ Receives: Encrypted HTML page
    │ Renders: Qonnect home page
    │
    ▼
User sees Qonnect interface
```

**Total Latency Breakdown:**
- DNS resolution: 10-50ms
- TLS handshake: 50-100ms
- Load Balancer routing: 5-10ms
- Cloud Run processing: 50-500ms (depending on operation)
- Response transmission: 20-100ms
- **Total:** 135-760ms (typical: ~200-300ms)

---

### 2. API Request Flow (Search Example)

```
┌──────────────────────────────────────────────────────────────┐
│ Example: Search for Google Employee                         │
│ Request: GET /smartstakeholdersearch/api/connections/sundar │
└──────────────────────────────────────────────────────────────┘

User Browser (JavaScript)
    │
    │ fetch('/smartstakeholdersearch/api/connections/sundar')
    │
    ▼
Load Balancer (same path as above)
    │
    │ Routes to: qonnect-backend
    │
    ▼
Cloud Run: Flask Application
    │
    │ Route: @bp.route('/api/connections/<ldap>')
    │ Handler: get_employee_connections(ldap)
    │
    ├─ Step 1: Check cache in Cloud Storage
    │   │
    │   ├─> Read: gs://smartstakeholdersearch-data/cache/sundar.json
    │   │   └─ If exists: Return cached hierarchy (fast, <100ms)
    │   │
    │   └─> If not exists: Generate hierarchy (slower, 1-2s)
    │
    ├─ Step 2: Load employee data
    │   │
    │   └─> Read: gs://smartstakeholdersearch-data/employees.json
    │       └─ Parse: Find employee 'sundar'
    │
    ├─ Step 3: Build hierarchy
    │   │
    │   └─> Recursive function: Build reporting structure
    │       └─ Traverse: Manager → Reports → Reports' Reports
    │
    ├─ Step 4: Save to cache (if new)
    │   │
    │   └─> Write: gs://smartstakeholdersearch-data/cache/sundar.json
    │
    └─ Step 5: Return JSON response
        │
        └─> Response: {
              "employee": {...},
              "hierarchy": [...],
              "connections": [...]
            }
        │
        ▼
User Browser
    │
    │ Receives: JSON data
    │ Renders: Hierarchy visualization
    │
    ▼
User sees employee hierarchy chart
```

**Performance:**
- Cache hit: <100ms (read from GCS)
- Cache miss: 1-2 seconds (compute + write to GCS)
- Cache hit rate: ~100% after warm-up (94,672 employees pre-cached)

---

## 📊 Data Flow

### 1. Employee Data Sync

```
┌──────────────────────────────────────────────────────────────┐
│ Google Sheets → Cloud Storage → Application                 │
└──────────────────────────────────────────────────────────────┘

Google Sheets (Source of Truth)
    │
    │ Spreadsheet: Employee data (94,672 rows)
    │ Columns: LDAP, Name, Email, Role, Manager, etc.
    │
    ▼
Flask Application (Sync Function)
    │
    │ API: Google Sheets API v4
    │ Authentication: credentials.json (service account)
    │ Function: load_data_from_json() or sync_data()
    │
    ├─ Step 1: Fetch data from Sheets
    │   └─> Call: sheets.spreadsheets().values().get()
    │       └─> Returns: All employee rows
    │
    ├─ Step 2: Transform data
    │   └─> Parse: Convert rows to JSON objects
    │       └─> Validate: Check required fields
    │
    ├─ Step 3: Write to Cloud Storage
    │   └─> Write: gs://smartstakeholdersearch-data/employees.json
    │       └─> Format: JSON array of employee objects
    │
    └─ Step 4: Update metadata
        └─> Write: gs://smartstakeholdersearch-data/metadata.json
            └─> Contains: Last sync timestamp, record count
        │
        ▼
Cloud Storage (smartstakeholdersearch-data)
    │
    │ employees.json: Updated with latest data
    │ metadata.json: Updated sync timestamp
    │
    ▼
Application reads from GCS for all operations
```

---

### 2. Connection Declaration Flow

```
┌──────────────────────────────────────────────────────────────┐
│ User declares connection → Saved to Cloud Storage           │
└──────────────────────────────────────────────────────────────┘

User Browser (Declare Page)
    │
    │ Form: Select 2 employees + strength (Weak/Medium/Strong)
    │ Submit: POST /smartstakeholdersearch/api/declare
    │
    ▼
Flask Application
    │
    │ Route: @bp.route('/api/declare', methods=['POST'])
    │ Handler: declare_connection()
    │
    ├─ Step 1: Validate input
    │   └─> Check: Both employees exist
    │       └─> Check: Strength is valid (Weak/Medium/Strong)
    │
    ├─ Step 2: Load existing connections
    │   └─> Read: gs://smartstakeholdersearch-data/connections.json
    │
    ├─ Step 3: Add new connection
    │   └─> Append: {
    │         "from": "employee1_ldap",
    │         "to": "employee2_ldap",
    │         "strength": "Strong",
    │         "declared_by": "current_user",
    │         "declared_at": "2025-10-22T14:00:00Z"
    │       }
    │
    ├─ Step 4: Save to Cloud Storage
    │   └─> Write: gs://smartstakeholdersearch-data/connections.json
    │       └─> Atomic write: Overwrite entire file
    │
    └─ Step 5: Return success
        └─> Response: {"success": true, "message": "Connection declared"}
        │
        ▼
User Browser
    │
    │ Shows: Success message
    │ Updates: Connection count
    │
    ▼
Connection visible in network graph
```

---

### 3. Cache Warming Flow

```
┌──────────────────────────────────────────────────────────────┐
│ Pre-compute and cache all employee hierarchies              │
└──────────────────────────────────────────────────────────────┘

Cache Warming Script (cache_warmup.py)
    │
    │ Runs: On-demand or scheduled
    │ Target: All 94,672 Google employees
    │
    ├─ Step 1: Load all employees
    │   └─> Read: gs://smartstakeholdersearch-data/employees.json
    │       └─> Parse: Get list of all LDAPs
    │
    ├─ Step 2: For each employee (parallel processing)
    │   │
    │   ├─> Check: Does cache exist?
    │   │   └─> gs://smartstakeholdersearch-data/cache/{ldap}.json
    │   │
    │   ├─> If not exists:
    │   │   ├─ Compute hierarchy
    │   │   ├─ Build reporting structure
    │   │   └─ Write to cache
    │   │
    │   └─> Progress: Log every 100 employees
    │
    ├─ Step 3: Handle failures
    │   └─> Retry: Failed employees with longer timeout (60s)
    │
    └─ Step 4: Report results
        └─> Summary:
            ├─ Total: 94,672 employees
            ├─ Cached: 94,085 succeeded
            ├─ Failed: 587 employees
            ├─ Retry: All 587 succeeded (5.3 minutes)
            └─ Final: 100% cache coverage
        │
        ▼
Cloud Storage (smartstakeholdersearch-data/cache/)
    │
    │ Contains: 190,053 cache files
    │ Size: ~3.4 GB
    │ Coverage: 100% of employees
    │
    ▼
Application serves all requests from cache (sub-second)
```

**Cache Statistics:**
- Total files: 190,053
- Total size: 3.4 GB (3,566,904,963 bytes)
- Average file size: ~18 KB
- Cache hit rate: ~100%
- Read performance: <100ms per file

---

## 🔒 Security Configuration

### 1. Authentication & Authorization

```
┌──────────────────────────────────────────────────────────────┐
│ User Authentication Flow                                     │
└──────────────────────────────────────────────────────────────┘

Login Page: /smartstakeholdersearch/login
    │
    │ User enters: Username + Password
    │ Submit: POST /smartstakeholdersearch/api/login
    │
    ▼
Flask Application (app.py)
    │
    │ Route: @bp.route('/api/login', methods=['POST'])
    │
    ├─ Step 1: Validate credentials
    │   └─> Check: Username exists in employee database
    │       └─> Verify: Password hash matches
    │
    ├─ Step 2: Create session
    │   └─> Flask session (server-side)
    │       └─> Store: user_id, username, login_time
    │
    ├─ Step 3: Set secure cookie
    │   └─> Cookie name: session
    │   └─> HttpOnly: True (prevents JavaScript access)
    │   └─> Secure: True (HTTPS only)
    │   └─> SameSite: Lax (CSRF protection)
    │   └─> Max-Age: 30 days (if "Remember Me" checked)
    │
    └─ Step 4: Return success
        └─> Response: {"success": true}
        │
        ▼
User Browser
    │
    │ Stores: Encrypted session cookie
    │ Redirects: To /smartstakeholdersearch/
    │
    ▼
Authenticated session (valid for 30 days)
```

**Session Configuration:**
```python
app.secret_key = '65e800c33f0966fdbb401d6de6f0a614bdb023960d88833f43f9ffe6515baf8a'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
```

---

### 2. Network Security

```
┌──────────────────────────────────────────────────────────────┐
│ Security Layers                                              │
└──────────────────────────────────────────────────────────────┘

Layer 1: TLS Encryption
    ├─ Protocol: TLS 1.2, TLS 1.3
    ├─ Certificate: Let's Encrypt (qualitest-letsencrypt)
    ├─ Cipher Suites: Modern, secure algorithms
    └─ HTTPS enforced (no HTTP access)

Layer 2: Load Balancer Security
    ├─ IP Whitelisting: Not configured (public access)
    ├─ DDoS Protection: Google Cloud Armor (optional)
    ├─ Rate Limiting: Not configured
    └─ Firewall Rules: Default (allows HTTPS)

Layer 3: Cloud Run Security
    ├─ Authentication: Required (via Flask sessions)
    ├─ Service Account: Least privilege access
    ├─ Container Isolation: gVisor (secure sandbox)
    └─ Egress Control: Default (allows all)

Layer 4: Application Security
    ├─ Session Management: Flask sessions (secure cookies)
    ├─ CSRF Protection: SameSite=Lax cookies
    ├─ XSS Protection: Content-Type headers, escaping
    └─ SQL Injection: Not applicable (no SQL database)
```

---

### 3. Data Security

```
┌──────────────────────────────────────────────────────────────┐
│ Data Encryption & Access Control                            │
└──────────────────────────────────────────────────────────────┘

Cloud Storage Bucket: smartstakeholdersearch-data
    │
    ├─ Encryption at Rest: Enabled (default)
    │   └─> Google-managed encryption keys
    │
    ├─ Encryption in Transit: TLS 1.2+
    │   └─> All API calls use HTTPS
    │
    ├─ Access Control:
    │   ├─> Project Owners: OWNER
    │   ├─> Compute Service Account: READ/WRITE
    │   ├─> Public Access: DENIED
    │   └─> IAM Policies: Principle of least privilege
    │
    └─ Object Versioning: Disabled (not needed)
```

**Sensitive Data:**
- `credentials.json`: Google Sheets API service account key
  - Access: Restricted to Cloud Run service account
  - Usage: Read-only access to Google Sheets
  - Rotation: Manual (should rotate annually)

---

### 4. Monitoring & Audit Logging

```
┌──────────────────────────────────────────────────────────────┐
│ Logging Configuration                                        │
└──────────────────────────────────────────────────────────────┘

Cloud Logging
    │
    ├─ Application Logs (Cloud Run)
    │   ├─> Flask application logs
    │   ├─> Request/response logs
    │   ├─> Error traces
    │   └─> Retention: 30 days (default)
    │
    ├─ Load Balancer Logs
    │   ├─> Access logs (HTTP requests)
    │   ├─> Error logs (4xx, 5xx)
    │   └─> Latency metrics
    │
    ├─ Cloud Storage Logs
    │   ├─> Data access logs
    │   └─> Admin activity logs
    │
    └─ Security Logs
        ├─> Authentication events
        ├─> IAM policy changes
        └─> Service account usage
```

---

## 💰 Cost Breakdown

### Monthly Cost Estimate

| Service | Usage | Cost per Month |
|---------|-------|----------------|
| **Cloud Run** | 1-10 instances, 1 vCPU, 1 GB RAM | $5-15 |
| **Load Balancer** | 1 forwarding rule, global | $18-25 |
| **Cloud Storage (Data)** | ~3.4 GB STANDARD class | $0.08 |
| **Cloud Storage (Defense)** | ~100 MB STANDARD class | $0.00 |
| **Cloud Logging** | ~5 GB logs/month | $2.50 |
| **Cloud Monitoring** | Basic metrics | $0.00 (free tier) |
| **Network Egress** | ~10 GB/month | $1.20 |
| **Artifact Registry** | Container images storage | $0.10 |
| **SSL Certificate** | Let's Encrypt (free) | $0.00 |
| **Static IP** | 1 global IP | $0.00 (in use) |
| **Total** | | **$27-44/month** |

**Cost Optimization Opportunities:**
1. Remove Load Balancer (-$18-25/month)
   - Direct Cloud Run usage
   - No CDN, no custom domain routing

2. Reduce Cloud Run min instances (-$3-5/month)
   - Change from 1 to 0 min instances
   - Trade: Cold start latency

3. Use Cloud Storage lifecycle policies (-$0.02/month)
   - Archive old cache files to Nearline/Coldline
   - Minimal savings

**Current Decision:** Keep Load Balancer for production stability and CDN benefits.

---

## 🚀 Deployment Process

### 1. Application Deployment

```
┌──────────────────────────────────────────────────────────────┐
│ Deployment Flow (Local → Cloud Run)                         │
└──────────────────────────────────────────────────────────────┘

Local Development
    │
    │ Developer makes changes to app.py, templates, etc.
    │ Test locally: python3 app.py
    │
    ▼
Git Repository
    │
    │ Commit: git add . && git commit -m "Feature update"
    │ Push: git push origin main
    │
    ▼
Cloud Run Deployment (Manual)
    │
    │ Command: gcloud run deploy qonnect-tool \
    │            --source . \
    │            --region europe-west2 \
    │            --project smartstakeholdersearch \
    │            --allow-unauthenticated
    │
    ├─ Step 1: Upload source code
    │   └─> Destination: gs://run-sources-smartstakeholdersearch-*/
    │       └─> Zip: Source directory → GCS
    │
    ├─ Step 2: Cloud Build
    │   └─> Automatically detect: Python app (app.py, requirements.txt)
    │       └─> Generate: Dockerfile
    │       └─> Build: Container image
    │       └─> Push: To Artifact Registry
    │
    ├─ Step 3: Deploy new revision
    │   └─> Create: New Cloud Run revision
    │       └─> Image: europe-west2-docker.pkg.dev/.../qonnect-tool@sha256:...
    │       └─> Environment: Copy from previous revision
    │
    ├─ Step 4: Traffic migration
    │   └─> Shift: 100% traffic to new revision
    │       └─> Gradual rollout: Instant (can configure gradual)
    │
    └─ Step 5: Health check
        └─> Verify: New instances are healthy
            └─> Startup probe: TCP port 8080 (240s timeout)
        │
        ▼
New revision is live (qonnect-tool-00026-xxm)
```

**Deployment Commands:**
```bash
# Standard deployment
gcloud run deploy qonnect-tool \
  --source . \
  --region europe-west2 \
  --project smartstakeholdersearch

# With environment variables
gcloud run services update qonnect-tool \
  --region europe-west2 \
  --project smartstakeholdersearch \
  --set-env-vars="SECRET_KEY=65e800c33f0..."

# Rollback to previous revision
gcloud run services update-traffic qonnect-tool \
  --to-revisions qonnect-tool-00025-ncr=100 \
  --region europe-west2

# View logs during deployment
gcloud run services logs read qonnect-tool \
  --region europe-west2 \
  --project smartstakeholdersearch \
  --limit 50
```

---

### 2. Infrastructure Deployment (Terraform/gcloud)

**Current Setup:** Manually created via gcloud CLI

**Future Recommendation:** Use Terraform for infrastructure as code

```hcl
# Example Terraform configuration (not currently used)

# Cloud Run Service
resource "google_cloud_run_service" "qonnect_tool" {
  name     = "qonnect-tool"
  location = "europe-west2"

  template {
    spec {
      containers {
        image = "europe-west2-docker.pkg.dev/smartstakeholdersearch/cloud-run-source-deploy/qonnect-tool"

        resources {
          limits = {
            cpu    = "1000m"
            memory = "1Gi"
          }
        }

        env {
          name  = "SECRET_KEY"
          value = var.secret_key
        }
      }
    }

    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale" = "1"
        "autoscaling.knative.dev/maxScale" = "10"
      }
    }
  }
}

# Load Balancer
resource "google_compute_global_forwarding_rule" "default" {
  name       = "qualitest-https-rule"
  target     = google_compute_target_https_proxy.default.id
  port_range = "443"
  ip_address = google_compute_global_address.default.address
}

# Cloud Storage Bucket
resource "google_storage_bucket" "data" {
  name          = "smartstakeholdersearch-data"
  location      = "europe-west2"
  storage_class = "STANDARD"
}
```

---

## 📈 Monitoring & Logging

### 1. Cloud Run Metrics

**Available Metrics:**
- Request count (total requests/second)
- Request latency (p50, p95, p99)
- Container CPU utilization
- Container memory utilization
- Instance count (active instances)
- Billable time (container seconds)

**Access:**
```bash
# View metrics via CLI
gcloud monitoring time-series list \
  --filter='resource.type="cloud_run_revision"' \
  --project=smartstakeholdersearch

# Or via Cloud Console:
https://console.cloud.google.com/run/detail/europe-west2/qonnect-tool/metrics
```

---

### 2. Application Logs

**Log Levels:**
- INFO: Normal operations
- WARNING: Unexpected but handled events
- ERROR: Application errors
- CRITICAL: System failures

**View Logs:**
```bash
# Recent logs
gcloud run services logs read qonnect-tool \
  --region=europe-west2 \
  --limit=100

# Follow live logs
gcloud run services logs tail qonnect-tool \
  --region=europe-west2

# Filter by severity
gcloud logging read 'resource.type="cloud_run_revision" AND severity="ERROR"' \
  --limit=50 \
  --project=smartstakeholdersearch
```

---

### 3. Uptime Monitoring

**Recommended Setup (not currently configured):**

```yaml
Uptime Check:
  Name: qonnect-production-check
  Type: HTTPS
  URL: https://qualitest.info/smartstakeholdersearch/
  Frequency: 1 minute
  Timeout: 10 seconds
  Regions: Multiple (US, EU, Asia)
  Alert:
    - Email: myselfsohailislam@gmail.com
    - Threshold: 2 consecutive failures
```

**Create Uptime Check:**
```bash
gcloud monitoring uptime-check-configs create qonnect-production \
  --display-name="Qonnect Production" \
  --resource-type=uptime-url \
  --host=qualitest.info \
  --path=/smartstakeholdersearch/ \
  --project=smartstakeholdersearch
```

---

## 🔧 Troubleshooting Guide

### Common Issues & Solutions

#### 1. 502 Bad Gateway
**Symptom:** Load Balancer returns 502 error

**Possible Causes:**
- Cloud Run instance not ready
- Container startup timeout
- Backend service misconfiguration

**Solution:**
```bash
# Check Cloud Run status
gcloud run services describe qonnect-tool \
  --region=europe-west2 \
  --format="value(status.conditions)"

# Check backend service
gcloud compute backend-services describe qonnect-backend \
  --global \
  --format="value(backends)"

# View recent errors
gcloud logging read 'resource.type="cloud_run_revision" AND severity="ERROR"' \
  --limit=20
```

---

#### 2. Login Not Working
**Symptom:** Users cannot login, session not persisting

**Possible Causes:**
- SESSION_COOKIE_SECURE mismatch (HTTP vs HTTPS)
- SECRET_KEY changed between deployments
- Cookie blocked by browser

**Solution:**
```bash
# Verify SECRET_KEY is set
gcloud run services describe qonnect-tool \
  --region=europe-west2 \
  --format="value(spec.template.spec.containers[0].env)"

# Check session configuration in app.py
# Ensure: SESSION_COOKIE_SECURE = True (for HTTPS)

# Test login API directly
curl -X POST https://qualitest.info/smartstakeholdersearch/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"sohail.islam","password":"***"}' \
  -c cookies.txt \
  -v
```

---

#### 3. Slow Search Performance
**Symptom:** Employee search takes >2 seconds

**Possible Causes:**
- Cache not warmed up (missing cache files)
- Cloud Storage slow read
- Too many concurrent requests

**Solution:**
```bash
# Check cache coverage
gsutil ls gs://smartstakeholdersearch-data/cache/ | wc -l
# Should show: 190,053 files

# Run cache warming script
python3 cache_warmup.py

# Check Cloud Storage performance
gsutil stat gs://smartstakeholdersearch-data/cache/sundar.json

# Increase Cloud Run instances
gcloud run services update qonnect-tool \
  --region=europe-west2 \
  --min-instances=2
```

---

#### 4. Out of Memory Errors
**Symptom:** Container crashes with OOM (Out of Memory)

**Possible Causes:**
- Memory leak in application
- Too much data loaded in memory
- Concurrency too high

**Solution:**
```bash
# Check memory usage
gcloud monitoring time-series list \
  --filter='resource.type="cloud_run_revision" AND metric.type="run.googleapis.com/container/memory/utilizations"' \
  --project=smartstakeholdersearch

# Increase memory limit
gcloud run services update qonnect-tool \
  --region=europe-west2 \
  --memory=2Gi

# Or reduce concurrency
gcloud run services update qonnect-tool \
  --region=europe-west2 \
  --concurrency=40
```

---

## 📝 Maintenance Procedures

### 1. Update Application Code
```bash
# 1. Pull latest code
git pull origin main

# 2. Test locally
python3 app.py

# 3. Deploy to Cloud Run
gcloud run deploy qonnect-tool \
  --source . \
  --region europe-west2 \
  --project smartstakeholdersearch

# 4. Verify deployment
curl -I https://qualitest.info/smartstakeholdersearch/

# 5. Monitor logs for errors
gcloud run services logs tail qonnect-tool --region=europe-west2
```

---

### 2. Rotate SECRET_KEY
```bash
# 1. Generate new secret key
NEW_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')

# 2. Update Cloud Run environment variable
gcloud run services update qonnect-tool \
  --region=europe-west2 \
  --project=smartstakeholdersearch \
  --set-env-vars="SECRET_KEY=$NEW_KEY"

# 3. All users will need to re-login
# (sessions are invalidated with new key)
```

---

### 3. Cache Warm-up
```bash
# 1. Upload cache warming script to Cloud Storage
gsutil cp cache_warmup.py gs://smartstakeholdersearch-data/scripts/

# 2. Run from Cloud Run or Cloud Shell
python3 cache_warmup.py

# 3. Monitor progress
# Output shows: Progress, success count, failure count

# 4. Retry failed entries
python3 retry_failed_cache_warming.py
```

---

### 4. Backup Data
```bash
# Backup all data files
gsutil -m cp -r gs://smartstakeholdersearch-data/ ./backups/$(date +%Y%m%d)/

# Backup specific files
gsutil cp gs://smartstakeholdersearch-data/employees.json ./backups/
gsutil cp gs://smartstakeholdersearch-data/connections.json ./backups/

# Restore from backup
gsutil cp ./backups/employees.json gs://smartstakeholdersearch-data/
```

---

## 🎯 Best Practices

### 1. Deployment
- ✅ Always test locally before deploying
- ✅ Deploy during low-traffic periods
- ✅ Monitor logs immediately after deployment
- ✅ Keep previous revision for quick rollback
- ✅ Use git tags for production releases

### 2. Security
- ✅ Rotate SECRET_KEY annually
- ✅ Review IAM permissions quarterly
- ✅ Keep credentials.json private (never commit)
- ✅ Monitor authentication logs
- ✅ Use HTTPS everywhere

### 3. Performance
- ✅ Maintain warm cache (cache warming script)
- ✅ Monitor response times (p95, p99)
- ✅ Keep min instances = 1 for production
- ✅ Optimize Cloud Storage reads (batch requests)
- ✅ Use CDN for static assets

### 4. Cost Optimization
- ✅ Review monthly billing reports
- ✅ Delete unused resources
- ✅ Consider Cloud Storage lifecycle policies
- ✅ Adjust min/max instances based on traffic
- ✅ Monitor egress bandwidth

---

## 📚 Reference Links

### GCP Console
- **Cloud Run:** https://console.cloud.google.com/run?project=smartstakeholdersearch
- **Load Balancer:** https://console.cloud.google.com/net-services/loadbalancing?project=smartstakeholdersearch
- **Cloud Storage:** https://console.cloud.google.com/storage/browser?project=smartstakeholdersearch
- **Logs:** https://console.cloud.google.com/logs?project=smartstakeholdersearch
- **Monitoring:** https://console.cloud.google.com/monitoring?project=smartstakeholdersearch

### Documentation
- Cloud Run Docs: https://cloud.google.com/run/docs
- Load Balancing Docs: https://cloud.google.com/load-balancing/docs
- Cloud Storage Docs: https://cloud.google.com/storage/docs

---

## 📧 Contact & Support

**Project Owner:** myselfsohailislam@gmail.com
**GCP Project ID:** smartstakeholdersearch
**Project Number:** 167154731583
**Support:** https://cloud.google.com/support

---

**Document Version:** 1.0
**Last Updated:** October 22, 2025
**Next Review:** January 2026
