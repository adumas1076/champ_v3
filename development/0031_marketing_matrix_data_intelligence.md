# 0031 — Marketing Matrix: Data Intelligence Layer
**Date:** 2026-04-11
**Category:** Marketing Machine — the analytics + scraping + scoring backbone
**Status:** V1 — Architecture document

---

## Why Data Before Logic

> "Logic without data is guessing. Data without logic is noise. Together they're a weapon."

The marketing machine's logic (Click to Client, T-M-B-OFU, scoring, branching) is ONLY as smart as the data feeding it. Without data:
- Content scoring is opinion, not measurement
- Lead scoring is guessing, not profiling
- Ad optimization is hoping, not testing
- Retention is reactive, not predictive

**Data is the fuel. Logic is the engine. Together they compound.**

---

## Data Source Map

### Tier 1: Your Own Platform Analytics (First-Party)

| Platform | API / Method | Key Metrics | Update Frequency |
|---|---|---|---|
| **Google Analytics 4** | GA4 Data API | Traffic sources, bounce rate, session duration, conversion paths, UTM attribution, goal completions | Real-time + daily aggregates |
| **YouTube Analytics** | YouTube Data API v3 + YouTube Studio | Views, watch time, CTR (impressions→clicks), audience retention curves, traffic sources, subscriber gain/loss, revenue, end screen clicks | 48-hour delay on some metrics |
| **Instagram Insights** | Instagram Graph API | Reach, impressions, engagement rate, follower demographics, story exits/replies, reel completion rate, saves | 24-hour delay |
| **TikTok Analytics** | TikTok API for Business | Views, likes, shares, comments, completion rate, traffic sources, follower activity, trending sounds used | 24-48 hour delay |
| **LinkedIn Analytics** | LinkedIn Marketing API | Impressions, engagement rate, CTR, follower demographics, company page analytics | 24-hour delay |
| **Twitter/X Analytics** | X API v2 | Impressions, engagement rate, link clicks, retweets, quote tweets, bookmark rate | Near real-time |
| **Facebook Analytics** | Facebook Graph API | Reach, engagement, ad performance, audience insights, post clicks | 24-hour delay |
| **Email Analytics** | ESP API (Resend/SendGrid) | Open rate, click rate, unsubscribe rate, bounce rate, link heat maps | Real-time |
| **Stripe** | Stripe API | MRR, churn rate, LTV, payment failures, subscription changes, revenue by tier | Real-time |
| **Landing Page** | Vercel Analytics + custom events | Page views, time on page, scroll depth, CTA clicks, form submissions, A/B test results | Real-time |

### Tier 2: Competitor Intelligence (Third-Party)

| Source | Method | What We Get |
|---|---|---|
| **VidIQ Outlier Score** | Scrape VidIQ or reverse-engineer formula (views / channel avg views) | Videos performing 10x+ above channel average — viral content indicators |
| **Competitor YouTube channels** | YouTube Data API (public data) | Upload frequency, view counts, title patterns, description keywords, tag usage |
| **Competitor thumbnails** | YouTube Data API (thumbnail URLs) + vision model analysis | Face position, text placement, color palette, contrast ratio, emotion detection |
| **Competitor titles** | YouTube Data API + NLP analysis | Length, hook type, keyword density, emotional triggers, formula patterns |
| **Competitor Instagram** | Instagram Graph API (public profiles) + scraping | Post frequency, engagement rates, hashtag strategy, content type mix |
| **Competitor TikTok** | TikTok API (public data) | Trending sounds, content formats, posting times, viral mechanics |
| **Competitor websites** | Web scraping (Puppeteer) | Landing page structure, CTA placement, lead magnets, pricing, social proof |
| **Trending topics** | Google Trends API + social listening | What's trending in your niche RIGHT NOW — ride waves |
| **Hashtag performance** | Platform APIs + scraping | Discovery hashtags vs vanity hashtags — which actually drive reach |
| **SEO keywords** | Google Search Console API + scraping | What your audience is searching for — content topics that have demand |

### Tier 3: Content Quality Signals (Derived)

