# YouTube Competition Analysis - Project Roadmap

> **This file is the source of truth for the project.**
> Follow this plan even when conversation context is lost.
> Do not deviate from architectural decisions without explicit discussion.

---

## Project Goal

Build an internal competitive-intelligence system for YouTube content that answers:

**"What video ideas are working right now for competitors, so we can create similar content while the trend is still hot?"**

---

## Core Philosophy (Never Forget)

1. **Relative performance > absolute numbers** - A video is "good" only relative to what is normal for that channel
2. **Timing matters** - We care about first hours/days, not lifetime success
3. **Cross-channel validation** - One creator popping off is not a trend
4. **Mechanical signals first, AI second** - Metrics decide what's important

---

## System Layers (Build in Order)

| Layer | Name | Status | Description |
|-------|------|--------|-------------|
| 1 | Tracking & Baselines | **COMPLETE** | Observe videos, capture snapshots, build baselines |
| 1.5 | Deployment & Dashboard | **COMPLETE** | Deploy tracker, seed data, build internal UI |
| 2 | Trend Detection | **CURRENT** | Detect hot topics across multiple channels |
| 3 | HIT Detection | NOT STARTED | Detect individual breakout videos |
| 4 | Channel Discovery | NOT STARTED | Auto-discover and prune competitor channels |

**Current: Trend Detection is next.**

---

## Part 1: Tracking & Baselines

### What Part 1 Delivers

- [x] Track 20-30 YouTube channels
- [x] Detect new video uploads (polling for dev, WebSub for production)
- [x] Capture 8 snapshots per video at fixed time windows
- [x] Separate Shorts vs Long-form content
- [x] Calculate rolling baselines (medians) per channel
- [x] Monitor system health (snapshot coverage)

### What Part 1 Does NOT Do

- No alerts
- No HIT detection
- No trend analysis
- No AI/grouping
- No UI (backend only)

---

## Technical Decisions (Locked In)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Backend Language | Python | User preference |
| Database | Supabase (PostgreSQL) | User preference, real-time features |
| Discovery (Dev) | RSS Polling | Works locally, no public URL needed |
| Discovery (Prod) | WebSub | Real-time notifications from YouTube |
| Shorts Detection | URL check method | Most reliable (`youtube.com/shorts/{id}`) |
| Snapshot Windows | 8 fixed windows | Minimum needed for breakout detection |
| Baseline Source | Any video with snapshot | No need to wait for completed videos (14 days) |
| **Tracker Hosting** | Railway | Easy deploys, supports long-running Python |
| **Dashboard** | Next.js | Full control over UI, deploys to Vercel |
| **Seed Baselines** | Manual with source tracking | Bootstrap with VidIQ data, replaced by real data |

---

## Snapshot Schedule (Fixed)

Every video gets exactly 8 snapshots:

| Window | Time After Publish | Purpose |
|--------|-------------------|---------|
| T+0h | Immediate | Anchor point |
| T+1h | 1 hour | First algorithm test |
| T+6h | 6 hours | Early adoption |
| T+12h | 12 hours | Momentum confirmation |
| T+24h | 24 hours | Standard benchmark |
| T+48h | 48 hours | Decay detection |
| T+7d | 7 days | Trend confirmation |
| T+14d | 14 days | Final archive, tracking stops |

**After T+14d: No more snapshots. Video marked as `completed`.**

---

## Database Schema

### Table: `channels`
```sql
channel_id          TEXT PRIMARY KEY      -- YouTube channel ID (UC...)
channel_name        TEXT NOT NULL
subscriber_count    INTEGER
total_videos        INTEGER
created_at          TIMESTAMP             -- When we added this channel
last_checked_at     TIMESTAMP             -- Last verification
is_active           BOOLEAN DEFAULT true  -- False = paused tracking
```

### Table: `videos`
```sql
video_id            TEXT PRIMARY KEY      -- YouTube video ID
channel_id          TEXT REFERENCES channels(channel_id)
published_at        TIMESTAMP NOT NULL    -- When YouTube published it
discovered_at       TIMESTAMP NOT NULL    -- When we first saw it
title               TEXT
duration_seconds    INTEGER
is_short            BOOLEAN               -- True if Short, False if Long
tracking_status     TEXT DEFAULT 'active' -- 'active' | 'completed' | 'deleted'
tracking_until      TIMESTAMP             -- published_at + 14 days
```

