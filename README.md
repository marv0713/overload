# overlord

`overlord` 是一个本地优先的内容处理 MVP：从公开内容源抓取素材，转成适合微信公众号草稿箱的文章。当前第一条路径是 YouTube 频道到公众号草稿。

## 能做什么

- 从单个 YouTube 视频 URL 获取元数据和字幕。
- 从配置的 YouTube 频道里扫描候选视频。
- 记录每个频道的处理进度，避免重复处理。
- 按全局系列编号生成公众号文章。
- 按不同博主/视频类型选择不同 writer profile。
- 生成本地 `article.md`、`article.html`、`transcript.txt`、`meta.json` 和 `run.json`。
- 可选推送到微信公众号草稿箱，不自动发布。

## 核心概念

- **source**：内容来源适配器。当前是 `youtube_channel`，后续可扩展小宇宙、博客等。
- **transcript**：供模型处理的正文文本，可能来自字幕、音频转写或正文抽取。
- **writer profile**：写作模板。用于区分单公司深度拆解、市场评论、访谈等文章结构。
- **processed store**：本地 JSON 进度记录，默认是 `data/processed.json`，不提交到仓库。
- **compare evaluation**：字幕和音频转写的对比评估流程，不是默认发布路径。

## 目录结构

```text
config/
  sources.example.json          # 可提交的示例来源配置
  writer_profiles/              # 可提交的写作模板
scripts/
  process_youtube.py            # 单视频入口
  process_sources.py            # 配置来源批处理入口
  push_wechat_draft.py          # 推送微信公众号草稿
  generate_cover.py             # 生成封面图
src/youtube_to_wechat/
  *.py                          # 核心模块
tests/
  test_*.py                     # unittest 测试
```

本地运行产生的 `data/`、`outputs/`、`.env`、`config/sources.json` 都会被 `.gitignore` 忽略。

## 安装

建议使用 Python 3.12：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

系统还需要能运行 `yt-dlp`。依赖安装后，代码会优先使用环境里的 `yt-dlp`，找不到时会尝试 `python -m yt_dlp`。

## 配置

复制环境变量示例：

```bash
cp .env.example .env
```

需要生成文章时配置：

```text
GEMINI_API_KEY=
```

需要推送公众号草稿时再配置：

```text
WECHAT_APPID=
WECHAT_APPSECRET=
WECHAT_AUTHOR=
```

复制来源配置示例：

```bash
cp config/sources.example.json config/sources.json
```

`config/sources.json` 是本地配置，不提交。字段说明：

- `type`：当前支持 `youtube_channel`。
- `name`：来源名称。
- `url`：YouTube 频道地址。
- `series`：公众号系列名。
- `priority`：全局队列优先级，数字越小越先处理。
- `min_duration_seconds`：过滤短视频。
- `writer_profile`：使用 `config/writer_profiles/<name>.md`。
- `compare_evaluation`：默认 `none`。

## 运行

单视频提取字幕和本地输出：

```bash
PYTHONPATH=src .venv/bin/python scripts/process_youtube.py "https://www.youtube.com/watch?v=VIDEO_ID" --skip-audio
```

查看配置来源下一步会处理哪些视频：

```bash
PYTHONPATH=src .venv/bin/python scripts/process_sources.py --dry-run --max-items 5
```

处理配置来源中的下一条视频，只生成本地 transcript 和占位文章：

```bash
PYTHONPATH=src .venv/bin/python scripts/process_sources.py --max-items 1
```

处理配置来源中的下一条视频，并调用 Gemini 生成文章：

```bash
PYTHONPATH=src .venv/bin/python scripts/process_sources.py --generate-article --max-items 1
```

推送本地文章到微信公众号草稿箱：

```bash
PYTHONPATH=src .venv/bin/python scripts/push_wechat_draft.py \
  outputs/youtube/<source_slug>/<video_id>/article.md \
  --cover outputs/youtube/<source_slug>/<video_id>/cover.png
```

生成封面图：

```bash
PYTHONPATH=src .venv/bin/python scripts/generate_cover.py \
  --ticker "MSFT 微软" \
  --subtitle "Ackman AI 换仓" \
  --issue "No.002" \
  --hook "价值洼地，还是暗藏杀机？" \
  --output outputs/youtube/<source_slug>/<video_id>/cover.png
```

## 队列规则

`process_sources.py` 会构建一个全局候选队列：

- 所有来源共享同一个 `series` 编号，例如 `No.001`、`No.002`。
- 先按 `priority` 排序。
- 对已有处理记录的来源，只处理该来源最新已处理视频之后发布的新视频。
- 对新加入、没有历史记录的来源，只选最新一条符合时长要求的视频，避免一次性回填旧内容。
- 每次默认只处理 1 条，可通过 `--max-items` 调整。

## Writer Profiles

writer profile 放在 `config/writer_profiles/`：

- `deep-stock-analysis.md`：单公司/少数公司深度投研。
- `market-commentary.md`：市场评论、行业趋势、多公司横向讨论。

通用合规要求在 `src/youtube_to_wechat/writer.py`，profile 只负责补充结构和风格。生成文章时会去掉开头免责声明，仅保留文末免责声明。

## 微信排版

微信公众号草稿推送使用 `src/youtube_to_wechat/wechat.py` 里的 Markdown 转 HTML 逻辑。当前样式针对手机阅读做了处理：

- 不使用 `text-align: justify`，避免 iPhone 窄屏中英混排时字距被拉大。
- 段落和列表左对齐。
- 保留适度行高和较小段间距。

## 测试

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

## 安全边界

- 不提交 `.env`。
- 不提交真实 `config/sources.json`。
- 不提交 `data/processed.json`。
- 不提交 `outputs/` 下的生成文章、封面或草稿素材。
- 只创建公众号草稿，不自动发布。
