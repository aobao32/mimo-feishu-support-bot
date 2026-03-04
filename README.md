# MiMo 飞书 Kiro 技术支持 Agent

基于 [Strands Agents SDK](https://github.com/strands-agents/sdk-python) + [MiMo-V2-Flash](https://github.com/XiaomiMiMo/MiMo) 构建的飞书机器人，专注回答 [Kiro](https://kiro.dev) IDE/CLI 相关技术问题。

## 一、功能

- 通过飞书 WebSocket 长连接接收用户消息，实时回复
- 接入 MiMo-V2-Flash 大模型（OpenAI 兼容接口）
- 内置工具：知识库查询、Kiro 官方文档抓取、GitHub Issues 搜索
- 每用户独立 Agent 实例，支持多轮对话上下文
- 不活跃 Agent 自动回收（默认 48 小时）

## 二、项目结构

```
mimo-feishu-agent/
├── main.py              # 入口，启动飞书 WS 客户端 + asyncio 事件循环
├── agent_service.py     # Agent 管理，每用户独立实例
├── feishu_gateway.py    # 飞书消息收发网关
├── config.py            # 配置管理（敏感信息从环境变量读取）
├── kb_tool.py           # 知识库查询工具
├── web_tools.py         # 文档抓取 & GitHub Issues 搜索工具
├── logger.py            # 日志模块（终端 + 按日滚动文件）
├── knowledge_base/      # 知识库目录（放入 .md 文件）
├── prompts/             # System Prompt 目录
├── pyproject.toml       # 项目配置 & 依赖声明
└── uv.lock              # 依赖锁定文件
```

## 三、环境要求

- Python >= 3.10
- [uv](https://docs.astral.sh/uv/) 包管理器

## 四、快速开始

### 1. 安装 uv

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或通过 pip
pip install uv

# 或通过 Homebrew (macOS)
brew install uv
```

安装完成后验证：

```bash
uv --version
```

### 2. 初始化项目环境

```bash
# 克隆项目后进入目录
cd mimo-feishu-agent

# 创建虚拟环境并安装依赖（uv 会自动读取 pyproject.toml）
uv sync
```

如需安装开发依赖（测试框架等）：

```bash
uv sync --extra dev
```

### 3. 配置环境变量

运行前需设置以下环境变量：

| 环境变量 | 必填 | 说明 |
|---------|------|------|
| `MIMO_API_KEY` | ✅ | MiMo-V2-Flash 模型 API Key |
| `APP_ID` | ✅ | 飞书开放平台应用 App ID |
| `APP_SECRET` | ✅ | 飞书开放平台应用 App Secret |

```bash
export MIMO_API_KEY="your-mimo-api-key"
export APP_ID="your-feishu-app-id"
export APP_SECRET="your-feishu-app-secret"
```

### 4. 配置 Prompts 和知识库

项目需要 `prompts/` 和 `knowledge_base/` 两个目录：

- `prompts/kiro_agent_prompt.md`（必须）：Agent 的 System Prompt 文件，定义机器人的角色和行为规则
- `knowledge_base/*.md`（可选）：Markdown 格式的知识库文件，如 `KB_1.md`。Agent 会自动扫描并在需要时调用

```bash
# 创建 System Prompt 文件（必须，否则启动报错）
vim prompts/kiro_agent_prompt.md

# 添加知识库文件（可选）
cp your_kb_file.md knowledge_base/KB_1.md
```

### 5. 启动

```bash
uv run python main.py
```

## 五、飞书应用配置

使用前需在[飞书开放平台](https://open.feishu.cn/)完成以下配置：

1. 创建企业自建应用，获取 App ID 和 App Secret
2. 开启机器人能力
3. 添加权限：`im:message`、`im:message:send_as_bot`、`im:message.reactions:create`
4. 订阅事件：`im.message.receive_v1`
5. 选择 WebSocket 长连接模式

## 六、License

Apache-2.0
