# SSL Certificate Renewal Reminder
**Certificate Type:** Let's Encrypt (Self-Managed via Certbot)
**Domain:** qualitest.info
**Current Expiry:** January 6, 2026

---

## 📅 Important Dates

### Current Certificate:
```
Issued:          October 8, 2025
Expires:         January 6, 2026
Days Remaining:  76 days (as of October 22, 2025)
```

### Renewal Timeline:
```
✅ NOW (Oct 22)    - Certificate valid, no action needed
⏰ DEC 7, 2025     - START RENEWAL (30 days before expiry)
🚨 JAN 6, 2026     - Certificate expires (DO NOT MISS!)
```

---

## ⚠️ IMPORTANT: Set Calendar Reminder

**ACTION REQUIRED:** Set a calendar reminder for:

📅 **December 7, 2025** (30 days before expiry)
⏰ **Time:** 9:00 AM
📝 **Title:** "Renew SSL Certificate for qualitest.info"
🔔 **Reminder:** 1 day before + day of

---

## 🔄 Renewal Process (When December 7 Arrives)

### Prerequisites:
- Certbot installed on your local machine
- Access to GoDaddy DNS management
- ~30 minutes of time

### Step-by-Step Renewal:

#### 1. Generate New Certificate (15-20 minutes)
```bash
# Run certbot with manual DNS challenge
sudo certbot certonly --manual --preferred-challenges dns -d qualitest.info

# Certbot will provide a DNS TXT record to add
```

#### 2. Add DNS Record in GoDaddy (5 minutes)
```
1. Go to: https://dcc.godaddy.com/manage/qualitest.info/dns
2. Add TXT record:
   - Type: TXT
   - Host: _acme-challenge
   - TXT Value: [Value provided by certbot]
   - TTL: 600 seconds
3. Save and wait 2-5 minutes for DNS propagation
```

#### 3. Complete Certbot Verification (2 minutes)
```bash
# Press Enter in certbot to verify
# Certbot will verify DNS and issue certificate

# Certificate files will be saved to:
# /etc/letsencrypt/live/qualitest.info/fullchain.pem
# /etc/letsencrypt/live/qualitest.info/privkey.pem
```

#### 4. Upload to GCP (5 minutes)
```bash
# Create new certificate in GCP
gcloud compute ssl-certificates create qualitest-letsencrypt-new \
  --certificate=/etc/letsencrypt/live/qualitest.info/fullchain.pem \
  --private-key=/etc/letsencrypt/live/qualitest.info/privkey.pem \
  --project=smartstakeholdersearch \
  --global

# Update HTTPS proxy to use new certificate
gcloud compute target-https-proxies update qualitest-https-proxy \
  --ssl-certificates=qualitest-letsencrypt-new \
  --project=smartstakeholdersearch \
  --global

# Wait 2-3 minutes for propagation
```

#### 5. Verify New Certificate (2 minutes)
```bash
# Test production URLs
curl -I https://qualitest.info/smartstakeholdersearch/

# Check certificate details
echo | openssl s_client -servername qualitest.info \
  -connect qualitest.info:443 2>/dev/null | \
  openssl x509 -noout -dates

# Should show new expiry date: ~April 2026
```

#### 6. Cleanup Old Certificate (1 minute)
```bash
# After confirming new certificate works, delete old one
gcloud compute ssl-certificates delete qualitest-letsencrypt \
  --project=smartstakeholdersearch \
  --global

# Rename new certificate (optional)
# You can keep the name as is, or rename for consistency
```

---

## 🚨 What Happens If You Miss Renewal?

### Before Expiry (Dec 7 - Jan 6):
- ✅ Production continues working normally
- ⏰ You have 30 days to renew
- 🟡 No user impact yet

### On Expiry Day (Jan 6, 2026):
- ❌ Certificate expires
- 🔴 Users see "Your connection is not private" warnings
- 🔴 All HTTPS traffic blocked
- 🔴 Production site inaccessible
- 💰 Business impact: 100% downtime

### After Expiry:
- 🚨 Emergency renewal required
- ⏱️ Same process, but under time pressure
- 😰 Stressful situation

**DON'T LET THIS HAPPEN!** Renew by December 7, 2025.

---

## 📧 Email Reminders from Let's Encrypt

Let's Encrypt will send renewal reminder emails to:
- **Email:** myselfsohailislam@gmail.com (if registered with certbot)

**Expected emails:**
- 30 days before expiry (Dec 7, 2025)
- 14 days before expiry (Dec 23, 2025)
- 7 days before expiry (Dec 30, 2025)
- 3 days before expiry (Jan 3, 2026)

