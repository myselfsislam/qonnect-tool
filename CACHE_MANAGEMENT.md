# Cache Management Guide

## Overview

The Qonnect application uses a **permanent 3-layer cache** that never expires automatically:
1. **Memory Cache** (1 hour) - Fastest, in-process
2. **Disk Cache** (permanent) - Fast, survives within container lifetime
3. **GCS Cache** (permanent) - Persistent across restarts, deployments, scaling

## 🎯 Quick Start

### Clear Production Cache
```bash
curl -X POST https://qualitest.info/smartstakeholdersearch/api/clear-cache
```

### Using Scripts (Recommended)
```bash
# Clear cache only
./clear_cache.sh --prod

# Sync data + clear cache (complete workflow)
./sync_and_clear.sh
```

---

## 📋 Available Scripts

### 1. `clear_cache.sh` - Clear Cache Only

Clears all caches (memory, disk, GCS) without syncing data.

**Usage:**
```bash
# Production (with confirmation)
./clear_cache.sh --prod

# Local development
./clear_cache.sh --local

# Default is production
./clear_cache.sh
```

**When to use:**
- After manual data changes in Google Sheets
- When you want to force recomputation
- Testing cache behavior

### 2. `sync_and_clear.sh` - Complete Workflow

Syncs from Google Sheets AND clears cache in one operation.

**Usage:**
```bash
./sync_and_clear.sh
```

**Workflow:**
1. ✅ Syncs all data from Google Sheets
2. ✅ Waits for sync to complete
3. ✅ Clears all caches
4. ✅ Verifies operation
5. ✅ Shows statistics

**When to use:**
- Weekly/monthly data refresh
- After bulk updates to Google Sheets
- Regular maintenance windows

---

## 📅 When to Clear Cache

### ✅ **REQUIRED** - Clear cache when:

1. **Employee Data Changes**
   - New hires added
   - Employees leave organization
   - Role/title changes
   - Manager assignments change
   - Team/department changes

2. **Connection Data Changes**
   - New declared connections added
   - Existing connections modified
   - Connections removed or deleted

3. **Organizational Structure Changes**
   - Reporting lines change
   - Department reorganization
   - Location/office changes

4. **After Syncing from Google Sheets**
   - If you manually sync via `/api/sync-google-sheets`
   - After bulk data updates

### ❌ **NOT REQUIRED** - Don't clear cache for:

1. **Regular application restarts**
   - Cache persists in GCS automatically

2. **Cloud Run scaling/deployments**
   - Cache loads from GCS seamlessly

3. **Minor data corrections**
   - If changes don't affect relationships

4. **UI/frontend changes**
   - Cache is backend data only

---

## 🔄 Recommended Workflows

### Workflow 1: Weekly Maintenance (Recommended)

```bash
# Every Monday morning
cd "/path/to/qonnect-tool"
./sync_and_clear.sh
```

**Schedule:** Weekly or bi-weekly

### Workflow 2: On-Demand Refresh

```bash
# When you know data has changed
curl -X POST https://qualitest.info/smartstakeholdersearch/api/clear-cache
```

**Trigger:** After specific data changes

### Workflow 3: Automated (Optional)

Set up a cron job or Cloud Scheduler:

```bash
# Cron job (runs every Sunday at 2 AM)
0 2 * * 0 cd /path/to/qonnect-tool && ./sync_and_clear.sh >> /var/log/qonnect-sync.log 2>&1
```

---

## 📊 Understanding Cache Behavior

### Cache Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                    First Query for Employee                  │
│                                                              │
│  1. Check Memory Cache     ❌ Not found                     │
│  2. Check Disk Cache       ❌ Not found                     │
│  3. Check GCS Cache        ❌ Not found                     │
│  4. Compute (1-2 seconds)  ✅ Calculate connections         │
│  5. Save to all 3 layers   ✅ Memory + Disk + GCS           │
│                                                              │
│  Result: ~1-2s response time                                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│               All Subsequent Queries (Forever!)              │
│                                                              │
│  1. Check Memory Cache     ✅ Found!                        │
│     (or Disk/GCS if memory expired)                          │
│                                                              │
│  Result: ~0.5s response time FOREVER                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    After Container Restart                   │
│                                                              │
│  1. Check Memory Cache     ❌ Empty (new container)         │
│  2. Check Disk Cache       ❌ Empty (/tmp cleared)          │
│  3. Check GCS Cache        ✅ Found! Load from GCS          │
│  4. Populate Memory+Disk   ✅ Warm up local caches          │
│                                                              │
│  Result: ~0.5s response time (GCS load + warmup)             │
└─────────────────────────────────────────────────────────────┘
```

### Performance Expectations

| Scenario | First Request | Cached Requests | Duration |
|----------|--------------|-----------------|----------|
| **New Employee** | 1-2s (compute) | 0.5s (cache) | Forever |
| **After Cache Clear** | 1-2s (compute) | 0.5s (cache) | Forever |
| **After Restart** | 0.5s (GCS load) | 0.5s (cache) | Forever |
| **Normal Operation** | 0.5s (cache) | 0.5s (cache) | Forever |

---

## 🔍 Monitoring Cache Health

### Check Cache Size
```bash
# GCS cache size
gsutil du -sh gs://smartstakeholdersearch-data/cache/

