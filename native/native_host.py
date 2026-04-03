#!/usr/bin/bin/env python3
"""
FreeRide Bridge Server

A standalone server that bridges CLI and Chrome Extension via WebSocket.

Architecture:
1. Native Host runs as HTTP + WebSocket server
2. Chrome Extension connects via WebSocket (persistent connection)
3. CLI sends requests via HTTP API
4. Server forwards requests to Extension via WebSocket
5. Extension sends responses back via WebSocket

Supports:
- Custom HTTP API (/ask, /status, /switch_mode) for CLI
- Anthropic Messages API (/v1/messages, /v1/models) for Claude Code

Usage:
    python3 native_host.py          # Start server
    python3 native_host.py --test   # Test mode
"""

import sys
import json
import asyncio
import argparse
import uuid
import re
from typing import Dict, Any, Optional, List, Union
from aiohttp import web
import aiohttp

# 模式切换支持 - 使用pyautogui模拟真实点击
# 注意：pyautogui需要在有图形界面的环境中运行
PYAUTOGUI_AVAILABLE = False
pyautogui = None

try:
    # 延迟导入，先设置环境变量避免Xlib错误
    import os
    os.environ.setdefault('DISPLAY', ':0')

    import pyautogui as _pyautogui
    pyautogui = _pyautogui
    pyautogui.PAUSE = 0.1  # 点击间隔
    PYAUTOGUI_AVAILABLE = True
    print("[FreeRide] pyautogui loaded successfully", file=sys.stderr)
except Exception as e:
    print(f"[FreeRide] Warning: pyautogui not available ({e}), mode switching will use Windows script", file=sys.stderr)

# Configuration
HTTP_HOST = "127.0.0.1"
HTTP_PORT = 8765

# Global state
websocket_clients = set()
pending_requests: Dict[str, asyncio.Future] = {}


def log(message: str):
    """Log to stderr"""
    print(f"[FreeRide] {message}", file=sys.stderr, flush=True)


# =====================
# Anthropic API Helpers
# =====================

def model_to_mode(model: str) -> str:
    """Map Claude model name to Doubao mode

    Mapping rule: sonnet/opus → think, haiku → quick
    """
    model_lower = model.lower()
    if 'opus' in model_lower or 'sonnet' in model_lower:
        return 'think'
    else:  # haiku or other
        return 'quick'


# =====================
# Prompt Adaptation Layer
# =====================

# Brand name replacements: Claude/Anthropic → Doubao/ByteDance
BRAND_REPLACEMENTS = [
    # Full names first (longer matches first)
    (r'Claude Code', '豆包'),
    (r'Claude\s+Opus', '豆包Pro'),
    (r'Claude\s+Sonnet', '豆包'),
    (r'Claude\s+Haiku', '豆包Lite'),
    (r'Claude-Opus', '豆包Pro'),
    (r'Claude-Sonnet', '豆包'),
    (r'Claude-Haiku', '豆包Lite'),
    (r'claude-opus', 'doubao-pro'),
    (r'claude-sonnet', 'doubao'),
    (r'claude-haiku', 'doubao-lite'),
    (r'Anthropic', '字节跳动'),
    (r'anthropic', 'bytedance'),
    (r'Claude', '豆包'),
    (r'claude', '豆包'),
]


def replace_brand_names(text: str) -> str:
    """Replace all Claude/Anthropic brand names with Doubao/ByteDance equivalents."""
    if not text or not isinstance(text, str):
        return text or ''
    for pattern, replacement in BRAND_REPLACEMENTS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def adapt_prompt(messages: List[Dict], system: str = None) -> str:
    """
    Adapt Claude Code's structured prompt into a natural format.

    Claude Code sends prompts with explicit role labels:
    - SYSTEM: long instructions about tools, rules, etc.
    - USER/ASSISTANT: conversation history

    This adapter transforms them into natural language to avoid bot detection.
    The transformation is purely rule-based (no LLM calls).
    """

    # Step 1: Extract all content and apply brand name replacements
    extracted = []
    for msg in messages:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        if isinstance(content, list):
            text_parts = []
            for c in content:
                if isinstance(c, dict) and c.get('type') == 'text':
                    text_parts.append(c.get('text', ''))
                elif isinstance(c, str):
                    text_parts.append(c)
            content = '\n'.join(text_parts)
        # Apply brand name replacement
        content = replace_brand_names(content)
        if content.strip():
            extracted.append((role, content.strip()))

    # Also replace brand names in system prompt
    if system:
        system = replace_brand_names(system)

    if not extracted:
        return ''

    # Step 2: Classify the request type
    is_simple_query = len(extracted) == 1 and extracted[0][0] == 'user'
    has_context = system is not None and len(system) > 50
    is_multi_turn = len(extracted) > 1

    # Step 3: Apply transformation strategy

    # Strategy A: Simple single query - send as-is
    if is_simple_query and not has_context:
        return extracted[0][1]

    # Strategy B: Query with context (system prompt)
    # Extract task from system and prepend naturally
    if is_simple_query and has_context:
        task_summary = extract_task_from_system(system)
        user_query = extracted[0][1]

        if task_summary:
            return f"{task_summary}\n\n{user_query}"
        return user_query

    # Strategy C: Multi-turn conversation
    # Format as natural dialogue
    return format_multi_turn(extracted, system)


