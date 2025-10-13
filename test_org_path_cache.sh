#!/bin/bash

# Test organizational path caching performance
# Tests the fix for 8-10s repeated query issue

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BASE_URL="${1:-http://127.0.0.1:8080/smartstakeholdersearch}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Organizational Path Caching Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Testing URL: $BASE_URL"
echo ""

# Test Case 1: mellferrier -> andrewromeo
echo -e "${YELLOW}Test 1: mellferrier → andrewromeo${NC}"
echo "---"

echo -e "${BLUE}First request (uncached):${NC}"
time curl -s "$BASE_URL/api/organizational-path/mellferrier/andrewromeo" > /tmp/test1.json
RESULT1=$(cat /tmp/test1.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"✓ intermediateCount: {data.get('intermediateCount', 'N/A')}, path length: {len(data.get('path', []))}\")")
echo "$RESULT1"
echo ""

echo -e "${BLUE}Second request (cached - should be MUCH faster):${NC}"
time curl -s "$BASE_URL/api/organizational-path/mellferrier/andrewromeo" > /tmp/test2.json
RESULT2=$(cat /tmp/test2.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"✓ intermediateCount: {data.get('intermediateCount', 'N/A')}, path length: {len(data.get('path', []))}\")")
echo "$RESULT2"
echo ""

echo -e "${BLUE}Third request (cached - should still be fast):${NC}"
time curl -s "$BASE_URL/api/organizational-path/mellferrier/andrewromeo" > /tmp/test3.json
RESULT3=$(cat /tmp/test3.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"✓ intermediateCount: {data.get('intermediateCount', 'N/A')}, path length: {len(data.get('path', []))}\")")
echo "$RESULT3"
echo ""

# Test Case 2: mellferrier -> himanis
echo -e "${YELLOW}Test 2: mellferrier → himanis${NC}"
echo "---"

echo -e "${BLUE}First request (uncached):${NC}"
time curl -s "$BASE_URL/api/organizational-path/mellferrier/himanis" > /tmp/test4.json
RESULT4=$(cat /tmp/test4.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"✓ intermediateCount: {data.get('intermediateCount', 'N/A')}, path length: {len(data.get('path', []))}\")")
echo "$RESULT4"
echo ""

echo -e "${BLUE}Second request (cached):${NC}"
time curl -s "$BASE_URL/api/organizational-path/mellferrier/himanis" > /tmp/test5.json
RESULT5=$(cat /tmp/test5.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"✓ intermediateCount: {data.get('intermediateCount', 'N/A')}, path length: {len(data.get('path', []))}\")")
echo "$RESULT5"
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ All tests completed!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Expected behavior:"
echo "  - First request: 0.1-0.5s (local) or 1-3s (prod, first time)"
echo "  - Cached requests: 0.01-0.05s (10-50ms) - much faster!"
echo ""
echo "Before the fix: Every request took 8-10s"
echo "After the fix: Only first request is slow, rest are <50ms"
