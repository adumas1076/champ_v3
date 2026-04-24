# 009 — Outlier Score Strategy (V1)
**Generated from:** Research on outlier content patterns + Anthony's watch list
**Date:** 2026-04-18
**Status:** V1 — The banger-finding engine

**What this is:** The system that finds content performing 5-10x above average in Anthony's niche, reverse-engineers WHY it worked, and adapts the pattern. This is Step 1 of the Content Formula — the intelligence layer that feeds every other step.

---

## What Is An Outlier?

An outlier is content performing **5-10x above a creator's channel average**.

If Dan Koe averages 10K likes per tweet and one tweet gets 120K likes — that's a 12x outlier. The tweet itself did the work, not his brand name. That means the CONTENT PATTERN is what worked. And that pattern is transferable.

**Key principle:** Study outliers, not averages. Average performance tells you what your audience tolerates. Outliers tell you what breaks through.

---

## Why Outliers Matter

- **Average content tells you what works for existing audience**
- **Outlier content tells you what breaks through to NEW audiences**
- Outliers reveal hidden audience preferences regular analytics miss
- Outlier patterns compound — use a proven pattern and you start ahead
- **100% of viral content was an outlier before it was viral**

---

## THE OUTLIER DETECTION ENGINE

### Detection Formula

```
OUTLIER SCORE = post_performance / creator_30_day_average

Where performance = weighted metric:
  - 50% engagement (likes + comments + shares + saves)
  - 30% reach (views / impressions)
  - 20% virality signals (replays, profile visits, follows from content)

Scoring:
  1.0x – 1.5x:  Normal post (ignore)
  1.5x – 3x:    Above average (note)
  3x – 5x:      Strong post (log pattern)
  5x – 10x:     OUTLIER (study + steal pattern)
  10x+:         VIRAL BANGER (deep analyze + replicate)
```

### What Gets Tracked

```yaml
outlier_detection:
  targets:
    - watch_list_creators  # From anthony_dna.yaml Section 8
    - adjacent_creators    # Discovered via platform recommendations
    - trending_content     # Platform-native trending sections
    
  platforms_monitored:
    - twitter
    - instagram
    - tiktok
    - linkedin
    - youtube
    
  detection_frequency: daily
  deep_analysis_frequency: weekly
  minimum_outlier_threshold: 5x  # Only 5x+ gets deep-analyzed
```

---

## THE 10-POINT OUTLIER ANALYSIS TEMPLATE

Every outlier found gets decomposed into patterns:

```
OUTLIER BREAKDOWN:

1. SOURCE
   - Creator: _______________
   - Platform: _______________
   - Follower count: _______________ (at time of post)
   - Post URL: _______________
   - Performance vs average: ___x

2. TOPIC
   - What is this about? (one sentence)
   - What's the core promise/hook?
   - Is the topic trending or evergreen?
   - Does it touch a current event?

3. HOOK (First 3 seconds / first line)
   - Exact opening words/visual
   - Hook type (Curiosity/Contrarian/Result/Question/Story/Shock/Challenge/Empathy)
   - Pattern interrupt used?

4. STRUCTURE
   - Hook → Tension → Payoff → Loop?
   - Hook → Body → CTA?
   - Other format?
   - Length: ___s (video) or ___ words (text)

5. THUMBNAIL / COVER
   - Face? (yes/no)
   - Expression if face
   - Text overlay? (how many words)
   - Color palette
   - Contrast level

6. TITLE / CAPTION
   - Exact text
   - Formula match (from 008_title_intelligence.md)
   - Length
   - Specificity (numbers? names? dates?)

7. CTA
   - What action was requested?
   - Was it strong or soft?
   - Keyword trigger?

8. EMOTIONAL DRIVER
   - What emotion did it trigger? (anger, curiosity, inspiration, schadenfreude, hope)
   - Identity resonance? ("this is me" factor)
   - Controversy level (1-10)

9. PLATFORM-SPECIFIC WINS
   - Why this post specifically worked on THIS platform
   - Could it work on other platforms or is it platform-specific?
   - Hashtag strategy
   - Timing (day + hour)

10. THE TRANSFERABLE PATTERN
    - What's the ONE thing we can steal?
    - How would Anthony execute this same pattern?
    - What's the Anthony-specific adaptation?
```

---

## THE WEEKLY OUTLIER RESEARCH WORKFLOW

Every week, the system runs this pipeline:

```
MONDAY (Automated):
  1. Pull last 7 days of content from all watch-list creators
  2. Calculate each creator's 30-day rolling average
  3. Flag posts with outlier score ≥ 3x
  4. Log basic data on 3x-5x posts
  5. Deep-analyze 5x+ posts using 10-point template

TUESDAY (Automated):
  6. Compile weekly report: top 10 outliers in niche
  7. Extract transferable patterns
  8. Tag patterns by type (hook format / structure / thumbnail / title / topic)
  9. Add winning patterns to pattern library

WEDNESDAY (Automated):
  10. Match outlier patterns to upcoming content slots
  11. Generate pattern-adapted content for Anthony
  12. Flag pattern-adapted content in content queue

WEEKLY REPORT TO ANTHONY (Thursday):
  - Top 10 outliers found this week
  - Top 3 patterns to steal this week
  - 5-10 pattern-adapted content pieces ready to review
  - Pattern library updates (what's trending in the niche)
```

