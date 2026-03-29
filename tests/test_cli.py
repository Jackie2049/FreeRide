#!/usr/bin/env python3
"""
FreeRide CLI Unit Tests

Tests for the freeride CLI tool.
"""

import unittest
import sys
import os

# Add cli directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cli'))

from unittest.mock import patch, MagicMock
import json


class TestCLIMakeRequest(unittest.TestCase):
    """Tests for make_request function"""

    @patch('urllib.request.urlopen')
    def test_status_request_success(self, mock_urlopen):
        """Test successful status request"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            'status': 'ok',
            'message': 'FreeRide Bridge Server is running'
        }).encode('utf-8')
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        # Import after patching
        import freeride
        result = freeride.make_request('/status')

        self.assertEqual(result['status'], 'ok')
        mock_urlopen.assert_called_once()

    @patch('urllib.request.urlopen')
    def test_ask_request_success(self, mock_urlopen):
        """Test successful ask request"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            'success': True,
            'content': 'Test response from Doubao'
        }).encode('utf-8')
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        import freeride
        result = freeride.make_request('/ask', {
            'prompt': 'Hello',
            'timeout': 60,
            'includeThinking': False,
            'mode': 'quick'
        })

        self.assertTrue(result['success'])
        self.assertEqual(result['content'], 'Test response from Doubao')

    @patch('urllib.request.urlopen')
    def test_connection_failure(self, mock_urlopen):
        """Test connection failure handling"""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError('Connection refused')

        import freeride
        result = freeride.make_request('/status')

        self.assertFalse(result['success'])
        self.assertIn('Connection failed', result['error'])


class TestCLICommands(unittest.TestCase):
    """Tests for CLI command functions"""

    @patch('freeride.make_request')
    def test_cmd_status_success(self, mock_request):
        """Test status command with successful response"""
        mock_request.return_value = {'status': 'ok'}

        import freeride
        from argparse import Namespace
        args = Namespace(host='127.0.0.1', port=8765)

        result = freeride.cmd_status(args)
        self.assertEqual(result, 0)

    @patch('freeride.make_request')
    def test_cmd_status_failure(self, mock_request):
        """Test status command with failed response"""
        mock_request.return_value = {'status': 'error'}

        import freeride
        from argparse import Namespace
        args = Namespace(host='127.0.0.1', port=8765)

        result = freeride.cmd_status(args)
        self.assertEqual(result, 1)

    @patch('freeride.make_request')
    def test_cmd_ask_success(self, mock_request):
        """Test ask command with successful response"""
        mock_request.return_value = {
            'success': True,
            'content': 'Test answer'
        }

        import freeride
        from argparse import Namespace
        args = Namespace(
            prompt='Test question',
            timeout=60,
            include_thinking=False,
            mode='quick',
            host='127.0.0.1',
            port=8765
        )

        result = freeride.cmd_ask(args)
        self.assertEqual(result, 0)

    @patch('freeride.make_request')
    def test_cmd_ask_with_thinking(self, mock_request):
        """Test ask command with thinking content"""
        mock_request.return_value = {
            'success': True,
            'content': 'Test answer',
            'thinking': 'Test thinking process'
        }

        import freeride
        from argparse import Namespace
        args = Namespace(
            prompt='Test question',
            timeout=60,
            include_thinking=True,
            mode='think',
            host='127.0.0.1',
            port=8765
        )

        result = freeride.cmd_ask(args)
        self.assertEqual(result, 0)


class TestCLIArgumentParsing(unittest.TestCase):
    """Tests for argument parsing"""

    def test_ask_command_args(self):
        """Test ask command argument parsing"""
        import freeride
        parser = freeride.argparse.ArgumentParser()
        freeride.setup_parser(parser)  # If this function exists

    def test_default_values(self):
        """Test default values for CLI arguments"""
        import freeride
        self.assertEqual(freeride.DEFAULT_HOST, '127.0.0.1')
        self.assertEqual(freeride.DEFAULT_PORT, 8765)
        self.assertEqual(freeride.DEFAULT_TIMEOUT, 300)


if __name__ == '__main__':
    unittest.main()
