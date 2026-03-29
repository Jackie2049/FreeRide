#!/usr/bin/env python3
"""
FreeRide Integration Tests

End-to-end tests that require a running server and browser extension.
Run these tests manually after starting the native host and loading the extension.

Usage:
    # Start native host first
    python3 native/native_host.py &

    # Run integration tests
    python3 tests/test_integration.py
"""

import unittest
import json
import urllib.request
import urllib.error
import time
import sys

# Configuration
HOST = "127.0.0.1"
PORT = 8765
BASE_URL = f"http://{HOST}:{PORT}"


def check_server_available():
    """Check if the server is running"""
    try:
        with urllib.request.urlopen(f"{BASE_URL}/status", timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get('status') == 'ok'
    except:
        return False


class IntegrationTestBase(unittest.TestCase):
    """Base class for integration tests"""

    @classmethod
    def setUpClass(cls):
        """Check server availability before running tests"""
        if not check_server_available():
            raise unittest.SkipTest(
                "Server not available. Start native_host.py first."
            )


class TestStatusEndpoint(IntegrationTestBase):
    """Tests for /status endpoint"""

    def test_status_returns_ok(self):
        """Test that /status returns ok"""
        with urllib.request.urlopen(f"{BASE_URL}/status", timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        self.assertEqual(data['status'], 'ok')
        self.assertIn('websocket_clients', data)
        self.assertIn('pending_requests', data)


class TestAskEndpoint(IntegrationTestBase):
    """Tests for /ask endpoint"""

    def test_ask_missing_prompt(self):
        """Test /ask with missing prompt returns error"""
        body = json.dumps({'timeout': 60}).encode('utf-8')
        req = urllib.request.Request(
            f"{BASE_URL}/ask",
            data=body,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            data = json.loads(e.read().decode('utf-8'))

        self.assertFalse(data.get('success', True))

    def test_ask_no_extension(self):
        """Test /ask when extension is not connected"""
        body = json.dumps({
            'prompt': 'Test question',
            'timeout': 5,
            'mode': 'quick'
        }).encode('utf-8')
        req = urllib.request.Request(
            f"{BASE_URL}/ask",
            data=body,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                # If successful, extension is connected
                self.assertIn('success', data)
        except urllib.error.HTTPError as e:
            data = json.loads(e.read().decode('utf-8'))
            # If error, should be about extension not connected
            self.assertFalse(data.get('success', True))
            self.assertIn('extension', data.get('error', '').lower())


class TestSwitchModeEndpoint(IntegrationTestBase):
    """Tests for /switch_mode endpoint"""

    def test_switch_mode_missing_coords(self):
        """Test /switch_mode with missing coordinates"""
        body = json.dumps({'targetMode': 'think'}).encode('utf-8')
        req = urllib.request.Request(
            f"{BASE_URL}/switch_mode",
            data=body,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            data = json.loads(e.read().decode('utf-8'))

        self.assertFalse(data.get('success', True))


class TestCORSSupport(IntegrationTestBase):
    """Tests for CORS support"""

    def test_options_request(self):
        """Test OPTIONS preflight request"""
        req = urllib.request.Request(
            f"{BASE_URL}/ask",
            headers={'Content-Type': 'application/json'},
            method='OPTIONS'
        )

        with urllib.request.urlopen(req, timeout=5) as resp:
            headers = dict(resp.headers)

        self.assertEqual(headers.get('Access-Control-Allow-Origin'), '*')


def run_tests():
    """Run all tests"""
    # Check server availability first
    print("Checking server availability...")
    if not check_server_available():
        print("ERROR: Server not available at", BASE_URL)
        print("Start the server with: python3 native/native_host.py")
        return 1

    print("Server is available. Running tests...\n")

    # Run tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestStatusEndpoint))
    suite.addTests(loader.loadTestsFromTestCase(TestAskEndpoint))
    suite.addTests(loader.loadTestsFromTestCase(TestSwitchModeEndpoint))
    suite.addTests(loader.loadTestsFromTestCase(TestCORSSupport))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