---

## THE PATTERN LIBRARY (Grows Every Week)

As outliers are found, patterns accumulate:

```yaml
pattern_library:
  hook_patterns:
    - pattern_id: "question_front_loaded"
      success_rate_in_niche: 8.2/10
      example: "Why does every AI course feel outdated in 3 months?"
      anthony_adaptations: 3  # Already used 3 times, scored 7.8 avg
      
    - pattern_id: "number_plus_negative"
      success_rate: 7.9/10
      example: "3 reasons your AI output looks generic"
      anthony_adaptations: 2
      
    - pattern_id: "tbtntt_signature"  # Owned by Anthony
      success_rate: [TBD]
      example: "[claim]. That's true. But that's not the truth."
      owner: anthony
      
  structure_patterns:
    - pattern_id: "story_to_framework"
      success_rate: 8.5/10
      template: "Hook story → extract lesson → generalize framework → CTA"
      
  thumbnail_patterns:
    - (from 007_thumbnail_intelligence.md)
    
  title_patterns:
    - (from 008_title_intelligence.md)
    
  topic_patterns:
    - pattern_id: "counterintuitive_advice"
      success_rate: 9.1/10
      example: "Why the obvious advice is actually the wrong advice"
      
    - pattern_id: "behind_the_scenes_numbers"
      success_rate: 8.7/10
      example: "Here's exactly what [X] costs / looks like / requires"
```

---

## ADAPTING PATTERNS (Not Copying)

Critical distinction: we STEAL PATTERNS, not CONTENT.

### Pattern Stealing (GOOD):
```
Outlier: "3 things your boss is lying to you about"
Anthony adaptation: "3 things AI gurus are lying to you about"
  - Same structure (number + accusation)
  - Same hook type (contrarian)
  - Different topic (Anthony's lane)
  - Different voice (Anthony's)
```

### Content Copying (BAD):
```
Outlier: "3 things your boss is lying to you about"
Bad copy: "3 things your boss is lying to you about" (same title)
  - Same structure
  - Same hook
  - Same topic (stolen)
  - Same voice (cloned) — this is plagiarism
```

**The rule:** Steal the FORMAT. Bring your own CONTENT. Bring your own VOICE. The result sounds like Anthony, not the original creator.

---

## THE REVERSE-ENGINEERING FRAMEWORK

For each outlier, ask these 5 questions:

### 1. Why did THIS post work when others didn't?
Not "why is this post good" — specifically: what's different about this one vs the creator's average post? That's the leverage point.

### 2. What psychological driver fired?
- Curiosity gap?
- FOMO?
- Identity resonance?
- Controversy?
- Vulnerability?
- Status?
- Fear?

### 3. What would happen if this ran on a different platform?
- Would the same hook work on Twitter as on TikTok?
- Would the format translate?
- Does the pattern cross platforms or is it platform-specific?

### 4. Does Anthony have the raw material for this?
- Does Anthony have a story/proof/framework that fits this pattern?
- If yes → create pattern-matched content
- If no → note pattern for future when material is available

### 5. What would make it BETTER than the original?
- Sharper hook?
- More specific numbers?
- Deeper payoff?
- Anthony-signature twist (like the TBTNTT format)?

---

## OUTLIER-DRIVEN CONTENT GENERATION

Flow for turning an outlier into Anthony content:

```
OUTLIER FOUND: Dan Koe's "How I Made $2M With 1 Product" (11x outlier)
  ↓
PATTERN EXTRACTED: Result Formula + specific number + specific outcome
  ↓
MATCH TO ANTHONY'S MATERIAL:
  - Has Anthony done a similar result? YES — Cocreatiq revenue
  - Specific number? "800 sessions with Champ"
  - Specific outcome? "Built an AI OS"
  ↓
ANTHONY ADAPTATION:
  "How I built an AI OS in 800 sessions with one AI partner"
  ↓
SCRIPT GENERATION (12-step formula):
  - Hook: "How I built an AI OS in 800 sessions" (Result formula)
  - Tension: Beat 1 — started with nothing, Beat 2 — 30 errors, Beat 3 — it worked
  - Payoff: Cocreatiq is live, running, real
  - Loop: End with "Day 1 still feels like day 1"
  ↓
PUBLISH TO PLATFORMS:
  - YouTube long-form (primary — matches source)
  - LinkedIn post (business audience match)
  - Twitter thread (adapted)
  - Instagram Reel (repurposed)
  ↓
SCORE 48HRS LATER:
  Did the Anthony adaptation outperform Anthony's own average?
  If yes → pattern confirmed for Anthony's audience
  If no → pattern doesn't translate, remove from active rotation
```

