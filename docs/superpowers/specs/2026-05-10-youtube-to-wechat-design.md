# YouTube 视频到公众号草稿 MVP 设计

日期：2026-05-10

## 背景

目标是先做一个小而稳定的脚本：给定一个 YouTube 视频 URL，提取视频内容中的观点，生成一篇适合公众号草稿箱的文章。第一版先处理单条视频，用来验证内容获取、转写、文章生成和本地输出效果。公众号 API 推送在本地文章效果稳定后接入。

示例输入：

```text
https://www.youtube.com/watch?v=6C7FjGs22g8
```

## MVP 范围

第一版只做单视频处理：

- 输入一个 YouTube 视频 URL。
- 获取视频基础信息：标题、频道、发布日期、视频 ID。
- 优先获取字幕文本。
- 如果没有字幕，预留音频下载和语音转写接口，但可以先报出明确错误。
- 清洗字幕或转写文本。
- 生成公众号文章草稿，包括标题、摘要、正文、核心观点、来源链接和人工核查点。
- 输出本地文件，不直接发布。

第一版不做：

- 自动扫描订阅频道。
- 多视频批处理。
- 自动发布公众号。
- 小程序或 Web 后台。
- 复杂版权/事实核查自动化。

## 关键约束

YouTube 官方字幕下载接口通常要求调用方拥有编辑该视频的权限，因此公开公开视频不一定能通过官方 API 直接下载字幕。实际实现中，第一版优先使用 `yt-dlp` 获取公开视频可用字幕；如果字幕不可用，再进入音频转写路径。

微信公众号自动化建议先推送到草稿箱，不直接群发。生成内容需要人工确认，避免事实错误、版权风险和标题不当。

## 模块设计

### 1. CLI 入口

文件建议：

```text
scripts/process_youtube.py
```

职责：

- 解析命令行参数。
- 校验 YouTube URL。
- 协调整个处理流程。
- 控制输出目录。
- 打印清晰的运行结果和错误信息。

命令形式：

```bash
python3 scripts/process_youtube.py "https://www.youtube.com/watch?v=6C7FjGs22g8"
```

### 2. 视频元数据模块

文件建议：

```text
src/youtube_to_wechat/youtube_meta.py
```

职责：

- 提取视频 ID。
- 调用 `yt-dlp` 或后续 YouTube Data API 获取视频标题、频道、发布日期、描述、缩略图。
- 将元数据标准化成内部结构。

输出示例：

```json
{
  "video_id": "6C7FjGs22g8",
  "url": "https://www.youtube.com/watch?v=6C7FjGs22g8",
  "title": "...",
  "channel": "...",
  "published_at": "...",
  "thumbnail_url": "..."
}
```

### 3. Transcript 获取模块

文件建议：

```text
src/youtube_to_wechat/transcript.py
```

职责：

- 优先尝试下载人工字幕。
- 其次尝试下载自动字幕。
- 支持语言优先级配置，例如 `zh-Hans`、`zh`、`en`。
- 将 VTT/SRT 清洗为纯文本。
- 如果字幕不可用，返回结构化错误，交给转写模块处理。

第一版可以先实现字幕路径。音频转写接口保留，但不强制实现。

### 4. 音频转写模块

文件建议：

```text
src/youtube_to_wechat/transcriber.py
```

职责：

- 在字幕不可用时下载音频。
- 调用转写服务生成 transcript。
- 输出与字幕模块一致的文本结构。

第一版建议做成接口占位：

```text
Transcriber.transcribe(video_url) -> TranscriptResult
```

后续可接：

- OpenAI Whisper / gpt-4o-transcribe。
- 本地 whisper.cpp。
- 第三方语音转写服务。

### 5. 文本清洗模块

文件建议：

```text
src/youtube_to_wechat/cleaner.py
```

职责：

- 去掉字幕时间戳、重复行、音乐/掌声标记。
- 合并过短字幕片段。
- 保留必要段落边界。
- 输出 `transcript.txt`。

### 6. 文章生成模块

文件建议：

```text
src/youtube_to_wechat/writer.py
```

职责：

- 将视频元数据和 transcript 发送给模型。
- 生成公众号文章结构。
- 要求模型避免逐字搬运原视频内容。
- 标记事实待核查点。
- 保留来源链接。

输出结构：

```json
{
  "title": "...",
  "digest": "...",
  "article_markdown": "...",
  "key_points": ["...", "..."],
  "source_url": "...",
  "review_notes": ["...", "..."]
}
```

### 7. HTML 渲染模块

文件建议：

```text
src/youtube_to_wechat/render.py
```

职责：

- 将 Markdown 转成公众号可用 HTML。
- 控制标题层级、段落、引用、列表格式。
- 后续接微信公众号草稿接口时，确保 HTML 符合微信限制。

### 8. 本地输出模块

文件建议：

```text
src/youtube_to_wechat/output.py
```

职责：

