# 财务报表解析智能体项目

本项目用于学习

## 启动项目

### 1. 安装依赖

项目使用 `uv` 管理依赖：

```powershell
uv sync
```

如果没有安装 `uv`，先安装：

```powershell
pip install uv
```

### 2. 配置模型

修改根目录下的 `config.yaml`：

```yaml
llm:
  api_key: "你的 API Key"
  base_url: "https://api.deepseek.com"
  model: "deepseek-v4-flash"
```

### 3. 启动服务

```powershell
uv run uvicorn fin_pdf_agent.app:app --reload
```

启动后访问：

- 页面：`http://127.0.0.1:8000`
- 健康检查：`http://127.0.0.1:8000/health`
- 接口文档：`http://127.0.0.1:8000/docs`

## 进度：
### 已完成：
1.agent.py框架
2.memory.py的基本功能，主要是使用openai sdk的session来管理上下文
3.context.py目前用于构建系统提示词。
沙箱智能体已添加
### 未完成
未真正加载工具
未真正加载skills

### 未来的扩展
1.memory.py中添加用户个性化长期记忆
2.memory.py添加上下文token计算和智能压缩功能
3.需要将window sandbox改为创建临时的windows用户来进行。

### 存在的问题：
1.考虑到打包时，path中的项目根目录路可能存在加载错误的问题。
2.没有考虑到代码的生命周期
