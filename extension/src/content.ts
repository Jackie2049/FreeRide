/**
 * FreeRide Content Script
 *
 * Handles prompt injection and response capture for Doubao
 * Based on ContextDrop's proven extraction logic
 */

import type { FreeRideMessage, FreeRideResponse, DoubaoMode } from './types';

const DEBUG = true;

function log(...args: any[]) {
  if (DEBUG) console.log('[FreeRide]', ...args);
}

function error(...args: any[]) {
  console.error('[FreeRide]', ...args);
}

// Current state
let isProcessing = false;

// Doubao selectors - from ContextDrop verified implementation
const DOUBAO_MESSAGE_SELECTORS = [
  '[class*="inner-item"]',
  '[class*="container-Pv"]',
  '[class*="message-block-container"]',
  '[class*="message-block"]',
  '[class*="chat-message"]',
  '[class*="message-item"]',
];

const DOUBAO_INPUT_SELECTORS = [
  '[contenteditable="true"][class*="editor"]',
  '[contenteditable="true"][class*="input"]',
  '[contenteditable="true"]',
  'textarea[class*="input"]',
  'textarea'
];

const DOUBAO_SEND_SELECTORS = [
  'button[class*="send"]',
  '[class*="send-btn"]',
  'button[type="submit"]'
];

/**
 * Find input element
 */
function findInputElement(): HTMLElement | null {
  log('Finding input element...');

  for (const selector of DOUBAO_INPUT_SELECTORS) {
    const elements = document.querySelectorAll<HTMLElement>(selector);
    for (const el of elements) {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        log(`Found input: ${el.tagName}`);
        return el;
      }
    }
  }
  error('No input element found');
  return null;
}

/**
 * Find send button (even if disabled)
 */
function findSendButtonEvenIfDisabled(): HTMLButtonElement | null {
  for (const selector of DOUBAO_SEND_SELECTORS) {
    const buttons = document.querySelectorAll<HTMLButtonElement>(selector);
    for (const btn of buttons) {
      const rect = btn.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        return btn;
      }
    }
  }
  return null;
}

/**
 * Find send button (only enabled)
 */
function findSendButton(): HTMLButtonElement | null {
  log('Finding send button...');

  for (const selector of DOUBAO_SEND_SELECTORS) {
    const buttons = document.querySelectorAll<HTMLButtonElement>(selector);
    for (const btn of buttons) {
      const rect = btn.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0 && !btn.disabled) {
        log('Found send button');
        return btn;
      }
    }
  }
  error('No enabled send button found');
  return null;
}

/**
 * Fill input element with content
 */
function fillInputElement(element: HTMLElement, content: string): boolean {
  try {
    element.focus();

    if (element.isContentEditable || element.contentEditable === 'true') {
      element.textContent = '';
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(element);
      range.collapse(false);
      selection?.removeAllRanges();
      selection?.addRange(range);

      const success = document.execCommand('insertText', false, content);
      if (!success) {
        element.textContent = content;
      }
    } else if (element.tagName === 'TEXTAREA' || element.tagName === 'INPUT') {
      (element as HTMLTextAreaElement).value = content;
    } else {
      return false;
    }

    // Trigger events
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
    element.dispatchEvent(new InputEvent('input', {
      bubbles: true,
      cancelable: true,
      inputType: 'insertText',
      data: content
    }));

    return true;
  } catch (e) {
    error('Failed to fill input:', e);
    return false;
  }
}

/**
 * Get message blocks from DOM
 */
function getMessageBlocks(): Element[] {
  for (const selector of DOUBAO_MESSAGE_SELECTORS) {
    const elements = document.querySelectorAll(selector);
    if (elements.length > 0) {
      log(`Found ${elements.length} message blocks with: ${selector}`);
      return Array.from(elements);
    }
  }
  return [];
}

/**
 * Check if element is an assistant message (has markdown content)
 */
function isAssistantMessage(block: Element): boolean {
  return !!block.querySelector('[class*="markdown"], [class*="flow-markdown"]');
}

/**
 * Extract text from assistant message (excluding thinking content)
 */