- 创建输出目录。
- 写入元数据、transcript、Markdown、HTML。
- 记录本次运行状态。

目录结构：

```text
outputs/youtube/6C7FjGs22g8/
  meta.json
  transcript.txt
  article.md
  article.html
  run.json
```

### 9. 微信公众号草稿模块

文件建议：

```text
src/youtube_to_wechat/wechat.py
```

职责：

- 获取和缓存 `access_token`。
- 上传封面图，得到 `thumb_media_id`。
- 创建公众号草稿。
- 返回草稿 `media_id`。

第一版暂不接入，等本地文章质量满意后再实现。

需要的环境变量：

```text
WECHAT_APPID
WECHAT_APPSECRET
WECHAT_AUTHOR
WECHAT_DEFAULT_THUMB_MEDIA_ID
```

### 10. 状态存储模块

文件建议：

```text
src/youtube_to_wechat/store.py
```

职责：

- 记录已处理的视频 ID。
- 避免定时任务重复处理。
- 保存处理状态、错误信息、输出路径。

第一版可以用 JSON 文件，后续改 SQLite。

```text
data/processed.json
```

## 数据流

```text
YouTube URL
  -> CLI
  -> video metadata
  -> transcript fetch
  -> transcript clean
  -> article generation
  -> markdown/html render
  -> local outputs
  -> later: WeChat draft API
```

## 配置设计

第一版最少配置：

```text
.env
OPENAI_API_KEY=...
```

后续定时处理固定博主时增加：

```yaml
sources:
  - type: youtube_channel
    name: Example Channel
    channel_id: UCxxxx
    language_priority: ["zh-Hans", "zh", "en"]
    enabled: true
```

## 错误处理

需要明确区分以下错误：

- 无法访问 YouTube。
- 视频不存在或不可公开访问。
- 没有可用字幕。
- 音频下载失败。
- 转写失败。
- 模型生成失败。
- 输出文件写入失败。
- 微信 API 调用失败。

每次运行都写入 `run.json`，方便排查。

## 测试策略

第一阶段测试：

- URL 解析测试。
- VTT/SRT 清洗测试。
- Markdown/HTML 输出测试。
- 无字幕时错误提示测试。

第二阶段测试：

- 使用真实视频跑一次端到端。
- 用固定 transcript fixture 验证文章生成结构。
- 微信草稿接口使用 mock 测试，避免真实接口消耗额度。

## 开发拆解

### 阶段 1：本地单视频闭环

- 建立 Python 项目目录。
- 实现 CLI。
- 实现视频 ID 解析。
- 接入 `yt-dlp` 获取元数据和字幕。
- 实现字幕清洗。
- 输出 `meta.json` 和 `transcript.txt`。

验收标准：

- 对示例视频运行命令后，能得到元数据和 transcript。
- 如果字幕不可用，错误信息明确。

### 阶段 2：生成公众号文章

- 设计文章生成 prompt。
- 实现模型调用。
- 输出结构化结果。
- 渲染 `article.md` 和 `article.html`。

验收标准：

- 文章不是简单摘要，而是有观点、有结构、有来源。
- 输出包含人工核查点。

### 阶段 3：定时任务和去重

- 加入 `processed.json` 或 SQLite。
- 增加固定 URL/频道配置。
- 支持定时执行时只处理一条新内容。

验收标准：

- 已处理视频不会重复生成。
- 定时任务失败时可从日志定位原因。

### 阶段 4：公众号草稿箱

- 实现 access token 获取与缓存。
- 实现封面素材处理。
- 实现新增草稿。
- 将 `article.html` 推送到公众号草稿箱。

验收标准：

- 运行后公众号后台出现草稿。
- 脚本不自动群发。

### 阶段 5：工作流/小程序演进

后续可以把 CLI 逻辑封装成 API：

```text
POST /jobs/youtube
GET /jobs/:id
GET /articles/:id
POST /articles/:id/push-wechat-draft
```

小程序或工作流平台只负责触发、查看结果和人工确认，核心处理逻辑复用当前 Python 模块。

## 推荐技术栈

- Python 3。
- `yt-dlp`：获取公开视频元数据、字幕、音频。
- `ffmpeg`：音频转写前的格式处理。
- `openai` SDK 或兼容模型 SDK：生成文章。
- `python-dotenv`：读取本地密钥。
- `markdown` 或 `mistune`：Markdown 转 HTML。
- JSON 文件起步，后续 SQLite。

## 安全与合规

- 不把 API key 写入仓库。
- 不自动发布，只推草稿。
- 文章保留来源链接。
- 避免大段复述原视频内容。
- 对事实性判断输出人工核查点。

## 当前实现优先级

下一步优先实现阶段 1 和阶段 2：

```text
输入 YouTube URL
  -> 拿字幕
  -> 生成 transcript.txt
  -> 生成 article.md/article.html
```

公众号草稿箱接入放在本地输出效果稳定之后。
