#!/bin/bash

# vMCP Test Suite Runner
# ======================
# Leverages pytest configuration from pyproject.toml

set -e  # Exit on error

echo "════════════════════════════════════════════════════════════════"
echo "  vMCP Backend Test Suite"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if servers are running
check_server() {
    local url=$1
    local name=$2

    echo -e "${BLUE}Checking ${name}...${NC}"
    if curl -s -f -o /dev/null "${url}"; then
        echo -e "${GREEN}✓ ${name} is running${NC}"
        return 0
    else
        echo -e "${RED}✗ ${name} is not running at ${url}${NC}"
        return 1
    fi
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1: Server Availability Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check all required servers
SERVERS_OK=true

check_server "http://localhost:8000/health" "vMCP Backend Server" || SERVERS_OK=false
check_server "http://localhost:8001/everything/mcp" "Everything MCP Server" || SERVERS_OK=false
check_server "http://localhost:8001/allfeature/mcp" "AllFeature MCP Server" || SERVERS_OK=false
check_server "http://localhost:8002/health" "Test HTTP Server" || SERVERS_OK=false

echo ""

if [ "$SERVERS_OK" = false ]; then
    echo -e "${RED}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}ERROR: Not all required servers are running!${NC}"
    echo -e "${RED}════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Please start the required servers:"
    echo "  1. vMCP Backend Server (port 8000)"
    echo "  2. Everything MCP Server (port 8001)"
    echo "  3. AllFeature MCP Server (port 8001)"
    echo "  4. Test HTTP Server (port 8002)"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓ All servers are running!${NC}"
echo ""

# Navigate to backend directory
cd "$(dirname "$0")/.."

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2: Running Tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Pass all arguments to pytest (configured via pyproject.toml)
echo "Command: uv run pytest $@"
echo ""

uv run pytest "$@"

TEST_RESULT=$?

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3: Test Results"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ $TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}✓✓✓ ALL TESTS PASSED! ✓✓✓${NC}"
else
    echo -e "${RED}✗✗✗ SOME TESTS FAILED! ✗✗✗${NC}"
fi

echo ""
echo -e "${GREEN}Coverage and test reports generated:${NC}"
echo "  - HTML Coverage: htmlcov/index.html"
echo "  - Test Report: test_reports/results.html"
echo "  - XML Coverage: coverage.xml"
echo ""
echo "Open reports:"
echo "  open htmlcov/index.html"
echo "  open test_reports/results.html"
echo ""

echo "════════════════════════════════════════════════════════════════"
echo "  Test Suite Complete"
echo "════════════════════════════════════════════════════════════════"

exit $TEST_RESULT
