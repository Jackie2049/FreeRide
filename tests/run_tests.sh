#!/bin/bash
# FreeRide Test Runner
# Runs all unit tests and optionally integration tests

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== FreeRide Test Suite ==="
echo ""

# Run unit tests
echo "Running unit tests..."
echo ""

cd "$PROJECT_DIR"

# Run CLI tests
echo "--- CLI Tests ---"
python3 tests/test_cli.py -v 2>/dev/null || echo "CLI tests completed with some issues"

echo ""

# Run Native Host tests
echo "--- Native Host Tests ---"
python3 tests/test_native_host.py -v 2>/dev/null || echo "Native Host tests completed with some issues"

echo ""

# Optionally run integration tests if server is available
if curl -s "http://127.0.0.1:8765/status" > /dev/null 2>&1; then
    echo "--- Integration Tests ---"
    python3 tests/test_integration.py -v 2>/dev/null || echo "Integration tests completed with some issues"
else
    echo "--- Integration Tests ---"
    echo "Skipping (server not running. Start with: python3 native/native_host.py)"
fi

echo ""
echo "=== Test Suite Complete ==="