function extractAssistantContent(block: Element): string {
  // 首先尝试找到回答内容区域（排除思考卡片）
  // 豆包的回答内容通常在特定的容器中

  // 尝试找到主要的回答内容区域
  const answerSelectors = [
    // 豆包回答内容 - 使用 data 属性
    '[data-message-author-role="assistant"]',
    // markdown 内容区域
    '[class*="flow-markdown"]',
    '[class*="markdown-body"]',
    '[class*="markdown-content"]'
  ];

  for (const selector of answerSelectors) {
    const elements = block.querySelectorAll(selector);
    for (const el of elements) {
      // 确保不是思考卡片内的内容
      const closestThinking = el.closest('[class*="thinking-box"], [data-thinking-box], [class*="think-block"]');
      if (!closestThinking && el.textContent?.trim()) {
        return el.textContent.trim();
      }
    }
  }

  // 如果上面没找到，尝试遍历所有容器，排除思考卡片
  const containerSelectors = [
    '[class*="flow-markdown"]',
    '[class*="markdown"]',
    '[class*="content-"]'
  ];

  for (const selector of containerSelectors) {
    const elements = block.querySelectorAll(selector);
    for (const el of elements) {
      // 检查是否在思考卡片内
      const parent = el.parentElement;
      if (parent) {
        const parentClass = parent.className || '';
        // 排除思考相关的容器
        if (!parentClass.includes('thinking') &&
            !parentClass.includes('think-block') &&
            !parentClass.includes('reasoning') &&
            el.textContent?.trim()) {
          return el.textContent.trim();
        }
      }
    }
  }

  return block.textContent?.trim() || '';
}

/**
 * Get the latest assistant message content
 */
function getLatestAssistantMessage(): string | null {
  const blocks = getMessageBlocks();

  const assistantMessages: { block: Element; content: string }[] = [];

  blocks.forEach(block => {
    if (isAssistantMessage(block)) {
      const content = extractAssistantContent(block);
      if (content) {
        assistantMessages.push({ block, content });
      }
    }
  });

  if (assistantMessages.length === 0) {
    return null;
  }

  const lastMessage = assistantMessages[assistantMessages.length - 1];
  log(`Latest assistant message (${lastMessage.content.length} chars)`);
  return lastMessage.content;
}

/**
 * Expand thinking card if collapsed
 */
function expandThinkingCard(): void {
  // 找到折叠的思考卡片并点击展开
  // 新版豆包使用多种选择器
  const thinkingRootSelectors = [
    '[class*="thinking-box-root"]',
    '[class*="think-block-container"]',
    '[data-thinking-box="content"]'
  ];

  for (const rootSelector of thinkingRootSelectors) {
    const thinkingRoot = document.querySelector(rootSelector);
    if (thinkingRoot) {
      // 查找可点击的展开区域 - 通常是包含"已完成思考"文本的元素
      const allClickable = thinkingRoot.querySelectorAll('[class*="cursor-pointer"]');
      for (const clickable of allClickable) {
        const text = clickable.textContent || '';
        // 只有当显示"已完成思考"时才需要展开
        if (text.includes('已完成思考') && !text.includes('深度思考中')) {
          log(`Expanding collapsed thinking card (selector: ${rootSelector})`);
          (clickable as HTMLElement).click();
          return; // 只点击一次
        }
      }
    }
  }
}

/**
 * Get thinking content from DOM
 * 豆包的思考卡片可能处于折叠或展开状态
 */
function getThinkingContent(): string | null {
  // 豆包的思考内容选择器 - 基于实际DOM分析
  // 优先级从高到低
  const thinkingSelectors = [
    // 新版豆包思考内容 - data 属性
    '[data-thinking-box="step-message"]',
    '[data-thinking-box="content"]',
    // 新版豆包思考卡片容器
    '[class*="thinking-box-root"]',
    // 旧版豆包思考卡片容器
    '[class*="think-block-container"]',
    // 备用选择器
    '[class*="think-content"]',
    '[class*="thinking-content"]',
    '[class*="deep-think"]',
    '[class*="reasoning"]'
  ];

  for (const selector of thinkingSelectors) {
    const el = document.querySelector(selector);
    if (el?.textContent?.trim()) {
      const text = el.textContent.trim();
      // 过滤掉只有"已完成思考"的情况
      if (text !== '已完成思考' && text.length > 10) {
        log(`Found thinking content with selector: ${selector}, length: ${text.length}`);
        return text;
      }
    }
  }

  return null;
}

/**
 * Check if deep thinking is still in progress
 */
function isDeepThinkingInProgress(): boolean {
  // 新版豆包使用 thinking-box 选择器
  const thinkingIndicators = [
    '[class*="thinking-box-root"]',
    '[class*="think-block-title"]',
    '[data-thinking-box="title"]'
  ];

  for (const selector of thinkingIndicators) {
    const el = document.querySelector(selector);
    if (el) {
      const text = el.textContent || '';
      // 如果标题包含"思考中"但不是"已完成思考"，说明还在思考
      if ((text.includes('思考中') || text.includes('深度思考')) && !text.includes('已完成')) {
        log('Deep thinking in progress');
        return true;
      }
    }
  }

  return false;
}