**Don't ignore these emails!**

---

## 💡 Pro Tips

### Before Renewal Day:
1. ✅ Ensure certbot is installed and working
2. ✅ Have GoDaddy login credentials ready
3. ✅ Test certbot with `certbot --version`
4. ✅ Review this document

### During Renewal:
1. ✅ Do it during low-traffic hours (early morning)
2. ✅ Have 30 minutes uninterrupted time
3. ✅ Don't rush the DNS propagation wait
4. ✅ Test thoroughly before deleting old certificate

### After Renewal:
1. ✅ Update this document with new expiry date
2. ✅ Set next reminder for 90 days later
3. ✅ Keep certbot certificate files backed up

---

## 🔧 Troubleshooting

### Problem: Certbot not installed
```bash
# Install certbot (macOS)
brew install certbot

# Install certbot (Ubuntu/Debian)
sudo apt-get install certbot

# Install certbot (CentOS/RHEL)
sudo yum install certbot
```

### Problem: DNS verification fails
- Wait longer (up to 10 minutes) for DNS propagation
- Verify TXT record exists: `dig _acme-challenge.qualitest.info TXT`
- Check you added the exact value certbot provided

### Problem: Certificate upload fails
- Check file paths are correct
- Ensure you have `gcloud` configured and authenticated
- Verify you have Owner/Editor role in GCP project

### Problem: Production stops working after update
```bash
# Rollback to old certificate immediately
gcloud compute target-https-proxies update qualitest-https-proxy \
  --ssl-certificates=qualitest-letsencrypt \
  --project=smartstakeholdersearch \
  --global

# Production restored in 1-2 minutes
```

---

## 📊 Certificate History

### Current Certificate (Active):
```
Certificate Name:  qualitest-letsencrypt
Issued:            October 8, 2025
Expires:           January 6, 2026
Renewal Status:    ⏰ Due December 7, 2025
```

### Previous Certificates:
```
(Add history as you renew)

Certificate 1:
  Issued: [Date]
  Expired: [Date]
  Renewed on: [Date]
```

---

## 📞 Emergency Contacts

If you need help during renewal:

**GCP Support:**
- Console: https://console.cloud.google.com/support
- Project: smartstakeholdersearch

**Let's Encrypt Support:**
- Community: https://community.letsencrypt.org
- Documentation: https://letsencrypt.org/docs

**DNS (GoDaddy):**
- Support: https://www.godaddy.com/help
- DNS Management: https://dcc.godaddy.com

---

## ✅ Checklist for Renewal Day

**Before Starting:**
- [ ] Certbot installed and working
- [ ] GoDaddy login credentials ready
- [ ] 30 minutes of uninterrupted time
- [ ] This document reviewed

**During Renewal:**
- [ ] Run certbot command
- [ ] Add DNS TXT record in GoDaddy
- [ ] Wait for DNS propagation (2-5 min)
- [ ] Complete certbot verification
- [ ] Upload certificate to GCP
- [ ] Update HTTPS proxy
- [ ] Wait for propagation (2-3 min)

**After Renewal:**
- [ ] Test all production URLs
- [ ] Verify certificate expiry date
- [ ] Delete old certificate
- [ ] Update this document
- [ ] Set next renewal reminder (April 2026)

---

## 🎯 Summary

**What:** SSL Certificate Renewal for qualitest.info
**When:** December 7, 2025 (30 days before expiry)
**How Long:** ~30 minutes
**Impact:** Minimal (2-3 minutes during certificate switch)
**Cost:** $0 (Let's Encrypt is free)

**Most Important:**
🚨 **DO NOT MISS DECEMBER 7, 2025 RENEWAL DATE!** 🚨

---

**Document Created:** October 22, 2025
**Next Review:** December 7, 2025
**Renewal Due:** December 7, 2025
**Certificate Expires:** January 6, 2026

---

## 🔮 Future Consideration

**Note:** We attempted Google-managed SSL (auto-renewal) on October 22, 2025, but it failed due to domain validation issues. If you want to try again in the future:

**Requirements for Google-managed SSL:**
- HTTP (port 80) must be accessible
- Domain must respond to Google's validation requests
- Can take 15-60 minutes to provision

**Benefits if it works:**
- ✅ Automatic renewal every 90 days
- ✅ Zero maintenance
- ✅ No certbot needed

**For now:** Stick with Let's Encrypt manual renewal (proven and working).