| Signal | Formula | Threshold |
|---|---|---|
| **Hook Score** | First 3s retention (YT) or scroll-stop rate (IG/TT) | Good: >65%, Great: >80% |
| **Retention Score** | Average view duration / total duration | Good: >40%, Great: >60% |
| **Engagement Depth** | (Comments + Saves) / Views | Good: >2%, Great: >5% |
| **Share Velocity** | Shares / first 24h views | Good: >1%, Great: >3% |
| **CTR** | Clicks / Impressions | Good: >4%, Great: >8% |
| **Completion Rate** | Full watches / total views (short-form) | Good: >50%, Great: >70% |
| **Outlier Score** | Video views / channel 90-day avg views | Outlier: >5x, Viral: >10x |
| **Save Rate** | Saves / Views (IG, TikTok) | Good: >2%, Great: >5% |
| **CTA Conversion** | CTA clicks / total views | Good: >1%, Great: >3% |
| **Revenue Per Mille (RPM)** | Revenue / (views / 1000) | Track trend, not absolute |

---

## Scraping & Analysis Pipelines

### Pipeline 1: Thumbnail Intelligence

```
INPUT: Niche keywords + competitor channel IDs

1. Pull top 100 outlier videos from niche (VidIQ score > 5x)
2. Download thumbnail images (YouTube Data API → thumbnail URL)
3. Analyze each with vision model (Gemini Flash):
   - Face detected? Position? Expression?
   - Text overlay? How many words? Font size? Color?
   - Background type? (solid, gradient, photo, screenshot)
   - Color palette (dominant colors, contrast ratio)
   - Visual complexity score
   - Emotional tone (curiosity, shock, authority, excitement)
4. Cluster into patterns:
   - "AI niche winners: close-up face + 3 words + high contrast + blue/orange"
   - "Business niche winners: results screenshot + arrow + number"
5. Score YOUR thumbnails against winning patterns BEFORE publishing
6. Generate 3 alternative thumbnails using top patterns

OUTPUT: Thumbnail pattern library + pre-publish scoring
UPDATE: Weekly (new outliers emerge)
```

### Pipeline 2: Title Intelligence

```
INPUT: Top 100 outlier video titles from niche

1. NLP analysis of each title:
   - Length (characters + words)
   - Hook type: question / stat / contrarian / how-to / story / list
   - Power words: "secret", "proven", "exactly", "mistake", "never"
   - Number usage: present? position? specific or round?
   - Emotional trigger: curiosity / fear / aspiration / urgency
   - Keyword density: niche-specific terms
2. Correlate title patterns with performance:
   - "Questions in title → 2.3x more comments"
   - "Titles with numbers → 1.8x higher CTR"
   - "Titles under 60 chars → 1.5x more clicks on mobile"
3. Build title formula library:
   - Formula A: "How I [RESULT] in [TIME] with [METHOD]" → 78% above avg CTR
   - Formula B: "[NUMBER] [ADJECTIVE] Ways to [OUTCOME]" → 65% above avg CTR
   - Formula C: "Stop [COMMON MISTAKE] (Do THIS Instead)" → 92% above avg CTR
4. Score YOUR titles against formula library
5. Generate 5 alternative titles ranked by predicted CTR

OUTPUT: Title formula library + pre-publish scoring + alternatives
UPDATE: Bi-weekly
```

### Pipeline 3: Content Performance Scoring

```
INPUT: Published content (48 hours post-publish)

1. Pull analytics from platform API
2. Calculate all quality signals (hook, retention, engagement, etc.)
3. Compute weighted content score:
   Hook (30%) + Retention (25%) + Engagement (20%) + Conversion (15%) + Outlier (10%)
4. Compare to:
   - YOUR average (personal benchmark)
   - NICHE average (competitive benchmark)
   - TOP 10% (aspiration benchmark)
5. Classify: VIRAL (>8.0) | HIT (6.0-8.0) | SOLID (4.0-6.0) | WEAK (2.0-4.0) | MISS (<2.0)
6. Extract lesson:
   - VIRAL/HIT → "What worked?" → add to pattern library
   - WEAK/MISS → "What failed?" → add to anti-pattern library
7. Feed lesson back into Marketing Operator's knowledge

OUTPUT: Content scorecard + lesson + updated pattern/anti-pattern libraries
UPDATE: Every 48 hours per published piece
```

