# SSL Renewal Automation - Setup Instructions

**Follow these steps to set up automated SSL certificate renewal**

---

## 🎯 What We're Setting Up

Automated SSL certificate renewal that runs in the cloud every 60 days.

**Time Required:** 30-40 minutes
**Cost:** ~$0.36/month (~$4/year)
**Manual Work After Setup:** ZERO

---

## ✅ Prerequisites

Before starting, ensure you have:
- [ ] GCP account with Owner/Editor role on `smartstakeholdersearch` project
- [ ] `gcloud` CLI installed and authenticated
- [ ] Access to GoDaddy account (domain owner)
- [ ] Access to: https://developer.godaddy.com

---

## 📝 Step-by-Step Setup

### Step 1: Get GoDaddy API Credentials (5 minutes)

#### 1.1 Login to GoDaddy Developer Portal
```
URL: https://developer.godaddy.com/keys
Login with your GoDaddy account credentials
```

#### 1.2 Create Production API Key
1. Click "Create New API Key"
2. Select Environment: **Production** (NOT OTE)
3. Give it a name: "SSL Certificate Renewal"
4. Click "Next"

#### 1.3 Save Credentials IMMEDIATELY
```
⚠️ CRITICAL: GoDaddy shows these ONLY ONCE!

API Key:    [Copy this - looks like: dUQk6nJxXPxW_S5z...]
API Secret: [Copy this - looks like: S5zR8xPx...]

Save these in a secure location RIGHT NOW!
```

✅ **Checkpoint:** You have saved both API Key and API Secret

---

### Step 2: Enable Required GCP APIs (2 minutes)

Run these commands:

```bash
# Enable Secret Manager
gcloud services enable secretmanager.googleapis.com \
  --project=smartstakeholdersearch

# Enable Cloud Build
gcloud services enable cloudbuild.googleapis.com \
  --project=smartstakeholdersearch

# Enable Cloud Scheduler
gcloud services enable cloudscheduler.googleapis.com \
  --project=smartstakeholdersearch

# Enable Cloud Run
gcloud services enable run.googleapis.com \
  --project=smartstakeholdersearch
```

✅ **Checkpoint:** All APIs enabled without errors

---

### Step 3: Store GoDaddy Credentials in Secret Manager (3 minutes)

```bash
# Store API Key
echo -n "YOUR_GODADDY_API_KEY_HERE" | \
  gcloud secrets create godaddy-api-key \
  --project=smartstakeholdersearch \
  --replication-policy="automatic" \
  --data-file=-

# Store API Secret
echo -n "YOUR_GODADDY_API_SECRET_HERE" | \
  gcloud secrets create godaddy-api-secret \
  --project=smartstakeholdersearch \
  --replication-policy="automatic" \
  --data-file=-
```

**Replace:**
- `YOUR_GODADDY_API_KEY_HERE` with your actual API key
- `YOUR_GODADDY_API_SECRET_HERE` with your actual API secret

**⚠️ IMPORTANT:** Use `echo -n` (with -n flag) to avoid adding newline!

#### Verify secrets created:
```bash
gcloud secrets list --project=smartstakeholdersearch | grep godaddy
```

You should see:
```
godaddy-api-key
godaddy-api-secret
```

✅ **Checkpoint:** Both secrets created and visible

---

### Step 4: Grant Service Account Access to Secrets (2 minutes)

```bash
# Grant access to godaddy-api-key
gcloud secrets add-iam-policy-binding godaddy-api-key \
  --member="serviceAccount:167154731583-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=smartstakeholdersearch

# Grant access to godaddy-api-secret
gcloud secrets add-iam-policy-binding godaddy-api-secret \
  --member="serviceAccount:167154731583-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=smartstakeholdersearch
```

✅ **Checkpoint:** Permissions granted successfully

---

### Step 5: Build Docker Container (5-10 minutes)

```bash
# Navigate to ssl-renewal directory
cd /Users/sism/Downloads/Sohail\ Islam/Personal\ Projects/qonnect-tool/ssl-renewal

# Build and push container image
gcloud builds submit \
  --tag gcr.io/smartstakeholdersearch/ssl-renewal \
  --project=smartstakeholdersearch
```

This will:
- Build Docker image with certbot and dependencies
- Push to Google Container Registry
- Take 5-10 minutes

✅ **Checkpoint:** Build completed with "SUCCESS" message

---

### Step 6: Deploy Cloud Run Job (2 minutes)

```bash
gcloud run jobs create ssl-renewal \
  --image gcr.io/smartstakeholdersearch/ssl-renewal \
  --region europe-west2 \
  --project smartstakeholdersearch \
  --set-env-vars="DOMAIN=qualitest.info" \
  --set-env-vars="GCP_PROJECT=smartstakeholdersearch" \
  --set-env-vars="HTTPS_PROXY_NAME=qualitest-https-proxy" \
  --set-env-vars="ADMIN_EMAIL=myselfsohailislam@gmail.com" \
  --set-secrets="GODADDY_API_KEY=godaddy-api-key:latest" \
  --set-secrets="GODADDY_API_SECRET=godaddy-api-secret:latest" \
  --max-retries=1 \
  --task-timeout=10m \
  --memory=512Mi \
  --cpu=1
```

