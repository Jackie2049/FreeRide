/**
 * FreeRide Background Script (Service Worker)
 *
 * Connects to Bridge Server via WebSocket and handles messages
 * Uses keep-alive mechanism to maintain Service Worker active
 */

import type { FreeRideMessage, FreeRideResponse } from './types';

// Bridge Server WebSocket URL
const BRIDGE_URL = 'ws://127.0.0.1:8765/ws';

// WebSocket connection
let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let keepAliveTimer: ReturnType<typeof setInterval> | null = null;

/**
 * Connect to Bridge Server
 */
function connectToBridge(): void {
  console.log('[FreeRide] Connecting to Bridge Server...');

  // Clear existing connection
  if (ws) {
    ws.close();
    ws = null;
  }

  try {
    ws = new WebSocket(BRIDGE_URL);

    ws.onopen = () => {
      console.log('[FreeRide] Connected to Bridge Server');
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      startKeepAlive();
    };

    ws.onclose = () => {
      console.log('[FreeRide] Disconnected from Bridge Server');
      stopKeepAlive();
      ws = null;
      scheduleReconnect();
    };

    ws.onerror = (error) => {
      console.error('[FreeRide] WebSocket error:', error);
    };

    ws.onmessage = async (event) => {
      try {
        const message = JSON.parse(event.data);
        console.log('[FreeRide] Message from Bridge:', message);

        // 处理扩展重载消息
        if (message.type === 'FREERIDE_RELOAD') {
          console.log('[FreeRide] Reloading extension...');
          chrome.runtime.reload();
          return;
        }

        await handleBridgeMessage(message);
      } catch (e) {
        console.error('[FreeRide] Failed to parse message:', e);
      }
    };

  } catch (error) {
    console.error('[FreeRide] Failed to connect:', error);
    scheduleReconnect();
  }
}

function scheduleReconnect(): void {
  if (!reconnectTimer) {
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connectToBridge();
    }, 5000);
  }
}

function startKeepAlive(): void {
  if (keepAliveTimer) {
    clearInterval(keepAliveTimer);
  }
  keepAliveTimer = setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }));
    }
  }, 20000);
}

function stopKeepAlive(): void {
  if (keepAliveTimer) {
    clearInterval(keepAliveTimer);
    keepAliveTimer = null;
  }
}

function sendToBridge(message: any): void {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(message));
  } else {
    console.warn('[FreeRide] Bridge not connected');
  }
}

async function handleBridgeMessage(message: FreeRideMessage): Promise<void> {
  const { type, requestId, payload } = message;

  if (type === 'FREERIDE_ASK' || type === 'FREERIDE_INJECT' || type === 'FREERIDE_CAPTURE') {
    const response = await forwardToContentScript(message);
    sendToBridge({
      type: 'FREERIDE_RESPONSE',
      requestId,
      response
    });
  }
}

async function forwardToContentScript(message: FreeRideMessage): Promise<FreeRideResponse> {
  const tabs = await chrome.tabs.query({ url: 'https://www.doubao.com/*' });

  if (tabs.length === 0) {
    return {
      success: false,
      error: 'Doubao tab not found. Please open doubao.com first.'
    };
  }

  const tab = tabs.find(t => t.active) || tabs[0];

  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tab.id!, message, (response: FreeRideResponse) => {
      if (chrome.runtime.lastError) {
        resolve({
          success: false,
          error: chrome.runtime.lastError.message || 'Failed to communicate with content script'
        });
      } else {
        resolve(response || { success: false, error: 'No response from content script' });
      }
    });
  });
}

// Listen for messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[FreeRide] Message from content script:', message);

  if (message.type === 'STATUS') {
    sendResponse({
      success: true,
      bridgeConnected: ws !== null && ws.readyState === WebSocket.OPEN
    });
    return true;
  }

  return false;
});

// Use alarms to keep Service Worker alive
chrome.alarms.create('keepAlive', { periodInMinutes: 0.4 });

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'keepAlive') {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.log('[FreeRide] Keep-alive: reconnecting...');
      connectToBridge();
    }
  }
});

// Start connection
connectToBridge();
console.log('[FreeRide] Background service worker started');