# Count cached items
gsutil ls gs://smartstakeholdersearch-data/cache/ | wc -l
```

### View Cache Statistics
```bash
# Using clear cache endpoint (doesn't actually clear)
curl -s -X POST https://qualitest.info/smartstakeholdersearch/api/clear-cache | python3 -m json.tool
```

**Response shows:**
```json
{
  "success": true,
  "stats": {
    "memory_connections_cleared": 15,
    "memory_hierarchy_cleared": 12,
    "disk_files_cleared": 25,
    "gcs_files_cleared": 10
  }
}
```

### Application Statistics
```bash
# View app stats
curl -s https://qualitest.info/smartstakeholdersearch/api/stats | python3 -m json.tool
```

---

## 🛠️ Troubleshooting

### Issue: Stale Data Showing

**Symptoms:** Users see old connection data or outdated employee info

**Solution:**
```bash
./sync_and_clear.sh
```

### Issue: Slow Responses

**Symptoms:** All queries are slow (1-2s+)

**Diagnosis:**
```bash
# Check if cache is empty
gsutil ls gs://smartstakeholdersearch-data/cache/ | wc -l
```

**Solution:**
- Cache is empty - queries will populate it naturally
- Cache is full but slow - check Cloud Run logs for errors

### Issue: Cache Growing Too Large

**Symptoms:** GCS cache > 100 MB

**Check size:**
```bash
gsutil du -sh gs://smartstakeholdersearch-data/cache/
```

**Solution (if needed):**
```bash
# Nuclear option: delete everything and rebuild
gsutil -m rm -r gs://smartstakeholdersearch-data/cache/**
./clear_cache.sh --prod
```

**Note:** Even 1000 employees = only ~6 MB. This should rarely be needed.

---

## 💰 Cost Implications

### Current Cache Costs

| Scenario | Storage | Operations | Total/Month |
|----------|---------|------------|-------------|
| 100 employees | ~0.6 MB | ~100 ops | $0.00 |
| 500 employees | ~3 MB | ~500 ops | $0.01 |
| 1000 employees | ~6 MB | ~1000 ops | $0.02 |
| 5000 queries | ~30 MB | ~5000 ops | $0.03 |

**Verdict:** Negligible cost, massive performance benefit!

---

## 🎯 Best Practices

### ✅ DO

1. **Clear cache after syncing** from Google Sheets
2. **Use `sync_and_clear.sh`** for regular maintenance
3. **Monitor cache size** monthly (should stay < 10 MB)
4. **Test in staging** before production (use `--local` flag)
5. **Document data changes** that require cache clear

### ❌ DON'T

1. **Don't clear cache unnecessarily** - hurts performance
2. **Don't clear during peak hours** - causes slow loads
3. **Don't forget to clear after bulk updates** - causes stale data
4. **Don't manually delete GCS files** - use the endpoint
5. **Don't assume cache auto-expires** - it's permanent!

---

## 📞 Support

### Cache Management Commands Cheat Sheet

```bash
# Quick clear (production)
curl -X POST https://qualitest.info/smartstakeholdersearch/api/clear-cache

# Safe clear with confirmation
./clear_cache.sh --prod

# Complete workflow (sync + clear)
./sync_and_clear.sh

# Check cache size
gsutil du -sh gs://smartstakeholdersearch-data/cache/

# Count cache files
gsutil ls gs://smartstakeholdersearch-data/cache/ | wc -l

# View application stats
curl -s https://qualitest.info/smartstakeholdersearch/api/stats

# View recent logs
gcloud logging read "resource.type=cloud_run_revision AND textPayload=~'cache'" --limit=20
```

---

## 🔐 Security Notes

- `/api/clear-cache` endpoint is **NOT authenticated** currently
- Anyone with the URL can clear cache
- Consider adding authentication if needed (future enhancement)
- Cache contains employee relationship data (not sensitive)

---

## 📝 Change Log

### Version 2.0 (2025-10-13)
- ✅ Made cache permanent (no TTL expiry)
- ✅ Added `/api/clear-cache` endpoint
- ✅ Created `clear_cache.sh` script
- ✅ Created `sync_and_clear.sh` workflow script
- ✅ 3-layer caching with GCS persistence

### Version 1.0 (2025-10-10)
- Initial GCS cache implementation
- 1-week TTL (deprecated)
- Basic disk caching

---

**Last Updated:** 2025-10-13
**Maintainer:** Sohail Islam
**Environment:** Production (qualitest.info)