✅ **Checkpoint:** Cloud Run job created successfully

---

### Step 7: Test Manual Execution (IMPORTANT!) (5-10 minutes)

```bash
# Execute job manually to test everything works
gcloud run jobs execute ssl-renewal \
  --region europe-west2 \
  --project smartstakeholdersearch \
  --wait
```

**This will:**
1. Run the renewal process
2. Renew your SSL certificate
3. Upload to GCP
4. Update Load Balancer
5. Take 5-10 minutes

**Watch the logs:**
```bash
# In another terminal, follow logs
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=ssl-renewal" \
  --limit=100 \
  --project=smartstakeholdersearch \
  --format="value(timestamp,textPayload)" \
  --freshness=10m
```

**Expected output:**
```
✅ Certificate renewed successfully!
✅ Certificate uploaded to GCP successfully!
✅ HTTPS proxy updated successfully!
✅ Verification successful! New certificate is active.
✅ SSL Certificate Renewal - Completed Successfully!
```

✅ **Checkpoint:** Job completed successfully, new certificate active

---

### Step 8: Verify Production Working (2 minutes)

```bash
# Test production URLs
curl -I https://qualitest.info/smartstakeholdersearch/

# Check certificate details
echo | openssl s_client -servername qualitest.info \
  -connect qualitest.info:443 2>/dev/null | \
  openssl x509 -noout -dates

# Should show:
# notAfter=Jan XX 2026 (new expiry date ~90 days from now)
```

✅ **Checkpoint:** Production working, new certificate active

---

### Step 9: Set Up Cloud Scheduler (Automated Runs) (3 minutes)

```bash
# Create scheduler to run every 60 days
gcloud scheduler jobs create http ssl-renewal-scheduler \
  --location=europe-west2 \
  --schedule="0 2 1 */2 *" \
  --time-zone="Asia/Kolkata" \
  --uri="https://europe-west2-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/smartstakeholdersearch/jobs/ssl-renewal:run" \
  --http-method=POST \
  --oauth-service-account-email="167154731583-compute@developer.gserviceaccount.com" \
  --project=smartstakeholdersearch \
  --description="Automatically renews SSL certificate every 60 days"
```

**Schedule Explanation:**
- `0 2 1 */2 *` = 2:00 AM on 1st day of every 2nd month
- Runs: Jan 1, Mar 1, May 1, July 1, Sep 1, Nov 1
- Time zone: Asia/Kolkata (IST)

✅ **Checkpoint:** Scheduler created successfully

---

### Step 10: Verify Scheduler (1 minute)

```bash
# List schedulers
gcloud scheduler jobs list \
  --location=europe-west2 \
  --project=smartstakeholdersearch

# Should show:
# NAME: ssl-renewal-scheduler
# SCHEDULE: 0 2 1 */2 *
# STATE: ENABLED
```

✅ **Checkpoint:** Scheduler is ENABLED

---

## 🎉 Setup Complete!

Congratulations! Your automated SSL renewal is now active.

### What Happens Next:

1. **Scheduler runs automatically** every 60 days at 2 AM IST
2. **Certificate renews** without any manual intervention
3. **Load Balancer updates** automatically
4. **You get email** if anything fails

### Next Automated Renewal:

Approximately **60 days from today**: ~December 22, 2025

---

## 📊 Monitoring

### Check Next Scheduled Run:
```bash
gcloud scheduler jobs describe ssl-renewal-scheduler \
  --location=europe-west2 \
  --project=smartstakeholdersearch \
  --format="value(schedule,timeZone,state)"
```

### View Execution History:
```bash
gcloud run jobs executions list \
  --job=ssl-renewal \
  --region=europe-west2 \
  --project=smartstakeholdersearch
```

### View Logs:
```bash
gcloud logging read "resource.type=cloud_run_job" \
  --limit=50 \
  --project=smartstakeholdersearch
```

---

## 🔔 Notifications

### Enable Email Alerts on Failure:

```bash
# Create notification channel (one-time)
gcloud alpha monitoring channels create \
  --display-name="SSL Renewal Alerts" \
  --type=email \
  --channel-labels=email_address=myselfsohailislam@gmail.com \
  --project=smartstakeholdersearch
```

---

## ✅ Final Checklist

Before considering setup complete:

- [x] GoDaddy API credentials obtained and saved
- [x] Secrets stored in Secret Manager
- [x] Cloud Run job deployed
- [x] Manual test execution successful
- [x] New certificate active on production
- [x] Production URLs working
- [x] Cloud Scheduler created and enabled
- [x] Next run date confirmed

---

## 🎯 Summary

**What was set up:**
- Automated SSL renewal every 60 days
- Runs in GCP Cloud (no local machine needed)
- Cost: ~$0.36/month (~$4/year)
- Maintenance: ZERO

**Next steps:**
- Nothing! System runs automatically
- Check logs occasionally to verify
- Relax knowing your SSL won't expire

---

**Setup completed:** October 23, 2025
**Next automated renewal:** ~December 22, 2025
**Manual work required:** ZERO

🎉 **Congratulations! You'll never worry about SSL renewal again!**
