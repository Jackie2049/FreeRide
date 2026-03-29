# FreeRide

**Claude Code的外挂工具** - 将重计算任务卸载到网页版AI助手（豆包），节省API token消耗。

## 核心理念

- **Claude Code是核心调度agent**（具有强大的规划和工具调用能力）
- **FreeRide是外挂工具**，提供与网页AI交互的能力
- **重计算任务委托给豆包**（免费/已订阅的服务）
- Claude Code只做**调度和结果整合**，消耗少量token

## 架构

```
Claude Code --CLI--> FreeRide CLI --HTTP--> Native Host --WebSocket--> Chrome Extension --> 豆包网页
     │                                                                                    │
     └────────────────────────────── 返回结果沿原路返回 ◀─────────────────────────────────┘
```

## 功能特性

- ✅ **多模式支持**: 快速(quick)、思考(think)、专家(expert) 三种回答模式
- ✅ **思考内容捕获**: 可选择包含AI思考过程的完整回复
- ✅ **自动模式切换**: 根据参数自动切换豆包的回答模式
- ✅ **稳定连接**: WebSocket持久连接 + Service Worker保活机制

## 安装

### 1. 运行安装脚本

```bash
cd FreeRide/native
./install.sh
```

### 2. 构建Chrome扩展

```bash
cd FreeRide/extension
npm install
npm run build
```

### 3. 加载Chrome扩展

1. 打开 Chrome/Chromium
2. 访问 `chrome://extensions/`
3. 启用"开发者模式"（右上角开关）
4. 点击"加载已解压的扩展程序"
5. 选择 `extension` 目录（或构建后的 `dist` 目录）

### 4. 启动Native Host

```bash
python3 FreeRide/native/native_host.py
```

### 5. 打开豆包

在浏览器中打开 https://www.doubao.com/

## 使用

### 从命令行使用

```bash
# 向豆包提问（快速模式）
freeride ask "什么是Python？"

# 使用思考模式
freeride ask "分析一下快速排序的时间复杂度" --mode think

# 使用专家模式
freeride ask "研究级问题：GPR52在精神分裂症中的作用" --mode expert

# 包含思考过程
freeride ask "复杂问题" --mode think --include-thinking

# 检查状态
freeride status
```

### CLI 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--mode, -m` | 回答模式: quick/think/expert | quick |
| `--include-thinking, -T` | 包含思考过程 | false |
| `--timeout, -t` | 超时时间(秒) | 300 |
| `--host` | Native Host地址 | 127.0.0.1 |
| `--port, -p` | Native Host端口 | 8765 |

### Claude Code中使用

Claude Code 可以通过 Bash 工具调用 FreeRide：

```
! freeride ask "分析一下这段代码的时间复杂度：def fib(n): ..." --mode think
```

## Token节省示例

```
用户: "帮我分析这个复杂的项目架构"

Claude Code:
1. 思考：这个分析任务比较重，可以让豆包来做
2. 调用: freeride ask "请分析以下项目架构..." --mode think
3. 等待: FreeRide把问题发给豆包，等待回复
4. 获取: 豆包的分析结果返回
5. 整合: 基于结果继续与用户对话

Token消耗:
- 直接用Claude Code API: 可能消耗 2000+ tokens
- 通过FreeRide: 只消耗调度和整合的 ~200 tokens
```

---

## 给 AI Coding Agents 的使用指南

> 如果你是一个 AI Coding Agent（如 Claude Code、Cursor、Cline 等），这个板块帮助你快速掌握如何使用 FreeRide。

### 什么时候应该使用 FreeRide？

**✅ 适合使用 FreeRide 的场景：**

| 场景 | 示例 |
|------|------|
| 复杂代码分析 | "分析这个项目的架构和设计模式" |
| 算法复杂度分析 | "分析这个排序算法的时间复杂度" |
| 知识问答 | "解释一下 Redis 分布式锁的实现原理" |
| 文档理解 | "总结这篇论文的核心观点" |
| 多轮调研 | "梳理某位学者的完整履历" |
| 需要深度思考的问题 | 使用 `--mode think` 获取推理过程 |

**❌ 不适合使用 FreeRide 的场景：**

- 需要修改文件、执行命令的任务（FreeRide 只能问答）
- 需要访问本地代码库的任务
- 简单的确认性问题（直接回答更高效）
- 涉及敏感/私密信息的问题

### 模式选择指南

```
问题复杂度判断：

简单问题（直接回答）
    ↓
中等复杂度 → freeride ask "..." --mode quick
    ↓
需要分析/推理 → freeride ask "..." --mode think
    ↓
研究级/学术问题 → freeride ask "..." --mode expert
```

### 前置条件检查

