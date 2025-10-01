# 🚀 Deploy Qonnect to Google Cloud Run - Complete Beginner's Guide

This guide will help you deploy your Qonnect application to Google Cloud Run step-by-step.

---

## 📋 What You'll Need

Before starting, make sure you have:

1. ✅ **Google Account** - Your Gmail account
2. ✅ **Credit/Debit Card** - For Google Cloud (free tier available, won't charge unless you go over limits)
3. ✅ **This Project** - Already on your computer
4. ✅ **Google Cloud CLI** - Already installed on your Mac ✅

**Estimated Time:** 20-30 minutes
**Cost:** FREE (using Google Cloud Free Tier)

---

## 🎯 Step 1: Set Up Google Cloud Account

### 1.1 Create Google Cloud Project

1. **Go to Google Cloud Console:**
   Open your browser and visit: https://console.cloud.google.com/

2. **Sign in** with your Google account (Gmail)

3. **Accept Terms of Service** (if this is your first time)

4. **Click on the project dropdown** at the top (says "Select a project")

5. **Click "NEW PROJECT"** button (top right)

6. **Fill in project details:**
   - **Project name:** `qonnect-app` (or any name you like)
   - **Organization:** Leave as "No organization"
   - Click **"CREATE"**

7. **Wait 10-15 seconds** for project creation

8. **Select your new project** from the dropdown at the top

✅ **You should now see your project name at the top of the page**

---

## 💳 Step 2: Enable Billing (Free Tier)

Google Cloud Run has a **generous free tier** that should cover your app:
- **2 million requests/month** - FREE
- **180,000 vCPU-seconds/month** - FREE
- **360,000 GiB-seconds/month** - FREE

### 2.1 Set Up Billing Account

1. **Click the hamburger menu** (☰) in the top-left

2. **Click "Billing"**

3. **Click "Link a Billing Account"** or "Create Billing Account"

4. **Enter your credit card details**
   - Don't worry - you won't be charged unless you exceed free tier limits
   - Free tier is very generous for small apps

5. **Complete the billing setup**

✅ **Billing is now enabled for your project**

---

## 🔧 Step 3: Enable Required APIs

You need to enable Cloud Run API and Cloud Build API.

### 3.1 Enable APIs via Console

1. **Click the hamburger menu** (☰) at top-left

2. **Go to "APIs & Services" → "Library"**

3. **Search for "Cloud Run API"**
   - Click on it
   - Click **"ENABLE"**
   - Wait for it to enable (~10 seconds)

4. **Search for "Cloud Build API"**
   - Click on it
   - Click **"ENABLE"**
   - Wait for it to enable (~10 seconds)

5. **Search for "Artifact Registry API"**
   - Click on it
   - Click **"ENABLE"**
   - Wait for it to enable (~10 seconds)

✅ **All required APIs are now enabled**

---

## 🖥️ Step 4: Prepare Your Terminal

Now we'll use the Terminal to deploy your app.

### 4.1 Open Terminal

1. **Press `Cmd + Space`** (Spotlight Search)
2. Type **"Terminal"**
3. Press **Enter**

### 4.2 Navigate to Your Project Folder

```bash
cd "/Users/sism/Downloads/Sohail Islam/Personal Projects/qonnect_tool"
```

### 4.3 Login to Google Cloud

```bash
gcloud auth login
```

**What happens:**
- A browser window will open
- Sign in with your Google account
- Click **"Allow"** to give access
- Return to Terminal

✅ **You should see "You are now logged in"**

### 4.4 Set Your Project

Replace `qonnect-app` with your actual project ID if different:

```bash
gcloud config set project qonnect-app
```

**To find your project ID:**
- Go to https://console.cloud.google.com/
- Look at the top bar - you'll see "Project Info" with the Project ID

✅ **Terminal should confirm: "Updated property [core/project]"**

---

## 🚀 Step 5: Deploy to Cloud Run

Now comes the exciting part - deploying your app!

### 5.1 Run the Deployment Command

Copy and paste this command into Terminal:

```bash
gcloud run deploy qonnect-tool \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --timeout 60 \
  --max-instances 10
```

**What this does:**
- `qonnect-tool` - Name of your service
- `--source .` - Use current folder (your app)
- `--region us-central1` - Deploy to US Central (you can change this)
- `--allow-unauthenticated` - Anyone can access (public website)
- `--port 8080` - Your app runs on port 8080
- `--memory 512Mi` - Allocate 512MB RAM (free tier)
- `--timeout 60` - 60 second timeout for requests
- `--max-instances 10` - Maximum 10 instances running

### 5.2 What Will Happen

You'll see output like this:

```
Building using Dockerfile and deploying container to Cloud Run service [qonnect-tool]...
⠛ Building and deploying...
  ✓ Uploading sources
  ✓ Building Container
  ✓ Creating Revision
  ✓ Routing traffic
Done.
Service [qonnect-tool] revision [qonnect-tool-00001-abc] has been deployed and is serving 100 percent of traffic.
Service URL: https://qonnect-tool-xxxxxxxxx-uc.a.run.app
```

**This will take 3-5 minutes.** You'll see:
1. ⏳ Uploading your code (~30 seconds)
2. ⏳ Building Docker container (~2-3 minutes)
3. ⏳ Deploying to Cloud Run (~30 seconds)

☕ **Grab a coffee and wait...**

### 5.3 Deployment Success

When done, you'll see:

```
✓ Service [qonnect-tool] deployed
Service URL: https://qonnect-tool-xxxxxxxxx-uc.a.run.app
```

✅ **Copy this URL - this is your live app!**

---

## 🎉 Step 6: Test Your Deployment

### 6.1 Open Your App

1. **Copy the Service URL** from the terminal output
2. **Open it in your browser**
3. **You should see your Qonnect app!**

### 6.2 Test the Health Endpoint

Open this URL (replace with your actual URL):

```
https://qonnect-tool-xxxxxxxxx-uc.a.run.app/api/health
```

You should see:
```json
{
  "status": "healthy",
  "data_loaded": true,
  "total_records": 14
}
```

✅ **Your app is live and working!**

---

## 🔧 Step 7: Configure Environment Variables (Important!)

Your app uses Google Sheets API. You need to make sure the credentials are accessible.

### 7.1 Check if credentials.json is deployed

Your `credentials.json` file should already be deployed with your app (it's in your project folder).

### 7.2 Verify in Cloud Console

1. Go to https://console.cloud.google.com/run
2. Click on **"qonnect-tool"** service
3. Click **"EDIT & DEPLOY NEW REVISION"**
4. Scroll down to **"Container"** section
5. Check that your service is running

✅ **If your app loads data, credentials are working!**

---

## 📊 Step 8: Monitor Your App

### 8.1 View Logs

1. Go to https://console.cloud.google.com/run
2. Click on **"qonnect-tool"**
3. Click **"LOGS"** tab
4. See real-time logs of your app

### 8.2 View Metrics

1. Same page, click **"METRICS"** tab
2. See:
   - Request count
   - Request latency
   - Container CPU/Memory usage

---

## ⚡ Step 9: Keep Your App Alive (Prevent Cold Starts)

Google Cloud Run will "sleep" your app after no activity. Here's how to keep it awake:

### 9.1 Set Up Cloud Scheduler (Recommended)

**Option A: Using Console (Easier)**

1. Go to https://console.cloud.google.com/cloudscheduler

2. **Enable Cloud Scheduler API** if prompted

3. Click **"CREATE JOB"**

4. **Fill in details:**
   - **Name:** `keep-qonnect-alive`
   - **Region:** `us-central1` (same as your Cloud Run)
   - **Frequency:** `*/5 * * * *` (every 5 minutes)
   - **Timezone:** Choose your timezone

5. **Click "CONTINUE"**

6. **Configure execution:**
   - **Target type:** HTTP
   - **URL:** `https://qonnect-tool-xxxxxxxxx-uc.a.run.app/api/health` (your app URL + /api/health)
   - **HTTP method:** GET

7. **Click "CONTINUE"** then **"CREATE"**

✅ **Your app will now be pinged every 5 minutes and stay awake!**

**Cost:** FREE (Cloud Scheduler free tier: 3 jobs free)

---

**Option B: Using UptimeRobot (Alternative - Easier)**

1. Go to https://uptimerobot.com/signUp
2. Create free account
3. Add monitor:
   - **URL:** Your Cloud Run URL + `/api/health`
   - **Interval:** 5 minutes
4. Done!

---

## 🎯 Step 10: Update Your App (Future Changes)

When you make code changes, redeploy:

### 10.1 Save Changes to GitHub

```bash
git add .
git commit -m "Your update message"
git push origin main
```

### 10.2 Redeploy to Cloud Run

```bash
cd "/Users/sism/Downloads/Sohail Islam/Personal Projects/qonnect_tool"

gcloud run deploy qonnect-tool \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

✅ **New version deployed in 3-5 minutes!**

---

## 💰 Cost Breakdown (What You'll Pay)

### Free Tier Limits:
- **2 million requests/month** - FREE
- **180,000 vCPU-seconds/month** - FREE
- **360,000 GiB-seconds/month** - FREE
- **Outbound data:** 1 GB/month FREE

### If You Exceed Free Tier (unlikely for small apps):
- **CPU:** $0.00002400/vCPU-second
- **Memory:** $0.00000250/GiB-second
- **Requests:** $0.40 per million requests

**For a small personal app like Qonnect:**
- **Expected cost:** $0/month (stays in free tier)
- **Max cost even with traffic:** $1-5/month

### Cloud Scheduler (Keep-Alive):
- **First 3 jobs:** FREE
- **Additional jobs:** $0.10/job/month

**Total Expected Cost: $0/month** ✅

---

## 🆘 Troubleshooting

### Problem: "Permission denied" error

**Solution:**
```bash
gcloud auth login
gcloud config set project YOUR-PROJECT-ID
```

---

### Problem: "API not enabled"

**Solution:**
Go to https://console.cloud.google.com/apis/library and enable:
- Cloud Run API
- Cloud Build API
- Artifact Registry API

---

### Problem: "credentials.json not found"

**Solution:**
Make sure `credentials.json` is in your project folder:
```bash
ls -la credentials.json
```

---

### Problem: App shows "503 Service Unavailable"

**Solution:**
- Check logs: https://console.cloud.google.com/run
- Click your service → Logs tab
- Look for errors

---

### Problem: "Build failed"

**Solution:**
Check your Dockerfile and requirements.txt are correct:
```bash
cat Dockerfile
cat requirements.txt
```

---

## 🎓 Useful Commands Cheat Sheet

```bash
# View current project
gcloud config get-value project

# List all Cloud Run services
gcloud run services list

# View service details
gcloud run services describe qonnect-tool --region us-central1

# View logs
gcloud run services logs read qonnect-tool --region us-central1

# Delete service (if needed)
gcloud run services delete qonnect-tool --region us-central1

# View billing
gcloud beta billing accounts list
```

---

## 📚 Additional Resources

- **Cloud Run Documentation:** https://cloud.google.com/run/docs
- **Cloud Run Pricing:** https://cloud.google.com/run/pricing
- **Free Tier Details:** https://cloud.google.com/free
- **Cloud Console:** https://console.cloud.google.com/

---

## ✅ Quick Checklist

Before deployment, make sure:

- [ ] Google Cloud account created
- [ ] Billing enabled (credit card added)
- [ ] Cloud Run API enabled
- [ ] Cloud Build API enabled
- [ ] Artifact Registry API enabled
- [ ] gcloud CLI installed and logged in
- [ ] Project ID set in gcloud
- [ ] credentials.json exists in project folder
- [ ] In correct folder: `/Users/sism/Downloads/Sohail Islam/Personal Projects/qonnect_tool`

After deployment:
- [ ] App URL accessible
- [ ] /api/health endpoint working
- [ ] Cloud Scheduler keep-alive configured
- [ ] Monitor logs for errors

---

## 🎉 Success!

Your Qonnect app is now live on Google Cloud Run!

**Your app URL:** `https://qonnect-tool-xxxxxxxxx-uc.a.run.app`

Share this URL with anyone to let them use your app! 🚀

---

**Need Help?**
- Check logs: https://console.cloud.google.com/run
- View metrics: https://console.cloud.google.com/run → Click your service → Metrics
- Ask Claude for help with specific error messages

**Last Updated:** 2025-10-01