/**
 * Check if AI is still generating
 */
function isStillGenerating(): boolean {
  // Method 1: Check if deep thinking is in progress
  if (isDeepThinkingInProgress()) {
    log('Deep thinking mode active');
    return true;
  }

  // Method 2: Check if send button is disabled
  const sendBtn = findSendButtonEvenIfDisabled();
  if (sendBtn && sendBtn.disabled) {
    log('Send button disabled - still generating');
    return true;
  }

  // Method 3: Check for loading indicators
  const loadingIndicators = [
    '[class*="loading"]',
    '[class*="generating"]',
    '.typing-indicator'
  ];

  for (const selector of loadingIndicators) {
    const el = document.querySelector(selector);
    if (el) {
      const style = window.getComputedStyle(el);
      if (style.display !== 'none' && style.visibility !== 'hidden') {
        log(`Loading indicator found: ${selector}`);
        return true;
      }
    }
  }

  return false;
}

/**
 * Response result including optional thinking content
 */
interface ResponseResult {
  content: string;      // 最终回答
  thinking?: string;    // 思考过程（如果有）
}

/**
 * Wait for AI response to complete
 *
 * Handles deep thinking mode:
 * 1. Deep thinking phase: thinking content changes, answer may be static
 * 2. Answer phase: thinking done, answer content changes
 * 3. Complete: both thinking and answer are stable, not generating
 *
 * Timeout is just a safety net - returns partial content if reached
 */
async function waitForResponse(timeout: number, contentBefore: string): Promise<ResponseResult> {
  return new Promise((resolve, reject) => {
    const startTime = Date.now();
    let lastAnswerContent = '';
    let lastThinkingContent = '';
    let capturedThinkingContent = '';  // 捕获的完整思考内容
    let stableCount = 0;
    const stableThreshold = 5;
    let newContentDetected = false;
    let thinkingPhaseComplete = false;

    log('Waiting for response...');
    log(`Content before: "${contentBefore.substring(0, 50)}..."`);

    const checkInterval = setInterval(() => {  // 200ms interval for faster response
      const elapsed = Date.now() - startTime;

      // Timeout is just safety net - return what we have
      if (elapsed > timeout) {
        clearInterval(checkInterval);
        if (lastAnswerContent) {
          log(`Timeout reached (${timeout/1000}s), returning captured content`);
          resolve({
            content: lastAnswerContent,
            thinking: capturedThinkingContent || undefined
          });
        } else {
          reject(new Error('Response timeout - no content detected'));
        }
        return;
      }

      const currentAnswerContent = getLatestAssistantMessage() || '';

      // 尝试展开思考卡片（如果折叠的话）
      expandThinkingCard();

      const currentThinkingContent = getThinkingContent() || '';
      const stillGenerating = isStillGenerating();

      // Track thinking content changes
      if (currentThinkingContent && currentThinkingContent !== lastThinkingContent) {
        log(`Thinking in progress: ${currentThinkingContent.length} chars`);
        lastThinkingContent = currentThinkingContent;
        capturedThinkingContent = currentThinkingContent;  // 持续更新捕获
        // Reset stability when thinking is active
        stableCount = 0;
        thinkingPhaseComplete = false;
        return;
      }

      // Thinking phase complete if thinking content exists and is stable
      if (currentThinkingContent && currentThinkingContent === lastThinkingContent && !thinkingPhaseComplete) {
        log('Thinking phase complete, waiting for answer...');
        thinkingPhaseComplete = true;
        // 保存最终的思考内容
        capturedThinkingContent = currentThinkingContent;
      }

      // Step 1: Wait for NEW answer content to appear
      if (!newContentDetected) {
        if (currentAnswerContent && currentAnswerContent !== contentBefore) {
          newContentDetected = true;
          lastAnswerContent = currentAnswerContent;
          log(`New answer content detected: "${currentAnswerContent.substring(0, 50)}..."`);
        }
        return;
      }

      // Step 2: Check completion signals
      // Complete = not generating + answer stable + thinking complete (if any)
      if (currentAnswerContent === lastAnswerContent && currentAnswerContent.length > 0) {
        if (!stillGenerating) {
          stableCount++;
          log(`Stable ${stableCount}/${stableThreshold}, generating: false, answer: ${currentAnswerContent.length} chars`);

          if (stableCount >= stableThreshold) {
            clearInterval(checkInterval);
            log('Response complete!');
            log(`Captured thinking: ${capturedThinkingContent ? capturedThinkingContent.length + ' chars' : 'none'}`);
            resolve({
              content: currentAnswerContent,
              thinking: capturedThinkingContent || undefined
            });
          }
        } else {
          // Still generating, reset stability counter
          stableCount = 0;
          log(`Still generating (thinking: ${!!currentThinkingContent})`);
        }
      } else {
        // Content still changing
        stableCount = 0;
        lastAnswerContent = currentAnswerContent;
        log(`Answer changed, new length: ${currentAnswerContent.length}`);
      }
    }, 100);  // 100ms interval for fast response
  });
}

