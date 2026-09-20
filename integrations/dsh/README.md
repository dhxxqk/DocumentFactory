# DocumentFactory + DeepSeek Harness

DocumentFactory 通过官方 `@deepseek-ai/dsh-mcp-client` 以本地 stdio 方式接入 DSH。MCP 是薄适配层；所有审计和规范化仍由 DocumentFactory Core 执行。

## 前置条件

1. 安装 DocumentFactory MCP extra：`python -m pip install -e ".[mcp]"`。
2. 安装与当前 DSH 相同发布线的官方 MCP client。官方 `@deepseek-ai/dsh` 已将该 client 作为依赖提供。
3. 设置：
   - `DOCUMENT_FACTORY_ROOT`：仓库绝对路径；
   - `DOCUMENT_FACTORY_PYTHON`：该仓库虚拟环境 Python 的绝对路径。
4. 修改任何已有 `cordis.patch.yml` 前先备份；只追加 `documentfactory.cordis.yml` 中的 insert 行，不覆盖已有内容。
5. 用 `dsh --profile web --dump-config` 和 `dsh --profile headless --dump-config` 核验最终 composition。

工具注册名固定为：

- `mcp__documentfactory__format_document`
- `mcp__documentfactory__audit_document`
- `mcp__documentfactory__list_presets`

用户要求统一 DOCX 格式时让 Agent 自主选择 `format_document`。工具返回后，Agent 必须对 formatted DOCX 与 Markdown Validation Report 调用 DSH `present`；只回复路径不算交付。after lint 仍有 ERROR 时不得宣称全部合格。

不应授意 Agent 使用 shell、Python 脚本或手工 XML 修改同一 DOCX。编号、TOC、GUI、HTTP MCP、WorkBuddy 和 Office 插件均不属于此集成。
