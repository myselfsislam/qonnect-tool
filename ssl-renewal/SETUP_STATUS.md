# SSL Automation Setup Status

**Last Updated:** October 23, 2025
**Setup Progress:** 50% Complete

---

## ✅ Completed Steps

### 1. Automation Files Created
- ✅ `Dockerfile` - Container with certbot and GoDaddy DNS plugin
- ✅ `renew.sh` - Comprehensive renewal script
- ✅ `README.md` - Technical documentation
- ✅ `SETUP_INSTRUCTIONS.md` - Step-by-step setup guide

### 2. GCP APIs Enabled
All required APIs have been enabled in the `smartstakeholdersearch` project:
- ✅ Secret Manager API (`secretmanager.googleapis.com`)
- ✅ Cloud Build API (`cloudbuild.googleapis.com`)
- ✅ Cloud Scheduler API (`cloudscheduler.googleapis.com`)
- ✅ Cloud Run API (`run.googleapis.com`)

### 3. Docker Container Built and Deployed
- ✅ Container image built successfully
- ✅ Image available at: `gcr.io/smartstakeholdersearch/ssl-renewal`
- ✅ Build ID: `495fd282-1494-4ef1-806e-bbbbf47941bb`
- ✅ Build Status: SUCCESS
- ✅ Dockerfile fix applied (replaced deprecated `apt-key` with modern `gpg --dearmor`)

---

## ⏳ Remaining Steps (User Action Required)

The following steps require **GoDaddy API credentials**, which only you can obtain:

### Step 1: Get GoDaddy API Credentials (5 minutes)
**Action Required:** Visit https://developer.godaddy.com/keys

1. Login to GoDaddy Developer Portal
2. Click "Create New API Key"
3. Environment: **Production** (NOT OTE)
4. Name: "SSL Certificate Renewal"
5. **CRITICAL:** Save the credentials immediately (GoDaddy shows them only once!)
   - API Key: `xxxxxxxxx`
   - API Secret: `xxxxxxxxx`

### Step 2: Store Credentials in Secret Manager (3 minutes)
Once you have the GoDaddy credentials, run these commands:

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

# Grant service account access to secrets
gcloud secrets add-iam-policy-binding godaddy-api-key \
  --member="serviceAccount:167154731583-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=smartstakeholdersearch

gcloud secrets add-iam-policy-binding godaddy-api-secret \
  --member="serviceAccount:167154731583-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=smartstakeholdersearch
```

### Step 3: Deploy Cloud Run Job (2 minutes)
After storing credentials, Claude Code can deploy the Cloud Run Job:

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

### Step 4: Test Manual Execution (5-10 minutes)
Test the automation with a manual run:

```bash
gcloud run jobs execute ssl-renewal \
  --region europe-west2 \
  --project smartstakeholdersearch \
  --wait
```

**Important:** This will renew your SSL certificate immediately. Your current certificate will be replaced with a new one.

### Step 5: Create Cloud Scheduler (3 minutes)
Set up automated renewal every 60 days:

```bash
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

---

## 📊 Current System Status

### Certificate Information:
- **Current Certificate:** qualitest-letsencrypt
- **Domain:** qualitest.info
- **Expires:** January 6, 2026 (76 days from now)
- **Manual Renewal Due:** December 7, 2025 (if automation not complete)

### Infrastructure Status:
- **Docker Image:** ✅ Built and ready
- **GCP APIs:** ✅ All enabled
- **Cloud Run Job:** ⏳ Awaiting deployment (needs GoDaddy credentials)
- **Cloud Scheduler:** ⏳ Awaiting creation
- **Production Impact:** ✅ Zero (automation runs separately)

---

## 💡 What Happens Next?

### Option 1: Complete Automation Setup Now
1. Get GoDaddy API credentials (5 minutes)
2. Store credentials in Secret Manager (3 minutes)
3. Let Claude Code deploy the Cloud Run Job and Scheduler (5 minutes)
4. Test with manual execution (10 minutes)
5. **Total Time:** ~25 minutes
6. **Result:** Fully automated SSL renewal, zero maintenance

### Option 2: Wait Until December
- Continue using current Let's Encrypt certificate
- Manual renewal required on December 7, 2025
- Follow steps in `SSL_CERTIFICATE_RENEWAL_REMINDER.md`
- **Total Time:** ~30 minutes on December 7
- **Result:** Certificate renewed but still manual process

---

## 🎯 Recommended Action

**Complete the automation setup now** to:
- ✅ Test the system while you have time (not under pressure)
- ✅ Ensure automation works before December
- ✅ Never worry about SSL renewal again
- ✅ Get a fresh certificate with 90 days validity
- ✅ Only 25 minutes of setup time

---

## 📁 Documentation Files

All setup documentation is available in the `ssl-renewal/` directory:
- `SETUP_INSTRUCTIONS.md` - Detailed step-by-step guide
- `README.md` - Technical documentation
- `SETUP_STATUS.md` - This file (current status)
- `Dockerfile` - Container definition
- `renew.sh` - Renewal script

Backup manual renewal guide:
- `SSL_CERTIFICATE_RENEWAL_REMINDER.md` - Manual renewal process (if automation fails)

---

## 🔗 Quick Links

- **GoDaddy Developer Portal:** https://developer.godaddy.com/keys
- **GCP Console - Cloud Run:** https://console.cloud.google.com/run/jobs?project=smartstakeholdersearch
- **GCP Console - Secret Manager:** https://console.cloud.google.com/security/secret-manager?project=smartstakeholdersearch
- **GCP Console - Cloud Scheduler:** https://console.cloud.google.com/cloudscheduler?project=smartstakeholdersearch

---

## 💰 Cost Summary

**Monthly Cost:** ~$0.36/month (~$4/year)

| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| Cloud Scheduler | 1 job, runs 6x/year | ~$0.10 |
| Cloud Run Job | Runs 5 min, 6x/year | ~$0.20 |
| Secret Manager | 2 secrets | ~$0.06 |
| **Total** | | **~$0.36/month** |

---

## ❓ Questions?

Review the comprehensive setup instructions:
```bash
cat ssl-renewal/SETUP_INSTRUCTIONS.md
```

Or ask Claude Code to help with any step!

---

**Next Action:** Get GoDaddy API credentials and continue with Step 2 above.
