#!/bin/bash
# Quick test runner for KubeMedic
# Usage: ./run_tests.sh [option]

set -e

echo "================================"
echo "KubeMedic Test Suite"
echo "================================"
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default command
CMD=${1:-"unit"}

case $CMD in
    unit)
        echo -e "${BLUE}Running unit tests (no external dependencies)${NC}"
        pytest tests/ -v -m "not integration"
        ;;
    integration)
        echo -e "${BLUE}Running integration tests (requires .env + services)${NC}"
        pytest tests/ -v -m integration
        ;;
    all)
        echo -e "${BLUE}Running all tests (unit + integration)${NC}"
        pytest tests/ -v
        ;;
    coverage)
        echo -e "${BLUE}Running tests with coverage report${NC}"
        pytest tests/ -v --cov=src/kube_medic --cov-report=html --cov-report=term
        echo -e "${GREEN}Coverage report generated: htmlcov/index.html${NC}"
        ;;
    help)
        echo -e "${YELLOW}Usage: ./run_tests.sh [option]${NC}"
        echo ""
        echo "Options:"
        echo "  unit          - Run unit tests only (default)"
        echo "  integration   - Run integration tests only"
        echo "  all           - Run all tests (unit + integration)"
        echo "  coverage      - Run with coverage report"
        echo "Examples:"
        echo "  ./run_tests.sh unit       # Run unit tests"
        echo "  ./run_tests.sh all        # Run all tests"
        echo "  ./run_tests.sh coverage   # Run with coverage"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}✓ Tests completed${NC}"