使用前确保：
1. Native Host 正在运行：`python3 native/native_host.py`
2. Chrome 扩展已加载
3. 豆包页面已打开（https://www.doubao.com/）

检查命令：
```bash
freeride status
```

### 完整调用示例

```bash
# 示例1：代码分析
freeride ask "分析以下代码的时间复杂度和空间复杂度：
def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)
" --mode think

# 示例2：知识问答（含思考过程）
freeride ask "解释 Redis 的持久化机制 RDB 和 AOF 的区别" --mode think --include-thinking

# 示例3：多轮调研
freeride ask "梳理 Python 异步编程的发展历史" --mode expert
```

### 工作流集成

```
用户请求
    ↓
判断任务类型
    ↓
┌─────────────────────────────────┐
│ 需要重计算/知识问答？            │
│         ↓ 是                    │
│ 调用 FreeRide                   │
│ 等待响应                        │
│ 整合结果                        │
└─────────────────────────────────┘
    ↓
需要文件操作/命令执行？
    ↓ 是
自己处理
    ↓
返回给用户
```

### 最佳实践

1. **Token 节省策略**：把大段分析任务委托给 FreeRide，你只做调度和整合
2. **多轮调研**：连续调用 FreeRide，逐步深入
3. **分工明确**：FreeRide 负责问答，你负责文件操作和命令执行

### 故障排除速查

| 问题 | 解决方案 |
|------|----------|
| 连接失败 | `freeride status` 检查状态 |
| 扩展未连接 | 刷新扩展和豆包页面 |
| 超时 | 增加 `--timeout` 参数 |
| 思考内容未返回 | 添加 `--include-thinking` 参数 |

## 目录结构

```
FreeRide/
├── extension/           # Chrome扩展
│   ├── src/
│   │   ├── background.ts  # Service Worker
│   │   ├── content.ts     # 内容脚本（注入+捕获+模式切换）
│   │   └── types.ts       # 类型定义
│   ├── manifest.json
│   └── dist/              # 构建输出
│
├── native/              # Native Messaging Host
│   ├── native_host.py     # Bridge Server (HTTP + WebSocket)
│   └── install.sh         # 安装脚本
│
├── cli/                 # CLI工具
│   └── freeride.py        # 命令行入口
│
└── tests/               # 测试用例
    ├── test_cli.py        # CLI单元测试
    ├── test_native_host.py # Native Host单元测试
    ├── test_integration.py # 集成测试
    └── run_tests.sh       # 测试运行脚本
```

## 开发

```bash
# 构建扩展
cd extension
npm install
npm run build

# 开发模式（监视变化）
npm run dev
```

## 测试

```bash
# 运行所有单元测试
cd FreeRide
python3 tests/test_cli.py -v
python3 tests/test_native_host.py -v

# 或使用测试脚本
./tests/run_tests.sh

# 运行集成测试（需要先启动服务器）
python3 native/native_host.py &
python3 tests/test_integration.py -v
```

## API 参考

### HTTP Endpoints

| 端点 | 方法 | 说明 |
|------|------|------|
| `/status` | GET | 检查服务器状态 |
| `/ask` | POST | 发送问题到豆包 |
| `/switch_mode` | POST | 切换豆包回答模式 |

### WebSocket

连接到 `ws://127.0.0.1:8765/ws` 进行双向通信。

## 故障排除

### 扩展无法连接到Native Host

1. 确认Native Host正在运行
2. 确认HTTP端口8765未被占用
3. 检查Native Host终端是否有错误信息

### Content Script无法找到输入框

1. 确认已打开 doubao.com
2. 确认页面已完全加载
3. 检查浏览器控制台是否有错误信息
4. 尝试刷新扩展和页面

### CLI连接超时

1. 确认Native Host正在运行
2. 检查 `freeride status` 返回结果
3. 确认Chrome扩展已加载且豆包页面已打开

### 模式切换失败

1. 确认豆包页面已完全加载
2. 检查浏览器控制台日志
3. 扩展使用纯DOM操作切换模式，无需额外依赖

## 更新日志

### v0.3.0
- 新增: GitHub Actions 自动发布流程
- 新增: 单元测试和集成测试
- 优化: 版本号同步 (manifest/package/README)
- 改进: 安装方式简化，通过 Release 下载 ZIP 包

### v0.2.0
- 新增: 三种回答模式支持 (quick/think/expert)
- 新增: 思考内容捕获功能 (--include-thinking)
- 新增: 自动展开思考卡片
- 优化: 纯DOM操作实现模式切换，移除pyautogui依赖
- 优化: 改进内容提取，正确分离思考内容和回答内容

### v0.1.0
- 初始版本
- 基本的问答功能
- Chrome扩展 + Native Host + CLI

## License

MIT