def extract_task_from_system(system: str) -> str:
    """
    Extract key task/role from system prompt.
    Returns a natural language summary or empty string.
    """
    if not system or len(system) < 20:
        return ''

    # Common patterns in Claude Code system prompts
    task_patterns = [
        r'You are (?:an? )?([^.\n]+)',
        r'Your (?:task|role|goal) (?:is|:)\s*([^.\n]+)',
        r'Help (?:the )?user (?:to )?([^.\n]+)',
    ]

    for pattern in task_patterns:
        match = re.search(pattern, system, re.IGNORECASE)
        if match:
            role = match.group(1).strip()
            # Make it natural
            if len(role) > 100:
                role = role[:100] + '...'
            return f"(我是{role})"

    return ''


def format_multi_turn(messages: List[tuple], system: str = None) -> str:
    """
    Format multi-turn conversation into natural dialogue.

    Instead of:
        USER: xxx
        ASSISTANT: xxx
        USER: xxx

    Use:
        xxx

        [我之前的回答]
        xxx

        [继续]
        xxx
    """
    parts = []

    # Handle system - skip if too long (likely tool definitions)
    if system:
        task = extract_task_from_system(system)
        if task:
            parts.append(task)

    for i, (role, content) in enumerate(messages):
        if role == 'user':
            if i == 0:
                # First user message - send directly
                parts.append(content)
            else:
                # Subsequent user messages - add continuation marker
                parts.append(f"[继续]\n{content}")
        else:
            # Assistant message - format as previous response
            # Truncate if too long
            if len(content) > 500:
                content = content[:500] + '...(省略)'
            parts.append(f"[我之前的回答]\n{content}")

    return '\n\n'.join(parts)


def messages_to_prompt(messages: List[Dict], system: str = None) -> str:
    """Entry point for prompt adaptation"""
    return adapt_prompt(messages, system)


def create_anthropic_response(content: str, model: str) -> Dict:
    """Create Anthropic-style response"""
    return {
        'id': f'msg_{uuid.uuid4().hex[:24]}',
        'type': 'message',
        'role': 'assistant',
        'content': [
            {
                'type': 'text',
                'text': content
            }
        ],
        'model': model,
        'stop_reason': 'end_turn',
        'stop_sequence': None,
        'usage': {
            'input_tokens': 0,
            'output_tokens': 0
        }
    }


def create_anthropic_error(error_type: str, message: str, status: int = 400) -> Dict:
    """Create Anthropic-style error response"""
    return {
        'type': 'error',
        'error': {
            'type': error_type,
            'message': message
        }
    }


async def handle_http_status(request: web.Request) -> web.Response:
    """Handle GET /status"""
    return web.json_response({
        'status': 'ok',
        'message': 'FreeRide Bridge Server is running',
        'websocket_clients': len(websocket_clients),
        'pending_requests': len(pending_requests)
    })


# =====================
# Anthropic API Handlers
# =====================

async def handle_http_v1_models(request: web.Request) -> web.Response:
    """Handle GET /v1/models - return available models"""
    return web.json_response({
        'object': 'list',
        'data': [
            {
                'id': 'claude-sonnet-4-20250514',
                'object': 'model',
                'created': 1700000000,
                'owned_by': 'freeride'
            },
            {
                'id': 'claude-opus-4-20250514',
                'object': 'model',
                'created': 1700000000,
                'owned_by': 'freeride'
            },
            {
                'id': 'claude-haiku-3-5-20241022',
                'object': 'model',
                'created': 1700000000,
                'owned_by': 'freeride'
            }
        ]
    })


