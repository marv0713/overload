# 小宇宙播客 Source 适配器实施方案

Last updated: 2026-05-17

## 背景

`overlord` 的 source 适配器是插件式架构：`process_sources.py` 通过 `SourceConfig.type` 分发处理逻辑。
YouTube channel 适配器已完整落地。本文档记录接入小宇宙播客（`xiaoyuzhou_podcast`）的设计决策和实施步骤。

---

## 内容获取策略

小宇宙没有官方开放 API，可用方案：

| 方法 | 稳定性 | 说明 |
|------|--------|------|
| **RSS Feed（推荐）** | ★★★★ | 节目有公开 RSS，或通过 RSSHub 桥接 |
| RSSHub 公共路由 | ★★★ | `rsshub.app/xiaoyuzhou/podcast/{podcastId}` |
| 网页抓取 | ★★ | 无 RSS 时降级，维护成本高，暂不实现 |

**MVP 方案**：以 RSS（含 RSSHub）为主入口，用 `feedparser` 解析。
音频内容下载后复用现有 `FasterWhisperTranscriber` 转写，与 YouTube 音频路径完全统一。n
---

## 内容引用与合规策略

播客内容受著作权保护。本系统采用以下方式规避侵权风险：

| 做法 | 策略 |
|------|------|
| ❌ 完整转载文字稿 | 禁止。未经授权完整转载属于侵权 |
| ✅ AI 改写摘要 | 默认做法。Gemini 基于转写内容生成原创性评论文章 |
| ✅ 引用 3-5 句金句 | 允许，需注明来源（著作权法第24条合理引用） |
| ✅ 嵌入原节目链接 | 每篇文章末尾必须附原节目小宇宙链接 |

**文章末尾必须输出来源说明区块**（由 Writer Prompt 强制生成）：

```
### 来源说明
本文内容基于小宇宙播客「{节目名}」第 N 期节目的 AI 辅助整理，
不代表本公众号立场，仅供参考，不构成投资建议。
👉 收听原节目：{小宇宙节目直链}
```

---

## 需要改动的文件

### 新建

#### `src/youtube_to_wechat/xiaoyuzhou.py`
对标 `youtube_channel.py`，对外暴露：

```python
@dataclass
class PodcastEpisode:
    episode_id: str        # RSS guid 或 URL hash，全局唯一
    title: str
    description: str       # RSS summary，作为补充文本
    audio_url: str         # mp3/m4a 直链，供 Whisper 转写
    duration_seconds: int
    published_at: str      # ISO 8601 日期

def fetch_podcast_episodes(rss_url: str, limit: int = 12) -> list[PodcastEpisode]:
    """解析 RSS Feed，返回最新 N 集（最新在前）。"""

def download_episode_audio(audio_url: str, dest_dir: Path) -> Path:
    """下载单集音频文件到 dest_dir，返回本地路径。"""
```

依赖：`feedparser`（加入 `requirements.txt`）。

#### `scripts/process_xiaoyuzhou.py`
单集处理入口，对标 `process_youtube.py`，方便调试：

```bash
PYTHONPATH=src .venv/bin/python scripts/process_xiaoyuzhou.py \
  --rss "https://rsshub.app/xiaoyuzhou/podcast/PODCAST_ID" \
  [--episode-id "EPISODE_GUID"]   # 不传则处理最新一集
```

### 修改

#### `src/youtube_to_wechat/source_config.py`
- `SourceConfigType` 新增 `"xiaoyuzhou_podcast"`。
- `SourceConfig` 新增可选字段 `rss_url: str = ""`。

#### `scripts/process_sources.py`
在 `process_source()` 中按 type 分发：

```python
if source.type == "youtube_channel":
    _process_youtube_source(...)
elif source.type == "xiaoyuzhou_podcast":
    _process_xiaoyuzhou_source(...)
```

`_process_xiaoyuzhou_source` 流程：
1. `fetch_podcast_episodes(rss_url)` 获取剧集列表
2. 过滤已处理 + 时长不足的剧集
3. 下载音频到 `outputs/xiaoyuzhou/{podcast_slug}/{episode_id}/audio/`
4. `FasterWhisperTranscriber.transcribe(audio_path)` 转写
5. `GeminiWriter.write(transcript, meta)` 生成文章
6. 写入 `article.md`、`meta.json`、`run.json`
7. `processed_store.mark_processed(...)`

#### `config/sources.example.json`
新增示例条目：

```json
{
  "type": "xiaoyuzhou_podcast",
  "name": "示例播客名称",
  "url": "https://www.xiaoyuzhoufm.com/podcast/PODCAST_ID",
  "rss_url": "https://rsshub.app/xiaoyuzhou/podcast/PODCAST_ID",
  "series": "炼金投研",
  "priority": 50,
  "min_duration_seconds": 600,
  "writer_profile": "alchemy-research"
}
```

#### `requirements.txt`
新增 `feedparser`。

---

## 输出目录约定

```
outputs/
  xiaoyuzhou/
    {podcast_slug}/
      {episode_id}/
        audio/          # 下载的原始音频
        transcript.txt  # Whisper 转写结果
        meta.json       # 剧集元数据
        article.md      # 生成文章
        article.html    # HTML 渲染
        run.json        # 各阶段运行状态
```

与 YouTube 的 `outputs/youtube/{source_slug}/{video_id}/` 结构保持一致。

---

## 实施顺序

1. 确认目标播客 RSS 源（你提供节目主页 URL，我验证可用性）
2. `requirements.txt` 加 `feedparser`
3. 新建 `src/youtube_to_wechat/xiaoyuzhou.py`
4. 修改 `source_config.py`（新增 type 和 rss_url 字段）
5. 新建 `scripts/process_xiaoyuzhou.py`（单集入口，用于调试）
6. 修改 `scripts/process_sources.py`（type 分发逻辑）
7. 更新 `config/sources.example.json`
8. 端到端测试：单集 → transcript → article → 草稿推送

---

## 待确认

1. **目标播客**：提供小宇宙节目主页 URL，确认是否有 RSS 或 RSSHub 路由。
2. **RSSHub**：是否使用公共实例 `rsshub.app`，还是自部署？（公共实例对小宇宙有时限速）
