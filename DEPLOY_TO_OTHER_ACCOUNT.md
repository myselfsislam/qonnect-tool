# 🔐 Deploy to Someone Else's Google Cloud Account

This guide explains how to deploy your Qonnect app to another person's Google Cloud project (e.g., client, company, or friend's account).

---

## 📋 What You Need from the Project Owner

The person who owns the Google Cloud project must give you:

### ✅ **Option A: Their Project ID + Permissions (Recommended)**

**They need to:**
1. Add you as a user to their project
2. Give you the correct permissions
3. Share their Project ID with you

**Permissions you need:**
- `Cloud Run Admin` - To deploy services
- `Cloud Build Editor` - To build containers
- `Service Account User` - To deploy as service account
- `Storage Admin` - For container registry

---

### ✅ **Option B: Service Account Key (Alternative)**

**They can create a service account key and share the JSON file with you.**

This is useful if they don't want to add your personal Google account to their project.

---

## 🎯 Method 1: Deploy Using Their Project (With Permissions)

This is the **recommended** way. You'll use your own Google account but deploy to their project.

### Step 1: Owner Adds You to Their Project

**The project owner must do this:**

1. **Go to:** https://console.cloud.google.com/
2. **Select their project** from the top dropdown
3. **Click hamburger menu (☰)** → **IAM & Admin** → **IAM**
4. **Click "GRANT ACCESS"** or "ADD" button
5. **Enter your email address** (your Gmail)
6. **Add these roles:**
   - `Cloud Run Admin`
   - `Cloud Build Editor`
   - `Service Account User`
   - `Artifact Registry Administrator`
7. **Click "SAVE"**

✅ **You'll receive an email invitation**

### Step 2: Accept Invitation

1. **Check your email** for the invitation
2. **Click the link** in the email
3. **Accept the invitation**

### Step 3: Get the Project ID

**The owner should share their Project ID with you.**

To find it:
1. Go to https://console.cloud.google.com/
2. Click the project dropdown at the top
3. Look for the **Project ID** column (not the project name!)
4. Copy the Project ID (e.g., `my-company-app-12345`)

### Step 4: Deploy to Their Project

**On your Terminal:**

```bash
# 1. Navigate to project folder
cd "/Users/sism/Downloads/Sohail Islam/Personal Projects/qonnect_tool"

# 2. Login with YOUR Google account
gcloud auth login

# 3. Set THEIR project ID (replace with actual ID)
gcloud config set project THEIR-PROJECT-ID

# 4. Verify you're using the correct project
gcloud config get-value project

# 5. Deploy!
gcloud run deploy qonnect-tool \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --timeout 60
```

✅ **The app will deploy to THEIR Google Cloud account!**

---

## 🔑 Method 2: Deploy Using Service Account Key

If they don't want to add your personal account, they can give you a service account key.

### Step 1: Owner Creates Service Account

**The project owner must do this:**

1. **Go to:** https://console.cloud.google.com/iam-admin/serviceaccounts
2. **Select their project**
3. **Click "CREATE SERVICE ACCOUNT"**
4. **Fill in details:**
   - **Name:** `qonnect-deployer`
   - **Description:** `Service account for deploying Qonnect`
5. **Click "CREATE AND CONTINUE"**
6. **Add roles:**
   - `Cloud Run Admin`
   - `Cloud Build Editor`
   - `Service Account User`
   - `Artifact Registry Administrator`
7. **Click "CONTINUE"** then **"DONE"**

### Step 2: Owner Creates Key File

1. **Find the service account** you just created in the list
2. **Click the email address** (e.g., `qonnect-deployer@project-id.iam.gserviceaccount.com`)
3. **Click "KEYS" tab** at the top
4. **Click "ADD KEY"** → **"Create new key"**
5. **Select "JSON"**
6. **Click "CREATE"**

✅ **A JSON file will download automatically** (e.g., `project-id-abc123.json`)

### Step 3: Owner Shares Key File with You

