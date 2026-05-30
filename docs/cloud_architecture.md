# 云端无服务器架构 (Supabase Serverless Architecture)

`overlord` 从最初的纯本地脚本 MVP，现在已经进化为支持**完全无服务器化（Serverless）配置和状态管理**的架构。

只要配置了 `SUPABASE_DB_URL` 环境变量，系统就会无缝接管本地的 JSON 配置文件和进度文件，将所有状态读写迁移到云端 PostgreSQL 数据库（如 Supabase）。

## 架构优势

1. **多端同步**：你可以用本地 Mac 测试生成，也可以用云端 VPS 定时运行，两边进度永远保持强一致。
2. **手机端/移动端管理**：不需要打开代码编辑器或 SSH 登录服务器，直接在手机浏览器登录 Supabase 后台的 Table Editor 即可实时修改订阅源、调整 Prompt。
3. **安全隔离**：配置项与代码解耦，不用担心不小心把私密频道列表 Commit 到开源仓库里。

## 数据库设计

系统在云端维护了两张核心表，使用极简的 Key-Value (JSONB) 设计来兼容历史本地逻辑：

### 1. 运行状态表 `overlord_state`

**功能**：替代原有的本地 `data/processed.json`。
**数据结构**：
- **Table Name**: `overlord_state`
- **Columns**:
  - `key` (VARCHAR, PRIMARY KEY): 固定为 `'state'`。
  - `value` (JSONB): 存储整体运行状态。

**包含的数据**：
- `series`: 各大专栏（如“炼金投研”）的文章期号（Issue Number）进度（例：`"next_issue": 10`）。
- `sources`: 各频道的抓取快照（用于判断频道是否有最新视频更新）。
- `processed_videos`: 所有历史已处理过的视频/播客 ID 及元数据。用于严格去重，避免重复推文。

### 2. 系统配置表 `overlord_config`

**功能**：替代原有的本地 `config/sources.json` 和 `config/writer_profiles/*.md`。
**数据结构**：
- **Table Name**: `overlord_config`
- **Columns**:
  - `key` (VARCHAR, PRIMARY KEY): 配置分类标识。
  - `value` (JSONB): 配置内容。

**包含的数据**：
- **`key='sources'`**：
  存储了所有订阅源的列表，结构与原 `sources.json` 完全一致。在后台修改这行 JSON，下次爬取时立即生效。
- **`key='writer_profiles'`**：
  存储了所有 Prompt 写作模型。值为一个字典结构：`{"模型名": "Markdown 长文本 Prompt"}`。你可以直接在后台修改或新增 Prompt 文本，如 `deep-stock-analysis`、`dehydrate` 等。

## 降级机制 (Fallback)

代码内部采用了平滑的降级机制：
当检测不到 `SUPABASE_DB_URL` 时，系统会自动退回读取本地 `config/sources.json` 和 `data/processed.json` 的模式。这保证了新人 Clone 代码库后依然能通过本地配置直接跑通。
