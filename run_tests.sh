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
    watch)
        echo -e "${BLUE}Running tests in watch mode (auto-rerun on file changes)${NC}"
        echo "Install pytest-watch: pip install pytest-watch"
        ptw tests/ -- -v -m "not integration"
        ;;
    config)
        echo -e "${BLUE}Testing configuration only${NC}"
        pytest tests/ -v -k TestConfig
        ;;
    logging)
        echo -e "${BLUE}Testing logging only${NC}"
        pytest tests/ -v -k TestLogging
        ;;
    k8s)
        echo -e "${BLUE}Testing Kubernetes tools only${NC}"
        pytest tests/ -v -k TestKubernetes
        ;;
    prom)
        echo -e "${BLUE}Testing Prometheus tools only${NC}"
        pytest tests/ -v -k TestPrometheus
        ;;
    quick)
        echo -e "${BLUE}Quick test run (fastest)${NC}"
        pytest tests/ -v -m "not integration" -x
        ;;
    *)
        echo -e "${YELLOW}Usage: ./run_tests.sh [option]${NC}"
        echo ""
        echo "Options:"
        echo "  unit          - Run unit tests only (default)"
        echo "  integration   - Run integration tests only"
        echo "  all           - Run all tests (unit + integration)"
        echo "  coverage      - Run with coverage report"
        echo "  watch         - Run in watch mode (requires pytest-watch)"
        echo "  config        - Test configuration only"
        echo "  logging       - Test logging only"
        echo "  k8s           - Test Kubernetes tools only"
        echo "  prom          - Test Prometheus tools only"
        echo "  quick         - Quick test run (stop on first failure)"
        echo ""
        echo "Examples:"
        echo "  ./run_tests.sh unit       # Run unit tests"
        echo "  ./run_tests.sh all        # Run all tests"
        echo "  ./run_tests.sh coverage   # Run with coverage"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}✓ Tests completed${NC}"