### Table: `snapshots`
```sql
id                  SERIAL PRIMARY KEY
video_id            TEXT REFERENCES videos(video_id)
captured_at         TIMESTAMP NOT NULL
window_type         TEXT NOT NULL         -- '0h', '1h', '6h', '12h', '24h', '48h', '7d', '14d'
views               INTEGER NOT NULL
likes               INTEGER NOT NULL
comments            INTEGER NOT NULL
```

### Table: `scheduled_snapshots`
```sql
id                  SERIAL PRIMARY KEY
video_id            TEXT REFERENCES videos(video_id)
window_type         TEXT NOT NULL
scheduled_for       TIMESTAMP NOT NULL
status              TEXT DEFAULT 'pending' -- 'pending' | 'completed' | 'failed' | 'skipped'
attempts            INTEGER DEFAULT 0
last_error          TEXT
```

### Table: `channel_baselines`
```sql
channel_id          TEXT REFERENCES channels(channel_id)
is_short            BOOLEAN               -- Separate baselines for Shorts vs Long
window_type         TEXT                  -- '1h', '6h', '24h', '48h'
median_views        INTEGER
median_likes        INTEGER
median_comments     INTEGER
sample_size         INTEGER               -- Videos used for calculation
source              TEXT DEFAULT 'calculated'  -- 'manual' (seed data) or 'calculated' (real data)
updated_at          TIMESTAMP
PRIMARY KEY (channel_id, is_short, window_type)
```

**Note:** `source = 'manual'` indicates seed data from VidIQ. UI shows these as "Estimated".
Once system calculates real baselines, they update to `source = 'calculated'`.

### Table: `buckets`
```sql
id                  UUID PRIMARY KEY DEFAULT gen_random_uuid()
name                TEXT NOT NULL
description         TEXT
color               TEXT              -- Hex color for UI
created_at          TIMESTAMP DEFAULT now()
```

### Table: `bucket_channels` (many-to-many)
```sql
bucket_id           UUID REFERENCES buckets(id) ON DELETE CASCADE
channel_id          TEXT REFERENCES channels(channel_id) ON DELETE CASCADE
created_at          TIMESTAMP DEFAULT now()
PRIMARY KEY (bucket_id, channel_id)
```

### Table: `websub_subscriptions`
```sql
channel_id          TEXT PRIMARY KEY REFERENCES channels(channel_id)
feed_url            TEXT NOT NULL
callback_url        TEXT NOT NULL
subscribed_at       TIMESTAMP
expires_at          TIMESTAMP
is_active           BOOLEAN DEFAULT true
```

---

## Python Project Structure

```
youtube-tracker/
├── src/
│   ├── __init__.py
│   ├── config.py                 # Environment variables, settings
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py         # Supabase client
│   │   ├── channels.py           # Channel operations
│   │   ├── videos.py             # Video operations
│   │   ├── snapshots.py          # Snapshot operations
│   │   └── baselines.py          # Baseline calculations
│   │
│   ├── youtube/
│   │   ├── __init__.py
│   │   ├── api.py                # YouTube Data API wrapper
│   │   └── shorts_detector.py    # URL-based Shorts detection
│   │
│   ├── discovery/
│   │   ├── __init__.py
│   │   ├── base.py               # Abstract interface
│   │   ├── polling.py            # RSS polling (dev mode)
│   │   └── websub.py             # WebSub handler (prod mode)
│   │
│   ├── scheduler/
│   │   ├── __init__.py
│   │   └── snapshot_worker.py    # Processes scheduled snapshots
│   │
│   └── jobs/
│       ├── __init__.py
│       ├── discovery_job.py      # Runs polling discovery
│       ├── baseline_job.py       # Updates channel baselines
│       └── health_job.py         # Monitors snapshot coverage
│
├── main.py                       # Entry point
├── requirements.txt
├── .env.example
└── ROADMAP.md                    # This file
```