### Pipeline 4: Posting Schedule Optimization

```
INPUT: 90 days of your engagement data

1. Group engagement by: hour of day × day of week × platform
2. Identify YOUR peak engagement windows (not generic "best times")
3. Cross-reference with competitor posting times:
   - Option A: Post 30 min before competitors (steal the attention)
   - Option B: Post 2 hours after (ride the wave they created)
4. Factor in audience timezone distribution
5. Generate personalized posting calendar per platform
6. Auto-adjust monthly as audience behavior shifts

OUTPUT: Optimal posting schedule per platform
UPDATE: Monthly recalibration
```

### Pipeline 5: Ad Creative Intelligence (Gian + Hormozi)

```
INPUT: 6 ad angles × 5 hooks = 30 ad variants

1. Launch all 30 with validation spend ($20-50 each)
2. After 3-5 days, pull metrics: CPC, CTR, CPL, conversion rate
3. Rank all 30 top to bottom
4. Apply 70/20/10:
   - 70% budget → slight variations of top 2 winners
   - 20% budget → significant variations (different person, setting)
   - 10% budget → completely new angles with 3 hooks each
5. Track creative fatigue (when did CTR start declining?)
6. Auto-rotate: kill underperformers Monday, promote winners Friday
7. Log: which angles + hooks + visuals win for THIS audience

OUTPUT: Winning ad library + fatigue timeline + creative rotation schedule
UPDATE: Weekly cycle (Gian's 7-day optimization)
```

### Pipeline 6: Competitive Benchmarking

```
INPUT: 5-10 competitor channels/accounts

1. Pull public metrics monthly:
   - Posting frequency
   - Average engagement rate
   - Content type mix (video/image/text/carousel)
   - Follower growth rate
   - Top performing content (outlier score)
2. Build niche benchmark table:
   - Average CTR in your niche
   - Average engagement rate
   - Average posting frequency
   - Content type distribution
3. Rank YOUR performance against benchmarks
4. Identify gaps: "Your CTR is top 30% but your posting frequency is bottom 50%"
5. Generate recommendations: "Increase posting from 3/week to 5/week to match niche leaders"

OUTPUT: Monthly competitive report + gap analysis + recommendations
UPDATE: Monthly
```

---

## How This Feeds The Marketing Matrix

| Pipeline | Feeds Into | Impact |
|---|---|---|
| Thumbnail Intelligence | Marketing Operator content creation | Thumbnails that compete with top 10% from day 1 |
| Title Intelligence | Marketing Operator + Content Engine | Titles optimized for CTR before publishing |
| Content Performance Scoring | Autoresearch loop + QA Operator | Every piece gets graded, lessons extracted, rules updated |
| Posting Schedule | Content Engine scheduler | Post at YOUR optimal times, not generic "best practices" |
| Ad Creative Intelligence | Lead Gen Operator + Gian framework | Systematic ad testing, not guessing |
| Competitive Benchmarking | Operations Operator + Research | Know where you stand and where to focus |

---

## Integration Points with Existing Code

| What Exists | Where | What We Add |
|---|---|---|
| Content Engine (80%) | content_engine/ | Wire analytics APIs, add scoring engine, connect autoresearch |
| Analytics adapters (6 platforms) | content_engine/analytics/ | Upgrade from basic pull to full signal extraction |
| Eval system | content_engine/eval.py | Add weighted multi-signal scoring (not just Lamar/Gary Vee criteria) |
| Autoresearch loop | content_engine/autoresearch.py | Feed pattern recognition output back into rules |
| Repurpose pipeline | content_engine/pipeline/repurpose.py | Add pre-publish QA scoring before scheduling |
| Scheduler | content_engine/pipeline/scheduler.py | Add optimal timing engine (Pipeline 4) |
| Funnel tracking | content_engine/pipeline/funnel.py | Add UTM attribution from Google Analytics |
| Marketing Operator | operators/configs/marketing.yaml | Add thumbnail + title intelligence as superpowers |
| QA Operator | operators/configs/qa.yaml | Add content scoring thresholds to evaluation |
| Research Operator | (tools) | Competitor scraping + trending topic detection |