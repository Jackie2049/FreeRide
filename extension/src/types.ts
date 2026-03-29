/**
 * FreeRide Type Definitions
 */

// Message types
export type MessageType =
  | 'FREERIDE_ASK'      // Inject prompt, send, wait for response
  | 'FREERIDE_INJECT'   // Inject prompt only
  | 'FREERIDE_CAPTURE'  // Capture latest AI response
  | 'FREERIDE_STATUS'   // Get current status
  | 'FREERIDE_RESPONSE' // Response from content script
  | 'ping'
  | 'pong';

// Doubao mode types
export type DoubaoMode = 'quick' | 'think' | 'expert';

// Message from CLI/Background to Content Script
export interface FreeRideMessage {
  type: MessageType;
  requestId?: string;
  payload?: {
    prompt?: string;
    timeout?: number;
    autoSend?: boolean;
    mode?: DoubaoMode;
    includeThinking?: boolean;  // 是否包含思考内容
  };
  response?: FreeRideResponse;
}

// Response from Content Script
export interface FreeRideResponse {
  success: boolean;
  error?: string;
  content?: string;        // 最终回答
  thinking?: string;       // 思考过程（仅当 includeThinking=true 时返回）
  status?: {
    platform: string;
    ready: boolean;
  };
}

// Platform configuration
export interface PlatformConfig {
  hostname: string;
  inputSelectors: string[];
  sendButtonSelectors: string[];
  messageContainerSelector: string;
  userMessageSelector: string;
  assistantMessageSelector: string;
}

// Doubao platform configuration - based on ContextDrop verified selectors
export const DOUBAO_CONFIG: PlatformConfig = {
  hostname: 'www.doubao.com',
  inputSelectors: [
    '[contenteditable="true"][class*="editor"]',
    '[contenteditable="true"][class*="input"]',
    '[contenteditable="true"]',
    'textarea[class*="input"]',
    'textarea'
  ],
  sendButtonSelectors: [
    'button[class*="send"]',
    '[class*="send-btn"]',
    'button[type="submit"]'
  ],
  // Message container - multiple possible selectors
  messageContainerSelector: '[class*="message-list"], [class*="chat-container"], [class*="conversation-content"], main, body',
  // User messages have bg-s-color-bg-trans class
  userMessageSelector: '[class*="message-block-container"] [class*="bg-s-color-bg-trans"], [class*="user-message"], [data-role="user"]',
  // Assistant messages have markdown content
  assistantMessageSelector: '[class*="inner-item"], [class*="container-Pv"], [class*="message-block-container"]:not(:has([class*="bg-s-color-bg-trans"])), [class*="flow-markdown"]'
};
