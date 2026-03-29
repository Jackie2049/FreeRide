#!/usr/bin/env python3
"""
FreeRide CLI

A command-line tool to interact with web AI assistants through the FreeRide system.

Usage:
    freeride ask "Your question here"
    freeride status
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

# Default configuration
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_TIMEOUT = 300  # 5分钟，豆包网页端没有超时限制


def log(message: str):
    """Print log message to stderr"""
    print(f"[FreeRide] {message}", file=sys.stderr)


def error(message: str):
    """Print error message to stderr"""
    print(f"[FreeRide ERROR] {message}", file=sys.stderr)


def make_request(
    endpoint: str,
    data: Optional[Dict] = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: int = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    """Make HTTP request to the native host"""
    url = f"http://{host}:{port}{endpoint}"

    try:
        headers = {'Content-Type': 'application/json'}

        if data:
            body = json.dumps(data).encode('utf-8')
            req = urllib.request.Request(url, data=body, headers=headers, method='POST')
        else:
            req = urllib.request.Request(url, headers=headers, method='GET')

        with urllib.request.urlopen(req, timeout=timeout + 10) as response:
            return json.loads(response.read().decode('utf-8'))

    except urllib.error.HTTPError as e:
        try:
            error_body = e.read().decode('utf-8')
            return json.loads(error_body)
        except:
            return {'success': False, 'error': f'HTTP {e.code}: {e.reason}'}

    except urllib.error.URLError as e:
        return {'success': False, 'error': f'Connection failed: {e.reason}. Is the native host running?'}

    except Exception as e:
        return {'success': False, 'error': str(e)}


def cmd_ask(args):
    """Send a question to Doubao and wait for response"""
    prompt = args.prompt
    timeout = args.timeout
    include_thinking = args.include_thinking
    mode = args.mode

    if not prompt:
        error("Please provide a prompt")
        return 1

    log(f"Asking: {prompt[:50]}... (mode: {mode}, includeThinking: {include_thinking})")

    response = make_request('/ask', {
        'prompt': prompt,
        'timeout': timeout,
        'includeThinking': include_thinking,
        'mode': mode
    })

    if response.get('success'):
        # 如果有思考内容且用户要求显示
        if include_thinking and response.get('thinking'):
            print("=== 思考过程 ===")
            print(response.get('thinking'))
            print("\n=== 回答 ===")

        content = response.get('content', '')
        print(content)
        return 0
    else:
        error(response.get('error', 'Unknown error'))
        return 1


def cmd_status(args):
    """Check the status of the FreeRide system"""
    response = make_request('/status')

    if response.get('status') == 'ok':
        print("FreeRide Native Host: Running")
        print(f"HTTP API: http://{DEFAULT_HOST}:{DEFAULT_PORT}")
        return 0
    else:
        error("FreeRide Native Host: Not running")
        return 1


def main():
    parser = argparse.ArgumentParser(
        prog='freeride',
        description='Interact with web AI assistants through FreeRide'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # ask command
    ask_parser = subparsers.add_parser('ask', help='Ask a question to Doubao')
    ask_parser.add_argument('prompt', help='The question/prompt to send')
    ask_parser.add_argument('--timeout', '-t', type=int, default=DEFAULT_TIMEOUT,
                           help=f'Timeout in seconds (default: {DEFAULT_TIMEOUT})')
    ask_parser.add_argument('--include-thinking', '-T', action='store_true',
                           help='Include thinking/reasoning content in response')
    ask_parser.add_argument('--mode', '-m', choices=['quick', 'think', 'expert'], default='quick',
                           help='Response mode: quick (default), think (deep reasoning), expert (research-level)')
    ask_parser.add_argument('--host', default=DEFAULT_HOST,
                           help=f'Native host address (default: {DEFAULT_HOST})')
    ask_parser.add_argument('--port', '-p', type=int, default=DEFAULT_PORT,
                           help=f'Native host port (default: {DEFAULT_PORT})')

    # status command
    status_parser = subparsers.add_parser('status', help='Check system status')
    status_parser.add_argument('--host', default=DEFAULT_HOST,
                              help=f'Native host address (default: {DEFAULT_HOST})')
    status_parser.add_argument('--port', '-p', type=int, default=DEFAULT_PORT,
                              help=f'Native host port (default: {DEFAULT_PORT})')

    # Parse arguments
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    # Execute command
    if args.command == 'ask':
        return cmd_ask(args)
    elif args.command == 'status':
        return cmd_status(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
