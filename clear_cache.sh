#!/bin/bash
##############################################################################
# Cache Clear Script for Qonnect Production
#
# Usage: ./clear_cache.sh [--local|--prod]
##############################################################################

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default to production
ENVIRONMENT="prod"
BASE_URL="https://qualitest.info/smartstakeholdersearch"

# Parse arguments
if [ "$1" == "--local" ]; then
    ENVIRONMENT="local"
    BASE_URL="http://localhost:8080/smartstakeholdersearch"
elif [ "$1" == "--prod" ]; then
    ENVIRONMENT="prod"
    BASE_URL="https://qualitest.info/smartstakeholdersearch"
fi

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          Qonnect Cache Clear Script                       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Environment:${NC} $ENVIRONMENT"
echo -e "${YELLOW}URL:${NC} $BASE_URL"
echo ""

# Confirmation prompt for production
if [ "$ENVIRONMENT" == "prod" ]; then
    echo -e "${YELLOW}⚠️  WARNING: You are about to clear the PRODUCTION cache!${NC}"
    echo -e "${YELLOW}   This will force recomputation for all cached queries.${NC}"
    echo ""
    read -p "Are you sure you want to continue? (yes/no): " confirmation

    if [ "$confirmation" != "yes" ]; then
        echo -e "${RED}✗ Cache clear cancelled.${NC}"
        exit 0
    fi
    echo ""
fi

# Clear the cache
echo -e "${BLUE}🔄 Clearing cache...${NC}"
RESPONSE=$(curl -s -X POST "$BASE_URL/api/clear-cache")

# Check if request was successful
if [ $? -eq 0 ]; then
    # Parse response
    SUCCESS=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('success', False))" 2>/dev/null)

    if [ "$SUCCESS" == "True" ]; then
        echo -e "${GREEN}✓ Cache cleared successfully!${NC}"
        echo ""
        echo -e "${BLUE}Statistics:${NC}"
        echo "$RESPONSE" | python3 -m json.tool 2>/dev/null | grep -A 10 "stats"
        echo ""

        # Verify GCS cache is cleared (only for prod)
        if [ "$ENVIRONMENT" == "prod" ]; then
            echo -e "${BLUE}🔍 Verifying GCS cache...${NC}"
            GCS_COUNT=$(gsutil ls gs://smartstakeholdersearch-data/cache/ 2>&1 | grep -c ".pkl" || echo "0")
            echo -e "${YELLOW}GCS cache files remaining:${NC} $GCS_COUNT"
            echo ""
        fi

        echo -e "${GREEN}✓ Cache clear completed successfully!${NC}"
        echo ""
        echo -e "${YELLOW}Next Steps:${NC}"
        echo "  1. New queries will be computed fresh and re-cached"
        echo "  2. First request for each employee will be slower (~1-2s)"
        echo "  3. Subsequent requests will be fast (~0.5s) from cache"
        echo ""
    else
        echo -e "${RED}✗ Cache clear failed!${NC}"
        echo -e "${YELLOW}Response:${NC}"
        echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
        exit 1
    fi
else
    echo -e "${RED}✗ Failed to connect to server!${NC}"
    echo -e "${YELLOW}URL:${NC} $BASE_URL/api/clear-cache"
    exit 1
fi

echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