---

## Implementation Checklist

### Phase 1: Foundation
- [x] **1.1** Create Supabase project
- [x] **1.2** Create database tables (schema above)
- [x] **1.3** Set up Python project structure
- [x] **1.4** Create `.env` with Supabase credentials
- [x] **1.5** Implement Supabase connection (`database/connection.py`)

### Phase 2: YouTube Integration
- [x] **2.1** Get YouTube Data API key
- [x] **2.2** Implement YouTube API wrapper (`youtube/api.py`)
- [x] **2.3** Implement Shorts detection (`youtube/shorts_detector.py`)
- [x] **2.4** Test: Fetch stats for a known video

### Phase 3: Video Discovery
- [x] **3.1** Implement polling discovery (`discovery/polling.py`)
- [x] **3.2** Implement video insertion logic (`database/videos.py`)
- [x] **3.3** Implement scheduled snapshot creation
- [x] **3.4** Test: Add a channel, detect new video, create schedule

### Phase 4: Snapshot System
- [x] **4.1** Implement snapshot worker (`scheduler/snapshot_worker.py`)
- [x] **4.2** Implement snapshot storage (`database/snapshots.py`)
- [x] **4.3** Implement retry logic for failed snapshots
- [x] **4.4** Implement video completion (after T+14d)
- [x] **4.5** Test: Full lifecycle of a video (all 8 snapshots)

### Phase 5: Baselines
- [x] **5.1** Implement baseline calculator (`database/baselines.py`)
- [x] **5.2** Implement Shorts vs Long separation
- [x] **5.3** Implement baseline job (`jobs/runner.py`)
- [x] **5.4** Test: Calculate baselines for a channel with 5+ videos

### Phase 6: Operations
- [x] **6.1** Implement health monitoring (in snapshot coverage)
- [x] **6.2** Implement logging throughout
- [x] **6.3** Create main.py entry point
- [x] **6.4** Test: System running and collecting data

### Phase 7: Production Readiness ✅
- [x] **7.1** Implement WebSub subscription (`discovery/websub.py`)
- [x] **7.2** Implement subscription renewal job
- [x] **7.3** Add FastAPI web server for webhook endpoints
- [x] **7.4** Switch from polling to WebSub (set DISCOVERY_MODE=websub)
- [x] **7.5** Add WebSub latency tracking
- [ ] **7.6** Monitor WebSub reliability over time (ongoing)

---

## Part 1.5: Deployment & Dashboard (CURRENT)

### Phase 8: Deploy Tracker to Railway
- [x] **8.1** Add `source` column to `channel_baselines` table
- [x] **8.2** Add channel URL resolution (accepts @handles and URLs)
- [x] **8.3** Create GitHub repo and push code
- [x] **8.4** Create Railway project and connect to GitHub
- [x] **8.5** Configure environment variables in Railway
- [x] **8.6** Verify tracker runs 24/7 and collects data

### Phase 9: Seed Data Import ✅
- [x] **9.1** User provides spreadsheet with 20-30 channels + estimated 24h medians
- [x] **9.2** Create import script for channels and seed baselines
- [x] **9.3** Import all channels with `source = 'manual'` baselines (11 channels imported from VidIQ)
- [x] **9.4** Verify channels are being tracked

### Phase 10: Next.js Dashboard ✅
- [x] **10.1** Create Next.js project (dashboard/ folder with shadcn/ui)
- [x] **10.2** Connect to Supabase
- [x] **10.3** Build channel list page
- [x] **10.4** Build video grid with thumbnails
- [x] **10.5** Show video performance vs baseline
- [x] **10.6** Mark estimated baselines as "Estimated" in UI
- [x] **10.7** Deploy to Vercel
- [x] **10.8** Add multi-channel filter
- [x] **10.9** Add performance filter (All/Above Baseline/Potential HITs/Below Baseline)
- [x] **10.10** Add bucket system for grouping channels (database tables + UI)
- [x] **10.11** Add channel dialog with VPH estimation and bucket assignment
- [x] **10.12** Add WebSub latency tracking (logs time between publish and webhook receipt)

