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
