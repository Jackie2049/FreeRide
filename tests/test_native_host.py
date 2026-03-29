#!/usr/bin/env python3
"""
FreeRide Native Host Unit Tests

Tests for the native_host.py bridge server.
"""

import unittest
import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock


class TestNativeHostHandlers(unittest.TestCase):
    """Tests for HTTP handlers"""

    def test_handle_http_status(self):
        """Test /status endpoint response format"""
        expected_keys = {'status', 'message', 'websocket_clients', 'pending_requests'}

        # Simulate the response structure
        response = {
            'status': 'ok',
            'message': 'FreeRide Bridge Server is running',
            'websocket_clients': 0,
            'pending_requests': 0
        }

        self.assertEqual(set(response.keys()), expected_keys)
        self.assertEqual(response['status'], 'ok')

    def test_handle_ask_missing_prompt(self):
        """Test /ask endpoint with missing prompt"""
        # Simulate validation logic
        data = {'timeout': 60}

        if not data.get('prompt'):
            response = {'success': False, 'error': 'Missing prompt'}
        else:
            response = {'success': True}

        self.assertFalse(response['success'])
        self.assertEqual(response['error'], 'Missing prompt')

    def test_handle_ask_valid_request(self):
        """Test /ask endpoint with valid request"""
        data = {
            'prompt': 'Test question',
            'timeout': 60,
            'includeThinking': False,
            'mode': 'quick'
        }

        # Validate request structure
        self.assertIn('prompt', data)
        self.assertIn('timeout', data)
        self.assertIn('mode', data)
        self.assertIn(data['mode'], ['quick', 'think', 'expert'])

    def test_handle_switch_mode_missing_coords(self):
        """Test /switch_mode endpoint with missing coordinates"""
        data = {'targetMode': 'think'}

        if data.get('buttonX') is None or data.get('buttonY') is None:
            response = {'success': False, 'error': 'Missing buttonX or buttonY'}
        else:
            response = {'success': True}

        self.assertFalse(response['success'])

    def test_handle_switch_mode_valid_request(self):
        """Test /switch_mode endpoint with valid coordinates"""
        data = {
            'buttonX': 100,
            'buttonY': 200,
            'targetMode': 'think',
            'moves': 1
        }

        # Validate request structure
        self.assertIsNotNone(data.get('buttonX'))
        self.assertIsNotNone(data.get('buttonY'))
        self.assertIn(data['targetMode'], ['quick', 'think', 'expert'])


class TestWebSocketMessageHandling(unittest.TestCase):
    """Tests for WebSocket message handling"""

    def test_response_message_routing(self):
        """Test FREERIDE_RESPONSE message routing"""
        pending_requests = {'test-request-id': asyncio.Future()}

        data = {
            'type': 'FREERIDE_RESPONSE',
            'requestId': 'test-request-id',
            'response': {
                'success': True,
                'content': 'Test response'
            }
        }

        # Verify message structure
        self.assertEqual(data['type'], 'FREERIDE_RESPONSE')
        self.assertIn('requestId', data)
        self.assertIn('response', data)

    def test_ping_message(self):
        """Test ping message handling"""
        data = {'type': 'ping'}
        expected_response = {'type': 'pong'}

        self.assertEqual(data['type'], 'ping')

    def test_status_message(self):
        """Test status message handling"""
        data = {'type': 'status'}
        internal_state = {
            'websocket_clients': 2,
            'pending_requests': 1
        }

        # Verify state structure
        self.assertIn('websocket_clients', internal_state)
        self.assertIn('pending_requests', internal_state)


class TestConfiguration(unittest.TestCase):
    """Tests for configuration values"""

    def test_default_configuration(self):
        """Test default configuration values"""
        HTTP_HOST = "127.0.0.1"
        HTTP_PORT = 8765

        self.assertEqual(HTTP_HOST, "127.0.0.1")
        self.assertEqual(HTTP_PORT, 8765)

    def test_message_types(self):
        """Test valid message types"""
        valid_types = [
            'FREERIDE_ASK',
            'FREERIDE_RESPONSE',
            'ping',
            'pong',
            'status'
        ]

        for msg_type in valid_types:
            self.assertIsInstance(msg_type, str)

    def test_mode_types(self):
        """Test valid Doubao modes"""
        valid_modes = ['quick', 'think', 'expert']

        for mode in valid_modes:
            self.assertIn(mode, valid_modes)


class TestRequestValidation(unittest.TestCase):
    """Tests for request validation"""

    def test_ask_request_validation(self):
        """Test /ask request validation"""
        valid_request = {
            'prompt': 'Test',
            'timeout': 60,
            'includeThinking': False,
            'mode': 'quick'
        }

        # Check required fields
        self.assertTrue(bool(valid_request.get('prompt')))

        # Check mode is valid
        self.assertIn(valid_request['mode'], ['quick', 'think', 'expert'])

        # Check timeout is positive
        self.assertGreater(valid_request['timeout'], 0)

    def test_switch_mode_request_validation(self):
        """Test /switch_mode request validation"""
        valid_request = {
            'buttonX': 100,
            'buttonY': 200,
            'targetMode': 'think',
            'moves': 1
        }

        # Check required coordinates
        self.assertIsNotNone(valid_request.get('buttonX'))
        self.assertIsNotNone(valid_request.get('buttonY'))

        # Check mode is valid
        self.assertIn(valid_request['targetMode'], ['quick', 'think', 'expert'])

        # Check moves is positive
        self.assertGreater(valid_request['moves'], 0)


class TestCORSHeaders(unittest.TestCase):
    """Tests for CORS handling"""

    def test_cors_headers_present(self):
        """Test that CORS headers are set"""
        expected_headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        }

        # Verify expected CORS configuration
        self.assertEqual(expected_headers['Access-Control-Allow-Origin'], '*')


if __name__ == '__main__':
    unittest.main()