### What Dashboard Shows (MVP) ✅
- Stats overview (total videos, channels, snapshots, avg performance)
- Bucket filter (card-based, color-coded channel groups)
- Multi-channel filter with checkboxes
- Performance filter (All/Above Baseline/Potential HITs/Below)
- Video grid with thumbnails, titles, publish date
- Performance metrics: views at 1h, 6h, 24h, 48h
- Baseline comparison: "2.5x above median" or "0.4x below"
- Add channel dialog with YouTube URL resolution

---

## Part 2: Trend Detection (CURRENT)

### Goal
Detect hot topics that are working across multiple channels, so we can create similar content while the trend is still hot.

### Trend Detection Rules
```
A topic is TRENDING if:
  - At least 3 different channels posted about it
  - Only counts videos performing >= 1.5x baseline
  - Within the last 14 days
```

### How It Works

1. **Topic Extraction (per video at 24h snapshot)**
   - Fetch transcript via `youtube-transcript-api`
   - Fallback to title + description if no transcript
   - Send to AI (DeepSeek via OpenRouter): "Extract 1-3 specific topics"
   - Store raw topics in `video_topics` table

2. **Topic Clustering (daily job)**
   - Gather all topics from videos in last 14 days with 1.5x+ performance
   - Send to AI: "Group similar topics into clusters"
   - Store normalized clusters in `topic_clusters` table

3. **Trend Calculation (daily job)**
   - For each cluster, count unique channels
   - Filter clusters with 3+ channels
   - Calculate avg performance, video count
   - Store in `trending_topics` table

### Database Tables

#### Table: `video_topics`
```sql
id                  SERIAL PRIMARY KEY
video_id            TEXT REFERENCES videos(video_id)
topic               TEXT NOT NULL           -- Raw topic from AI
extracted_at        TIMESTAMP DEFAULT now()
```

#### Table: `topic_clusters`
```sql
id                  UUID PRIMARY KEY DEFAULT gen_random_uuid()
normalized_name     TEXT NOT NULL           -- "ChatGPT Prompting"
created_at          TIMESTAMP DEFAULT now()
updated_at          TIMESTAMP DEFAULT now()
```

#### Table: `cluster_topics` (maps raw topics to clusters)
```sql
cluster_id          UUID REFERENCES topic_clusters(id) ON DELETE CASCADE
topic               TEXT NOT NULL           -- Raw topic string
created_at          TIMESTAMP DEFAULT now()
PRIMARY KEY (cluster_id, topic)
```

#### Table: `trending_topics`
```sql
id                  SERIAL PRIMARY KEY
cluster_id          UUID REFERENCES topic_clusters(id)
channel_count       INTEGER NOT NULL
video_count         INTEGER NOT NULL
avg_performance     DECIMAL(5,2)            -- e.g., 2.3 = 2.3x baseline
video_ids           TEXT[]                  -- Array of video IDs
detected_at         TIMESTAMP DEFAULT now()
period_start        TIMESTAMP               -- 14 days ago
period_end          TIMESTAMP               -- now
```

### Phase 11: Trend Detection Implementation
- [ ] **11.1** Create database tables for topics and trends
- [ ] **11.2** Add `youtube-transcript-api` to requirements
- [ ] **11.3** Implement transcript fetcher with fallback
- [ ] **11.4** Set up OpenRouter client for AI calls
- [ ] **11.5** Implement topic extraction (per video)
- [ ] **11.6** Implement topic clustering (daily job)
- [ ] **11.7** Implement trend calculation
- [ ] **11.8** Create backfill script for existing videos
- [ ] **11.9** Add trending topics page to dashboard
- [ ] **11.10** Test with real data

---

## Part 3: HIT Detection (After Trend Detection)

### Phase 12: HIT Detection Logic
- [ ] **12.1** Define HIT thresholds (relative velocity > 2.0, etc.)
- [ ] **12.2** Implement HIT calculation in Python
- [ ] **12.3** Store HIT flags in database
- [ ] **12.4** Add HIT indicators to dashboard
- [ ] **12.5** Test with real data

