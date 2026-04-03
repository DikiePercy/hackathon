#!/bin/bash
# ============================================================================
# Integration Test Script - проверка всех компонентов системы
# ============================================================================

set -e

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║          INTEGRATION TEST - Архив Памяти                             ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

function test_service() {
    local name=$1
    local url=$2
    echo -n "Testing ${name}... "
    
    if curl -f -s -o /dev/null --max-time 5 "${url}"; then
        echo -e "${GREEN}✓${NC}"
        return 0
    else
        echo -e "${RED}✗${NC}"
        return 1
    fi
}

function test_api() {
    local name=$1
    local url=$2
    local expected=$3
    echo -n "Testing ${name}... "
    
    response=$(curl -s --max-time 5 "${url}" || echo "FAILED")
    
    if echo "$response" | grep -q "$expected"; then
        echo -e "${GREEN}✓${NC}"
        return 0
    else
        echo -e "${RED}✗${NC} (got: ${response:0:50})"
        return 1
    fi
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Базовые сервисы"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_service "PostgreSQL" "http://localhost:5432" || echo -e "   ${YELLOW}Hint: Check docker-compose logs db${NC}"
test_api "C++ Backend Health" "http://localhost:8080/health" "status" || echo -e "   ${YELLOW}Hint: docker-compose logs cpp_backend${NC}"
test_api "Python Backend Health" "http://localhost:8000/health" "status" || echo -e "   ${YELLOW}Hint: docker-compose logs python_backend${NC}"
test_service "ChromaDB" "http://localhost:8001" || echo -e "   ${YELLOW}Hint: docker-compose logs vector_db${NC}"
test_service "Frontend" "http://localhost:8501" || echo -e "   ${YELLOW}Hint: docker-compose logs frontend${NC}"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. API Endpoints"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_api "Root Endpoint" "http://localhost:8000/" "backend_python"
test_api "Stats Endpoint" "http://localhost:8000/api/stats" "persons"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. C++ Text Processing"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo -n "Testing C++ /process endpoint... "
response=$(curl -s -X POST http://localhost:8080/process \
    -H "Content-Type: application/json" \
    -d '{"text":"Тестовый документ для проверки. Это второе предложение."}' \
    --max-time 5 || echo "FAILED")

if echo "$response" | grep -q "chunks"; then
    chunks_count=$(echo "$response" | grep -o '"chunks":\[.*\]' | grep -o ',' | wc -l)
    chunks_count=$((chunks_count + 1))
    echo -e "${GREEN}✓${NC} (chunks: ${chunks_count})"
else
    echo -e "${RED}✗${NC}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. Authentication Flow"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Register test user
TEST_USER="test_$(date +%s)"
TEST_PASS="testpass123"

echo -n "Register user... "
register_response=$(curl -s -X POST http://localhost:8000/register \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"${TEST_USER}\",\"password\":\"${TEST_PASS}\"}" \
    --max-time 5 || echo "FAILED")

if echo "$register_response" | grep -q "username"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠${NC} (user may already exist)"
fi

echo -n "Login user... "
login_response=$(curl -s -X POST http://localhost:8000/login \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=${TEST_USER}&password=${TEST_PASS}" \
    --max-time 5 || echo "FAILED")

if echo "$login_response" | grep -q "access_token"; then
    echo -e "${GREEN}✓${NC}"
    TOKEN=$(echo "$login_response" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
else
    echo -e "${RED}✗${NC}"
    TOKEN=""
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. Protected Endpoints (with JWT)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -n "$TOKEN" ]; then
    echo -n "GET /cards... "
    cards_response=$(curl -s http://localhost:8000/cards \
        -H "Authorization: Bearer ${TOKEN}" \
        --max-time 5 || echo "FAILED")
    
    if echo "$cards_response" | grep -q "\["; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Skipped (no token)${NC}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${GREEN}✓${NC} = Working"
echo -e "${YELLOW}⚠${NC} = Warning (may work but check logs)"
echo -e "${RED}✗${NC} = Failed"
echo ""
echo "To view logs: docker-compose logs -f [service_name]"
echo "To restart: docker-compose restart [service_name]"
echo ""