async def handle_http_v1_messages(request: web.Request) -> web.Response:
    """Handle POST /v1/messages - Anthropic Messages API"""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            create_anthropic_error('invalid_request_error', 'Invalid JSON'),
            status=400
        )

    # Extract Anthropic request fields
    model = data.get('model', 'claude-sonnet-4-20250514')
    messages = data.get('messages', [])
    system = data.get('system')
    max_tokens = data.get('max_tokens', 4096)
    stream = data.get('stream', False)

    # Validate required fields
    if not messages:
        return web.json_response(
            create_anthropic_error('invalid_request_error', 'messages is required'),
            status=400
        )

    if not websocket_clients:
        return web.json_response(
            create_anthropic_error('api_error', 'Chrome extension not connected. Please ensure the extension is loaded and Doubao page is open.'),
            status=503
        )

    # Convert to internal format
    prompt = messages_to_prompt(messages, system)
    mode = model_to_mode(model)

    log(f"[Anthropic API] Request: model={model}, mode={mode}, messages={len(messages)}, stream={stream}")

    # Generate request ID
    request_id = str(uuid.uuid4())

    # Create future for response
    future = asyncio.get_event_loop().create_future()
    pending_requests[request_id] = future

    try:
        # Send to Chrome Extension via WebSocket
        message = {
            'type': 'FREERIDE_ASK',
            'requestId': request_id,
            'payload': {
                'prompt': prompt,
                'timeout': 300,
                'includeThinking': False,
                'mode': mode
            }
        }

        for ws in websocket_clients:
            await ws.send_json(message)

        log(f"[Anthropic API] Request {request_id} sent to extension")

        # Wait for response
        try:
            response = await asyncio.wait_for(future, timeout=320)
            log(f"[Anthropic API] Request {request_id} completed")

            # Extract content from response
            if response.get('success'):
                content = response.get('content', '')
            else:
                error_msg = response.get('error', 'Unknown error')
                return web.json_response(
                    create_anthropic_error('api_error', error_msg),
                    status=500
                )

            # Return based on stream mode
            if stream:
                return await create_streaming_response(request, content, model)
            else:
                return web.json_response(create_anthropic_response(content, model))

        except asyncio.TimeoutError:
            log(f"[Anthropic API] Request {request_id} timeout")
            return web.json_response(
                create_anthropic_error('api_error', 'Response timeout'),
                status=504
            )

    finally:
        pending_requests.pop(request_id, None)


