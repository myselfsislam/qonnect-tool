#!/bin/bash
##############################################################################
# Sync Data and Clear Cache - Automated Workflow
#
# This script:
# 1. Syncs data from Google Sheets
# 2. Clears all caches
# 3. Verifies the operation
##############################################################################

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

BASE_URL="https://qualitest.info/smartstakeholdersearch"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Qonnect: Sync Data + Clear Cache Workflow             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Confirmation
echo -e "${YELLOW}⚠️  This will:${NC}"
echo "  1. Sync all data from Google Sheets"
echo "  2. Clear all caches (memory, disk, GCS)"
echo "  3. Force recomputation of all queries"
echo ""
read -p "Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo -e "${RED}✗ Operation cancelled.${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}STEP 1: Syncing from Google Sheets...${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"

SYNC_RESPONSE=$(curl -s -X POST "$BASE_URL/api/sync-google-sheets")
SYNC_SUCCESS=$(echo "$SYNC_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('success', False))" 2>/dev/null)

if [ "$SYNC_SUCCESS" == "True" ]; then
    echo -e "${GREEN}✓ Data sync completed!${NC}"
    echo ""
    echo -e "${YELLOW}Sync Statistics:${NC}"
    echo "$SYNC_RESPONSE" | python3 -m json.tool 2>/dev/null | grep -A 10 "stats" | head -15
    echo ""
else
    echo -e "${RED}✗ Data sync failed!${NC}"
    echo "$SYNC_RESPONSE" | python3 -m json.tool 2>/dev/null
    exit 1
fi

# Wait a moment for sync to settle
sleep 2

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}STEP 2: Clearing all caches...${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"

CLEAR_RESPONSE=$(curl -s -X POST "$BASE_URL/api/clear-cache")
CLEAR_SUCCESS=$(echo "$CLEAR_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('success', False))" 2>/dev/null)

if [ "$CLEAR_SUCCESS" == "True" ]; then
    echo -e "${GREEN}✓ Cache cleared!${NC}"
    echo ""
    echo -e "${YELLOW}Cache Clear Statistics:${NC}"
    echo "$CLEAR_RESPONSE" | python3 -m json.tool 2>/dev/null | grep -A 10 "stats"
    echo ""
else
    echo -e "${RED}✗ Cache clear failed!${NC}"
    echo "$CLEAR_RESPONSE" | python3 -m json.tool 2>/dev/null
    exit 1
fi

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}STEP 3: Verification...${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"

# Check stats
STATS=$(curl -s "$BASE_URL/api/stats")
TOTAL_EMPLOYEES=$(echo "$STATS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('total_employees', 'N/A'))" 2>/dev/null)
GOOGLE_EMPLOYEES=$(echo "$STATS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('google_employees', 'N/A'))" 2>/dev/null)

echo -e "${YELLOW}Current Statistics:${NC}"
echo "  • Total Employees: $TOTAL_EMPLOYEES"
echo "  • Google Employees: $GOOGLE_EMPLOYEES"
echo ""

# Check GCS cache
GCS_COUNT=$(gsutil ls gs://smartstakeholdersearch-data/cache/ 2>&1 | grep -c ".pkl" || echo "0")
echo -e "${YELLOW}GCS Cache Files:${NC} $GCS_COUNT (should be 0 after clear)"
echo ""

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Workflow completed successfully!${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}What happens next:${NC}"
echo "  1. All employee data is fresh from Google Sheets"
echo "  2. First query for each employee will compute fresh (~1-2s)"
echo "  3. Results will be cached and stay fast forever (~0.5s)"
echo "  4. Cache will persist across restarts"
echo ""
echo -e "${GREEN}System is ready for use!${NC}"
echo ""