### HIT Detection Rules (Preview)
```
HIT if:
  relative_velocity > 2.0
  AND relative_engagement > 1.2
  AND growth_acceleration >= 0
  AND views_24h >= MIN_VIEWS (e.g., 500)
```

---

## Baseline Calculation Logic

**IMPORTANT: Baselines calculate from ANY video with a snapshot at that window.**
No need to wait for videos to be "completed" (14 days). This means:
- 1h baseline available after 1 hour (with 5+ videos)
- 24h baseline available after 24 hours
- etc.

```python
# For each channel, for each window (1h, 6h, 24h, 48h):
# 1. Get all snapshots at this window for this channel
# 2. Filter by content type (Shorts vs Long)
# 3. Calculate median (middle value when sorted)
# 4. Store in channel_baselines

# Example:
# Channel X, Long videos, T+24h
# Views: [8000, 9000, 7500, 12000, 8500]
# Sorted: [7500, 8000, 8500, 9000, 12000]
# Median: 8500

# Why median? One viral video (10M views) would destroy an average.
# Median is resistant to outliers.

# Configuration:
# BASELINE_SAMPLE_SIZE = 30   # Max videos to use
# BASELINE_MIN_SAMPLE = 5     # Min videos required
```

---

## Key Metrics (Part 1 Outputs)

### Per Video (stored)
- `views_1h`, `views_6h`, `views_24h`, `views_48h` (from snapshots)

### Per Channel (calculated)
- `channel_median_views_1h` (rolling, last 20-50 videos)
- `channel_median_views_6h`
- `channel_median_views_24h`
- `channel_median_views_48h`
- Separate values for Shorts vs Long

### Operational
- `snapshot_coverage` = actual_snapshots / expected_snapshots

---

## What Part 2 Will Use (Preview)

Part 2 (HIT Detection) will use Part 1 data to calculate:

```
relative_velocity = video_views_24h / channel_median_views_24h

HIT if:
  relative_velocity > 2.0
  AND relative_engagement > 1.2
  AND growth_acceleration >= 0
  AND views_24h >= MIN_VIEWS
```

**Part 1 just collects the data. Part 2 makes the decisions.**

---

## Rules to Follow

1. **Never skip snapshots** - Even if a video seems uninteresting, complete all 8 windows
2. **Never mix Shorts and Long baselines** - They have different performance profiles
3. **Polling is temporary** - Always keep WebSub as the production target
4. **Store everything** - Raw data is cheap, recalculation is expensive
5. **Medians, not averages** - Resist outlier corruption
6. **14 days then stop** - No value in tracking old videos

---

## Environment Variables Needed

```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
YOUTUBE_API_KEY=AIza...
DISCOVERY_MODE=polling  # or "websub" in production
POLLING_INTERVAL_MINUTES=15
SNAPSHOT_WORKER_INTERVAL_MINUTES=5
BASELINE_UPDATE_HOURS=12

# WebSub (required when DISCOVERY_MODE=websub)
WEBSUB_CALLBACK_URL=https://creatrr.app/webhooks/youtube
PORT=8080  # Railway sets this automatically
```

---

## Revision History

| Date | Change |
|------|--------|
| 2024-01-15 | Initial plan created |
| 2024-01-16 | Part 1 implementation complete |
| 2024-01-19 | Baseline calculation updated: now uses ANY video with snapshot at window, not just completed videos. This allows baselines to be available immediately (after min sample reached) instead of waiting 14 days. |
| 2024-01-20 | Added Part 1.5: Deployment & Dashboard. Plan to deploy tracker to Railway, seed with VidIQ data, build Next.js dashboard. Added `source` column to baselines schema for tracking manual vs calculated data. |
| 2024-01-23 | Implemented WebSub for real-time video notifications. Added FastAPI web server, webhook endpoints, subscription management. Domain: creatrr.app |
| 2024-01-26 | Phase 9 (Seed Data) complete: 11 channels imported from VidIQ. Phase 10 (Dashboard) complete: Next.js + shadcn/ui deployed to Vercel. Added bucket system for channel grouping, multi-channel filter, performance filter, add channel dialog. Added WebSub latency tracking. Part 1.5 complete - ready for HIT Detection. |

---

**END OF ROADMAP**