async def create_streaming_response(request: web.Request, content: str, model: str):
    """Create SSE streaming response for Anthropic API"""
    response = web.StreamResponse()
    response.content_type = 'text/event-stream'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['Access-Control-Allow-Origin'] = '*'
    await response.prepare(request)

    msg_id = f'msg_{uuid.uuid4().hex[:24]}'

    async def send_event(event: str, data: dict):
        """Send a single SSE event"""
        await response.write(f'event: {event}\n'.encode())
        await response.write(f'data: {json.dumps(data)}\n\n'.encode())

    # 1. message_start
    await send_event('message_start', {
        'type': 'message_start',
        'message': {
            'id': msg_id,
            'type': 'message',
            'role': 'assistant',
            'content': [],
            'model': model,
            'stop_reason': None,
            'usage': {'input_tokens': 0, 'output_tokens': 0}
        }
    })

    # 2. content_block_start
    await send_event('content_block_start', {
        'type': 'content_block_start',
        'index': 0,
        'content_block': {'type': 'text', 'text': ''}
    })

    # 3. Pseudo-streaming: send content in chunks
    chunk_size = 15  # characters per chunk
    for i in range(0, len(content), chunk_size):
        chunk = content[i:i + chunk_size]
        await send_event('content_block_delta', {
            'type': 'content_block_delta',
            'index': 0,
            'delta': {'type': 'text_delta', 'text': chunk}
        })
        await asyncio.sleep(0.02)  # Small delay for realistic streaming effect

    # 4. content_block_stop
    await send_event('content_block_stop', {
        'type': 'content_block_stop',
        'index': 0
    })

    # 5. message_delta
    await send_event('message_delta', {
        'type': 'message_delta',
        'delta': {'stop_reason': 'end_turn', 'stop_sequence': None},
        'usage': {'output_tokens': len(content) // 4}  # Rough estimate
    })

    # 6. message_stop
    await send_event('message_stop', {
        'type': 'message_stop'
    })

    await response.write_eof()
    return response


async def handle_http_status(request: web.Request) -> web.Response:
    """Handle GET /status"""
    return web.json_response({
        'status': 'ok',
        'message': 'FreeRide Bridge Server is running',
        'websocket_clients': len(websocket_clients),
        'pending_requests': len(pending_requests)
    })


async def handle_http_ask(request: web.Request) -> web.Response:
    """Handle POST /ask - forward to WebSocket client (Extension)"""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return web.json_response({'success': False, 'error': 'Invalid JSON'}, status=400)

    prompt = data.get('prompt', '')
    timeout = data.get('timeout', 60)
    include_thinking = data.get('includeThinking', False)
    mode = data.get('mode', 'quick')  # quick, think, expert

    if not prompt:
        return web.json_response({'success': False, 'error': 'Missing prompt'}, status=400)

    if not websocket_clients:
        return web.json_response({
            'success': False,
            'error': 'Chrome extension not connected. Please ensure the extension is loaded and Doubao page is open.'
        }, status=503)

    log(f"Received ask request: {prompt[:50]}... (mode: {mode}, includeThinking: {include_thinking})")

    # Generate request ID
    import uuid
    request_id = str(uuid.uuid4())

    # Create future for response
    future = asyncio.get_event_loop().create_future()
    pending_requests[request_id] = future

    try:
        # Send to all connected WebSocket clients (Extension)
        message = {
            'type': 'FREERIDE_ASK',
            'requestId': request_id,
            'payload': {
                'prompt': prompt,
                'timeout': timeout,
                'includeThinking': include_thinking,
                'mode': mode
            }
        }

        for ws in websocket_clients:
            await ws.send_json(message)

        log(f"Request {request_id} sent to {len(websocket_clients)} client(s)")

        # Wait for response
        try:
            response = await asyncio.wait_for(future, timeout=timeout + 10)
            log(f"Request {request_id} completed")
            return web.json_response(response)
        except asyncio.TimeoutError:
            log(f"Request {request_id} timeout")
            return web.json_response({
                'success': False,
                'error': 'Response timeout'
            }, status=504)

    finally:
        pending_requests.pop(request_id, None)


async def handle_websocket(request: web.Request) -> web.WebSocketResponse:
    """Handle WebSocket connection from Chrome Extension"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    websocket_clients.add(ws)
    log(f"WebSocket client connected. Total clients: {len(websocket_clients)}")

    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    await handle_websocket_message(ws, data)
                except json.JSONDecodeError:
                    log(f"Invalid JSON from WebSocket: {msg.data[:100]}")
            elif msg.type == aiohttp.WSMsgType.ERROR:
                log(f"WebSocket error: {ws.exception()}")
    finally:
        websocket_clients.discard(ws)
        log(f"WebSocket client disconnected. Total clients: {len(websocket_clients)}")

    return ws


async def handle_websocket_message(ws: web.WebSocketResponse, data: Dict[str, Any]):
    """Handle message from WebSocket client (Extension)"""
    msg_type = data.get('type')
    log(f"WebSocket message: {msg_type}")

    if msg_type == 'FREERIDE_RESPONSE':
        # Response from extension for a previous request
        request_id = data.get('requestId')
        response = data.get('response', {})

        if request_id and request_id in pending_requests:
            future = pending_requests[request_id]
            if not future.done():
                future.set_result(response)
            log(f"Response for {request_id} routed to pending request")
        else:
            log(f"No pending request found for {request_id}")

    elif msg_type == 'ping':
        await ws.send_json({'type': 'pong'})

    elif msg_type == 'status':
        await ws.send_json({
            'type': 'status',
            'websocket_clients': len(websocket_clients),
            'pending_requests': len(pending_requests)
        })


async def handle_http_options(request: web.Request) -> web.Response:
    """Handle CORS preflight"""
    response = web.Response()
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


async def handle_http_reload(request: web.Request) -> web.Response:
    """Handle POST /reload - trigger extension reload via WebSocket"""
    log("Extension reload requested")

    # 通过 WebSocket 通知扩展刷新
    if websocket_clients:
        for ws in list(websocket_clients):
            try:
                await ws.send_json({'type': 'FREERIDE_RELOAD'})
            except Exception as e:
                log(f"Failed to send reload to client: {e}")

    return web.json_response({'success': True, 'message': 'Reload signal sent'})


async def handle_http_switch_mode(request: web.Request) -> web.Response:
    """Handle POST /switch_mode - use pyautogui to simulate real mouse clicks"""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return web.json_response({'success': False, 'error': 'Invalid JSON'}, status=400)

    button_x = data.get('buttonX')
    button_y = data.get('buttonY')
    target_mode = data.get('targetMode', 'think')
    moves = data.get('moves', 1)  # 需要按向下箭头的次数

    if button_x is None or button_y is None:
        return web.json_response({'success': False, 'error': 'Missing buttonX or buttonY'}, status=400)

    log(f"Switching mode: button=({button_x}, {button_y}), target={target_mode}, moves={moves}")

    # 方案1: 如果pyautogui在当前环境可用（非WSL）
    if PYAUTOGUI_AVAILABLE and pyautogui is not None:
        try:
            import threading
            import time

            def do_click():
                try:
                    pyautogui.click(button_x, button_y)
                    time.sleep(0.3)
                    for i in range(moves):
                        pyautogui.press('down')
                        time.sleep(0.1)
                    pyautogui.press('enter')
                    log(f"Mode switch completed: {target_mode}")
                except Exception as e:
                    log(f"pyautogui error: {e}")

            thread = threading.Thread(target=do_click)
            thread.start()
            await asyncio.sleep(0.8)
            return web.json_response({'success': True, 'message': f'Mode switched to {target_mode}'})

        except Exception as e:
            log(f"Failed to switch mode: {e}")
            return web.json_response({'success': False, 'error': str(e)}, status=500)

    # 方案2: 调用Windows端的PowerShell脚本（适用于WSL，无需安装任何依赖）
    try:
        import subprocess

        # PowerShell脚本路径
        ps_script = r"C:\Users\73523\Desktop\FreeRide\switch_mode.ps1"

        # 通过PowerShell执行
        cmd = [
            "powershell.exe",
            "-ExecutionPolicy", "Bypass",
            "-File", ps_script,
            "-ButtonX", str(button_x),
            "-ButtonY", str(button_y),
            "-Moves", str(moves)
        ]

        log(f"Calling PowerShell: {' '.join(cmd)}")

        # 在后台线程中执行
        def run_script():
            try:
                # 使用encoding参数处理Windows中文编码
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    encoding='gbk',
                    errors='ignore'  # 忽略无法解码的字符
                )
                log(f"PowerShell output: {result.stdout}")
                if result.stderr:
                    log(f"PowerShell stderr: {result.stderr}")
            except Exception as e:
                log(f"PowerShell error: {e}")

        import threading
        thread = threading.Thread(target=run_script)
        thread.start()

        # 等待操作完成
        await asyncio.sleep(1.0)

        return web.json_response({'success': True, 'message': f'Mode switch command sent to Windows'})

    except Exception as e:
        log(f"Failed to call PowerShell: {e}")
        return web.json_response({
            'success': False,
            'error': f'Mode switching failed: {str(e)}'
        }, status=500)


def create_app() -> web.Application:
    """Create aiohttp application"""
    app = web.Application()

    # CORS middleware
    @web.middleware
    async def cors_middleware(request, handler):
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = ex
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    # Routes
    app.router.add_get('/status', handle_http_status)
    app.router.add_post('/ask', handle_http_ask)
    app.router.add_options('/ask', handle_http_options)
    app.router.add_post('/switch_mode', handle_http_switch_mode)
    app.router.add_options('/switch_mode', handle_http_options)
    app.router.add_post('/reload', handle_http_reload)
    app.router.add_options('/reload', handle_http_options)
    app.router.add_get('/ws', handle_websocket)

    # Anthropic API routes
    app.router.add_get('/v1/models', handle_http_v1_models)
    app.router.add_post('/v1/messages', handle_http_v1_messages)
    app.router.add_options('/v1/messages', handle_http_options)

    return app


async def main_async():
    """Main async entry point"""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, HTTP_HOST, HTTP_PORT)
    await site.start()

    log(f"Bridge Server started at http://{HTTP_HOST}:{HTTP_PORT}")
    log(f"WebSocket endpoint: ws://{HTTP_HOST}:{HTTP_PORT}/ws")
    log("Press Ctrl+C to stop")

    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await runner.cleanup()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='FreeRide Bridge Server')
    parser.add_argument('--test', action='store_true', help='Run in test mode')
    args = parser.parse_args()

    if args.test:
        log("Test mode - checking server...")
        import urllib.request
        try:
            with urllib.request.urlopen(f'http://{HTTP_HOST}:{HTTP_PORT}/status', timeout=5) as resp:
                print(resp.read().decode())
        except Exception as e:
            print(f"Server not running: {e}")
        return

    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        log("Server stopped")


if __name__ == '__main__':
    main()