// ============ 模式切换功能 ============

/**
 * 豆包模式名称映射
 */
const MODE_NAMES: Record<DoubaoMode, string> = {
  quick: '快速',
  think: '思考',
  expert: '专家'
};

/**
 * 模拟键盘事件
 */
function dispatchKeyEvent(element: HTMLElement, key: string, code: string, keyCode: number): void {
  const event = new KeyboardEvent('keydown', {
    key,
    code,
    keyCode,
    which: keyCode,
    bubbles: true,
    cancelable: true
  });
  element.dispatchEvent(event);
}

/**
 * 找到模式切换按钮
 * 豆包的模式按钮特征：data-testid="deep-thinking-action-button"
 */
function findModeButton(): HTMLElement | null {
  // 方法1: 通过data-testid查找（最可靠）
  const modeContainer = document.querySelector('[data-testid="deep-thinking-action-button"]');
  if (modeContainer) {
    // 找到内层按钮（实际触发菜单的那个）
    const innerButton = modeContainer.querySelector('button');
    if (innerButton) {
      log(`Found mode button via data-testid: ${innerButton.textContent?.substring(0, 20)}`);
      return innerButton as HTMLElement;
    }
    // 如果没有内层按钮，尝试找最近的按钮
    const closestBtn = modeContainer.closest('button');
    if (closestBtn) {
      log(`Found mode button via closest: ${closestBtn.textContent?.substring(0, 20)}`);
      return closestBtn as HTMLElement;
    }
  }

  // 方法2: 通过文本匹配查找
  const buttons = document.querySelectorAll('button');
  const modeKeywords = ['快速', '思考', '专家'];

  for (const btn of buttons) {
    const text = btn.textContent?.trim() || '';
    // 模式按钮只包含模式名称，长度较短
    for (const keyword of modeKeywords) {
      if (text === keyword || (text.includes(keyword) && text.length < 15)) {
        log(`Found mode button via text: ${text}`);
        return btn as HTMLElement;
      }
    }
  }

  error('Mode button not found');
  return null;
}

/**
 * 获取当前模式
 */
function getCurrentMode(): DoubaoMode | null {
  const modeButton = findModeButton();
  if (!modeButton) return null;

  const text = modeButton.textContent || '';
  if (text.includes('思考')) return 'think';
  if (text.includes('专家')) return 'expert';
  return 'quick'; // 默认快速
}

/**
 * 找到菜单项（通过文本匹配）
 */
function findMenuItemByText(text: string): HTMLElement | null {
  const items = document.querySelectorAll('[role="menuitem"]');
  for (const item of items) {
    if (item.textContent?.includes(text)) {
      return item as HTMLElement;
    }
  }
  return null;
}

/**
 * 切换豆包回答模式
 * 使用纯 DOM 操作 + PointerEvent 模拟点击
 *
 * 关键发现：豆包使用 React 指针事件系统，需要 PointerEvent 而非 MouseEvent
 *
 * @param mode 目标模式: 'quick' | 'think' | 'expert'
 * @returns 是否切换成功
 */
