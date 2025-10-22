# Automated SSL Certificate Renewal

**Fully automated SSL certificate renewal using GCP Cloud Scheduler + Cloud Run**

## Overview

This system automatically renews your Let's Encrypt SSL certificate every 60 days using:
- **Certbot** with GoDaddy DNS plugin
- **GCP Cloud Run Job** (runs the renewal)
- **GCP Cloud Scheduler** (triggers every 60 days)
- **GCP Secret Manager** (stores GoDaddy API credentials securely)

**Cost:** ~$0.36/month (~$4/year)
**Maintenance:** Zero (fully automated)

---

## Architecture

```
Cloud Scheduler (every 60 days)
    ↓
Triggers Cloud Run Job
    ↓
Docker Container with Certbot runs
    ↓
Uses GoDaddy DNS API for domain validation
    ↓
Gets new certificate from Let's Encrypt
    ↓
Uploads to GCP Load Balancer
    ↓
Updates HTTPS proxy
    ↓
Deletes old certificates
    ↓
Done!
```

---

## Setup Steps

### Step 1: Get GoDaddy API Credentials

1. Go to: https://developer.godaddy.com/keys
2. Click "Create New API Key"
3. Environment: **Production**
4. Save the credentials:
   - API Key: `xxxxxxxxx`
   - API Secret: `xxxxxxxxx`

**⚠️ IMPORTANT:** Save these immediately - GoDaddy shows the secret only once!

### Step 2: Store Credentials in GCP Secret Manager

```bash
# Enable Secret Manager API
gcloud services enable secretmanager.googleapis.com \
  --project=smartstakeholdersearch

# Create secrets for GoDaddy API credentials
echo -n "YOUR_GODADDY_API_KEY" | \
  gcloud secrets create godaddy-api-key \
  --project=smartstakeholdersearch \
  --replication-policy="automatic" \
  --data-file=-

echo -n "YOUR_GODADDY_API_SECRET" | \
  gcloud secrets create godaddy-api-secret \
  --project=smartstakeholdersearch \
  --replication-policy="automatic" \
  --data-file=-
```

### Step 3: Build and Deploy Cloud Run Job

```bash
# Navigate to ssl-renewal directory
cd ssl-renewal

# Build and deploy using Cloud Build
gcloud builds submit --tag gcr.io/smartstakeholdersearch/ssl-renewal .

# Deploy as Cloud Run Job
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

### Step 4: Test the Job Manually

```bash
# Execute the job manually to test
gcloud run jobs execute ssl-renewal \
  --region europe-west2 \
  --project smartstakeholdersearch \
  --wait

# View logs
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=ssl-renewal" \
  --limit=50 \
  --project=smartstakeholdersearch \
  --format=json
```

### Step 5: Set Up Cloud Scheduler

```bash
# Enable Cloud Scheduler API
gcloud services enable cloudscheduler.googleapis.com \
  --project=smartstakeholdersearch

# Create schedule (runs every 60 days at 2 AM)
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

## Monitoring

### Check Scheduler Status
```bash
gcloud scheduler jobs list \
  --location=europe-west2 \
  --project=smartstakeholdersearch
```

### View Job Execution History
```bash
gcloud run jobs executions list \
  --job=ssl-renewal \
  --region=europe-west2 \
  --project=smartstakeholdersearch
```

### View Logs
```bash
gcloud logging read "resource.type=cloud_run_job" \
  --limit=100 \
  --project=smartstakeholdersearch
```

---

## Manual Renewal (If Needed)

If you ever need to manually trigger renewal:

```bash
gcloud run jobs execute ssl-renewal \
  --region=europe-west2 \
  --project=smartstakeholdersearch \
  --wait
```

---

## Cost Breakdown

| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| Cloud Scheduler | 1 job, runs 6x/year | ~$0.10 |
| Cloud Run Job | Runs 5 min, 6x/year | ~$0.20 |
| Secret Manager | 2 secrets | ~$0.06 |
| **Total** | | **~$0.36/month** |

**Annual cost:** ~$4.32/year

---

## Troubleshooting

### Job Fails with "Invalid GoDaddy credentials"
- Verify secrets are set correctly
- Check API key is for Production (not OTE)
- Regenerate GoDaddy API key if needed

### Job Fails with "DNS validation timeout"
- GoDaddy DNS propagation can take 2-5 minutes
- Script waits 120 seconds by default
- Check GoDaddy API access is working

### Certificate Not Updating on Load Balancer
- Check IAM permissions for service account
- Verify HTTPS proxy name is correct
- Check logs for specific error message

---

## Security

- ✅ GoDaddy API credentials stored in Secret Manager (encrypted)
- ✅ Service account has minimal required permissions
- ✅ Credentials never logged or exposed
- ✅ Sensitive files deleted after use
- ✅ All communications over HTTPS

---

## Files

- `Dockerfile` - Container image definition
- `renew.sh` - Renewal script
- `README.md` - This file

---

## Maintenance

**None required!** The system runs automatically every 60 days.

### Optional: Update Schedule

To change renewal frequency:

```bash
# Example: Every 45 days
gcloud scheduler jobs update http ssl-renewal-scheduler \
  --location=europe-west2 \
  --schedule="0 2 */45 * *" \
  --project=smartstakeholdersearch
```

---

## Rollback

If you want to stop automation:

```bash
# Pause scheduler
gcloud scheduler jobs pause ssl-renewal-scheduler \
  --location=europe-west2 \
  --project=smartstakeholdersearch

# Delete scheduler (if removing completely)
gcloud scheduler jobs delete ssl-renewal-scheduler \
  --location=europe-west2 \
  --project=smartstakeholdersearch

# Delete Cloud Run job
gcloud run jobs delete ssl-renewal \
  --region=europe-west2 \
  --project=smartstakeholdersearch
```

---

## Next Renewal

The scheduler is set to run every 60 days at 2:00 AM IST.

**First automated renewal:** Approximately 60 days after setup.

You'll receive an email notification if renewal fails.

---

**Setup Date:** October 23, 2025
**Renewal Frequency:** Every 60 days
**Next Manual Renewal:** Not needed (automated!)