---

## PLATFORM-SPECIFIC OUTLIER TOOLS

### YouTube
- **VidIQ** (paid) or **TubeBuddy** — outlier score filters built-in
- **YouTube Studio Analytics** — competitor insights
- Track: top videos by creator, 30-day rolling average, CTR + retention

### TikTok
- **Platform search** — sort by "most liked" in niche hashtags
- **Creator profile** — browse highest-view videos
- Track: views, shares, completion rate, avg watch time

### Twitter/X
- **Advanced search** — filter by min likes + user
- **Typefully** or **Hypefury** — tweet performance tools
- Track: impressions, engagement rate, quote tweets (deep engagement signal)

### Instagram
- **Explore page** — algorithmic outlier surfacing
- **Creator profile grid** — visual outlier spotting (the one post with 10x more comments)
- Track: likes, saves, shares, profile visits from post

### LinkedIn
- **LinkedIn analytics** (manual — platform doesn't have third-party outlier tools yet)
- **Creator search** — filter by engagement volume
- Track: impressions, reactions, comments, reshares

---

## THE "TIME MACHINE" TACTIC

Powerful move: don't just study NEW outliers. Study OLD outliers from 2-3 years ago that specific niches haven't caught up to yet.

```
Study: Top 50 outlier posts from 2023-2024 in Anthony's niche
Ask: Are these patterns still working? Have they been over-used?
Find: Patterns that worked AMAZING but haven't been replicated by current creators
Exploit: Run the old pattern with 2026 context → often performs as well or better
```

**Why this works:** Audience memory is short. A pattern that worked 2 years ago can feel "fresh" today if most current creators aren't using it.

---

## CONTENT TO BANK (Building Over Time)

Track which patterns are confirmed winners for Anthony specifically:

```yaml
anthony_confirmed_patterns:
  # Built over time from actual post performance
  
  - pattern: "TBTNTT signature"
    anthony_avg_score: 8.4/10
    status: "proven — use 2-3x/week"
    
  - pattern: "Building in public with real numbers"
    anthony_avg_score: 8.1/10
    status: "proven — use 2x/week"
    
  - pattern: "20-years-perspective hot take"
    anthony_avg_score: 7.9/10
    status: "proven — use 1-2x/week"
    
  # As more posts publish, this grows
```

---

## OUTLIER RESEARCH FOR THE SIGNATURE SERIES

### "That's True But That's Not The Truth" — Outlier Strategy
- Scan for common "easy AI" claims in the niche
- Find the "True" side (what people are saying)
- Build the "Not The Truth" payoff (what you know from 20 years + building)
- Each outlier in niche = potential TBTNTT episode

### "Me & Champ — Road to Generational Wealth" — Outlier Strategy
- Scan "building in public" posts — what moments get highest engagement?
- Failure posts > win posts (usually 2-3x engagement)
- Specific dollar amounts > vague ones
- Real screenshots > claims
- Each confirmed pattern = how to format the next Me & Champ episode

---

## V1 → V2 EVOLUTION

- **Week 1-4:** Manual outlier detection, system builds initial pattern library
- **Week 5-8:** Pattern library has 50+ patterns scored
- **Week 9-12:** System auto-matches patterns to Anthony's content slots
- **Month 4+:** Autoresearch loop updates patterns every cycle — the library self-refreshes

---

## THE FEEDBACK LOOP

```
OUTLIER DETECTED
  ↓
PATTERN EXTRACTED + ADDED TO LIBRARY
  ↓
PATTERN USED IN ANTHONY CONTENT
  ↓
48HRS LATER: ANTHONY POST SCORED
  ↓
IF POST SCORE > ANTHONY'S AVERAGE:
  → Pattern WORKS for Anthony's audience
  → Use more
  → Flag as "proven for Anthony"
  
IF POST SCORE = ANTHONY'S AVERAGE:
  → Pattern works but isn't exceptional
  → Keep in rotation
  
IF POST SCORE < ANTHONY'S AVERAGE:
  → Pattern doesn't translate
  → Remove from active rotation
  → Log WHY (different audience? execution issue? platform mismatch?)
```

The system learns what patterns transfer from OTHER creators to ANTHONY'S audience. After 90 days, the pattern library is Anthony-specific — not generic.

---

## THE MOAT

Most creators never do outlier research systematically. They:
- Post and hope
- Copy what they saw once
- Follow gurus telling them what "should" work

Anthony's system:
- Studies 100+ outliers/month across 5 platforms
- Extracts transferable patterns automatically
- Tests patterns against Anthony's own data
- Builds a private library of what works for HIS audience

After 6 months: Anthony's content machine knows his audience better than any agency ever could. That knowledge compounds. That's the moat.