async function switchMode(mode: DoubaoMode): Promise<boolean> {
  const modeText = MODE_NAMES[mode];
  log(`Switching to mode: ${mode} (${modeText})`);

  // Step 1: 检查当前模式是否已经是目标模式
  const currentMode = getCurrentMode();
  if (currentMode === mode) {
    log(`Already in ${mode} mode`);
    return true;
  }

  // Step 2: 找到模式按钮
  const modeButton = findModeButton();
  if (!modeButton) {
    error('Mode button not found');
    return false;
  }

  try {
    // Step 3: 使用 PointerEvent 打开菜单
    const rect = modeButton.getBoundingClientRect();
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;

    // 关键：必须使用 PointerEvent，而不是 MouseEvent
    modeButton.dispatchEvent(new PointerEvent('pointerdown', {
      bubbles: true,
      cancelable: true,
      clientX: x,
      clientY: y,
      button: 0,
      pointerType: 'mouse',
      isPrimary: true
    }));

    modeButton.dispatchEvent(new PointerEvent('pointerup', {
      bubbles: true,
      cancelable: true,
      clientX: x,
      clientY: y,
      button: 0,
      pointerType: 'mouse',
      isPrimary: true
    }));

    modeButton.click();
    log('Mode button clicked with PointerEvent');

    // Step 4: 等待菜单出现
    await new Promise(r => setTimeout(r, 200));

    // Step 5: 找到并点击目标菜单项
    const menuItems = document.querySelectorAll('[role="menuitem"]');
    let targetItem: HTMLElement | null = null;

    for (const item of menuItems) {
      const text = item.textContent || '';
      if (text.includes(modeText)) {
        targetItem = item as HTMLElement;
        break;
      }
    }

    if (!targetItem) {
      error(`Menu item "${modeText}" not found`);
      return false;
    }

    targetItem.click();
    log(`Clicked menu item: ${modeText}`);

    // Step 6: 等待模式切换完成
    await new Promise(r => setTimeout(r, 300));

    // Step 7: 验证切换结果
    const newMode = getCurrentMode();
    const success = newMode === mode;

    log(`Mode switch ${success ? 'succeeded' : 'failed'}, current: ${newMode}`);
    return success;

  } catch (e) {
    error(`Failed to switch mode: ${e}`);
    return false;
  }
}

/**
 * Handle FREERIDE_ASK
 */
async function handleAsk(prompt: string, timeout: number, includeThinking: boolean = false, mode?: DoubaoMode): Promise<FreeRideResponse> {
  if (isProcessing) {
    return { success: false, error: 'Another request in progress' };
  }

  isProcessing = true;

  try {
    // Step 0: 如果指定了模式，先切换
    if (mode) {
      log(`Requested mode: ${mode}`);
      const switched = await switchMode(mode);
      if (!switched) {
        log(`Mode switch failed, continuing with current mode`);
        // 不阻断流程，继续执行
      }
    }

    // Step 1: Record current assistant message before sending
    const contentBefore = getLatestAssistantMessage() || '';
    log(`Content before sending: "${contentBefore.substring(0, 50)}..."`);
    log(`Include thinking: ${includeThinking}`);

    // Step 2: Find and fill input
    const inputEl = findInputElement();
    if (!inputEl) {
      return { success: false, error: 'Input not found' };
    }

    if (!fillInputElement(inputEl, prompt)) {
      return { success: false, error: 'Failed to fill input' };
    }

    await new Promise(r => setTimeout(r, 500));

    // Step 3: Click send
    const sendBtn = findSendButton();
    if (!sendBtn) {
      return { success: false, error: 'Send button not found' };
    }

    sendBtn.click();
    log('Send button clicked');

    // Step 4: Wait for NEW response
    const result = await waitForResponse(timeout * 1000, contentBefore);

    // 构建响应
    const response: FreeRideResponse = {
      success: true,
      content: result.content
    };

    // 如果需要，包含思考内容
    if (includeThinking && result.thinking) {
      response.thinking = result.thinking;
    }

    return response;

  } catch (e) {
    error('ASK error:', e);
    return {
      success: false,
      error: e instanceof Error ? e.message : 'Unknown error'
    };
  } finally {
    isProcessing = false;
  }
}

/**
 * Handle FREERIDE_STATUS
 */
function handleStatus(): FreeRideResponse {
  const inputEl = findInputElement();
  const blocks = getMessageBlocks();

  return {
    success: true,
    content: JSON.stringify({
      platform: 'doubao',
      ready: !!inputEl,
      messageBlocks: blocks.length
    })
  };
}

/**
 * Message listener
 */
chrome.runtime.onMessage.addListener((message: FreeRideMessage, _sender, sendResponse) => {
  log('Message:', message.type);

  switch (message.type) {
    case 'FREERIDE_ASK':
      handleAsk(
        message.payload?.prompt || '',
        message.payload?.timeout || 300,
        message.payload?.includeThinking || false,
        message.payload?.mode as DoubaoMode | undefined
      ).then(sendResponse);
      return true;

    case 'FREERIDE_STATUS':
      sendResponse(handleStatus());
      return true;

    default:
      sendResponse({ success: false, error: `Unknown: ${message.type}` });
      return false;
  }
});

log('Content script loaded');