**The owner should send you:**
1. The JSON key file (via secure method - email, Slack, encrypted file share)
2. Their Project ID

**⚠️ SECURITY WARNING:**
- This key file gives full access to deploy to their project
- Keep it secure and don't commit it to GitHub
- Delete it when you're done

### Step 4: You Deploy Using the Key

**On your Terminal:**

```bash
# 1. Navigate to project folder
cd "/Users/sism/Downloads/Sohail Islam/Personal Projects/qonnect_tool"

# 2. Copy the key file to your project folder
# (Let's say they sent you: my-company-key.json)

# 3. Activate the service account
gcloud auth activate-service-account --key-file=my-company-key.json

# 4. Set their project ID
gcloud config set project THEIR-PROJECT-ID

# 5. Verify you're using the correct project
gcloud config get-value project

# 6. Deploy!
gcloud run deploy qonnect-tool \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --timeout 60
```

✅ **The app will deploy to their account using the service account!**

### Step 5: Clean Up (After Deployment)

```bash
# Switch back to your own account
gcloud auth login

# Optional: Revoke the service account
gcloud auth revoke SERVICE_ACCOUNT_EMAIL

# Delete the key file (important for security!)
rm my-company-key.json
```

---

## 🔄 Switching Between Multiple Projects

If you regularly deploy to multiple projects (yours + client's):

### Save Multiple Configurations

```bash
# Create a named configuration for client's project
gcloud config configurations create client-project
gcloud config set project CLIENT-PROJECT-ID
gcloud config set account YOUR-EMAIL@gmail.com

# Create configuration for your own project
gcloud config configurations create my-project
gcloud config set project MY-PROJECT-ID
gcloud config set account YOUR-EMAIL@gmail.com

# List all configurations
gcloud config configurations list

# Switch between them
gcloud config configurations activate client-project
gcloud config configurations activate my-project
```

### Quick Switch Commands

```bash
# See current project
gcloud config get-value project

# Change project (temporary)
gcloud config set project OTHER-PROJECT-ID

# Deploy to specific project (one-time)
gcloud run deploy qonnect-tool \
  --source . \
  --project OTHER-PROJECT-ID \
  --region us-central1
```

---

## 🎯 Method 3: They Give You Console Access Only

If they want you to deploy via the Cloud Console (web interface) instead of Terminal:

### Step 1: Owner Adds You to IAM

Same as Method 1 - they add your email with proper roles.

### Step 2: Deploy via Console

1. **Go to:** https://console.cloud.google.com/run
2. **Select their project** from dropdown at top
3. **Click "CREATE SERVICE"**
4. **Select "Continuously deploy from a repository"** or **"Deploy one revision from source"**
5. **Follow the web UI wizard**

This method is easier but less flexible than using Terminal.

---

## 📊 Who Pays for the Costs?

**Important:** The **project owner** pays for all Cloud Run costs, not you!

- All billing goes to the project owner's credit card
- You're just deploying the app, not paying for it
- Make sure they're aware of potential costs (though free tier is generous)

---

## 🔐 Security Best Practices

### For You (Developer):

✅ **DO:**
- Use Method 1 (IAM permissions) when possible
- Delete service account keys after use
- Never commit keys to GitHub
- Add key files to `.gitignore`

❌ **DON'T:**
- Share service account keys with others
- Commit keys to version control
- Leave keys on your computer after project ends
- Deploy without owner's permission

### For Project Owner:

✅ **DO:**
- Use Method 1 (add developer's email to IAM)
- Give least-privilege access (only needed roles)
- Remove access when project is done
- Monitor Cloud Run deployments

❌ **DON'T:**
- Give Owner or Editor roles (too much access)
- Share service account keys unless necessary
- Leave unused service accounts active

---

## 🧪 Testing Before Deployment

Before deploying to their project, test locally:

```bash
# Test locally first
cd "/Users/sism/Downloads/Sohail Islam/Personal Projects/qonnect_tool"
python app.py

# Visit http://localhost:8080
# Make sure everything works
```

Only deploy to their project when you're sure it works!

---

## 📋 Pre-Deployment Checklist

Before deploying to their account:

- [ ] You have their Project ID
- [ ] You have permissions (Method 1) OR service account key (Method 2)
- [ ] You tested the app locally
- [ ] credentials.json works (Google Sheets API)
- [ ] Dockerfile exists and is correct
- [ ] requirements.txt has all dependencies
- [ ] You confirmed the deployment region with them
- [ ] You know if they want authentication enabled or disabled

---

## 🆘 Common Issues

### Error: "Permission denied"

**Solution:**
- Ask the owner to check IAM permissions
- Make sure you have all 4 required roles
- Try: `gcloud auth login` and re-authenticate

---

### Error: "Project not found"

**Solution:**
- Verify the Project ID (not the project name!)
- Make sure you were added to the project
- Check: `gcloud config get-value project`

---

### Error: "API not enabled"

**Solution:**
- The owner needs to enable these APIs in their project:
  - Cloud Run API
  - Cloud Build API
  - Artifact Registry API
- Go to: https://console.cloud.google.com/apis/library

---

### Error: "Billing not enabled"

**Solution:**
- The owner needs to enable billing on their project
- This requires adding a credit card
- Free tier still applies

---

## 🔄 Updating Their Deployed App

When you need to update the app later:

```bash
# 1. Navigate to project
cd "/Users/sism/Downloads/Sohail Islam/Personal Projects/qonnect_tool"

# 2. Make your code changes
# ... edit files ...

# 3. Set their project
gcloud config set project THEIR-PROJECT-ID

# 4. Redeploy
gcloud run deploy qonnect-tool \
  --source . \
  --region us-central1
```

✅ **New version deployed in 3-5 minutes!**

---

## 🎓 Useful Commands

```bash
# See which account you're using
gcloud auth list

# See which project you're using
gcloud config get-value project

# List all projects you have access to
gcloud projects list

# List services in their project
gcloud run services list --project THEIR-PROJECT-ID

# View their Cloud Run logs
gcloud run services logs read qonnect-tool \
  --project THEIR-PROJECT-ID \
  --region us-central1

# Get their service URL
gcloud run services describe qonnect-tool \
  --project THEIR-PROJECT-ID \
  --region us-central1 \
  --format "value(status.url)"
```

---

## 📄 Template: What to Ask the Project Owner

Copy and send this to the project owner:

```
Hi [Name],

I need access to deploy the Qonnect app to your Google Cloud project.

Please do the following:

1. Go to https://console.cloud.google.com/iam-admin/iam
2. Select your project for Qonnect
3. Click "GRANT ACCESS"
4. Add my email: YOUR-EMAIL@gmail.com
5. Give me these roles:
   - Cloud Run Admin
   - Cloud Build Editor
   - Service Account User
   - Artifact Registry Administrator
6. Click "SAVE"

Also, please send me:
- Your Project ID (found at console.cloud.google.com)
- Which region you prefer (default: us-central1)

After that, I'll be able to deploy the app to your account.

Thanks!
```

---

## ✅ Summary

**Method 1 (Recommended):**
- Owner adds your email to IAM → You deploy with `gcloud`
- **Pros:** Secure, no key files, easy to revoke
- **Cons:** Requires owner to add you to IAM

**Method 2 (Alternative):**
- Owner creates service account key → You deploy with key
- **Pros:** No need to add your personal account
- **Cons:** Key file security risk, harder to manage

**Method 3 (Simple):**
- Owner adds you to IAM → You deploy via Console UI
- **Pros:** No Terminal needed
- **Cons:** Less flexible, harder to automate

**Choose Method 1 unless they have a specific reason not to!**

---

**Need help?** Ask me:
- "The owner gave me this error: [paste error]"
- "How do I find the project ID they're talking about?"
- "Can I deploy to both my account and theirs?"

---

**Last Updated:** 2025-10-01
