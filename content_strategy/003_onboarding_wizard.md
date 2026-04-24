# 003 — Content DNA Onboarding Wizard
**Date:** 2026-04-18
**Status:** V1 — Client 0 test ready
**Purpose:** Extract all client inputs needed to power the Content Factory
**Delivery:** Onboarding Operator runs this conversationally (voice or text). Outputs structured YAML that feeds directly into the system.
**Part of:** $3K Cocreatiq Setup Fee

---

## Wizard Principles

1. **Conversational, not a form.** Operator asks, client answers, operator follows up. Never feels like data entry.
2. **Examples at every step.** "Here's what a good answer looks like..." prevents blank-page paralysis.
3. **Progressive disclosure.** Only show the next question when the current one is answered.
4. **Auto-save + resume.** Takes 60-90 minutes total. Can be broken into sessions.
5. **The Operator distills.** Client talks naturally. Operator extracts structured outputs.
6. **Client approves the distillation.** Before locking anything, the Operator shows the client: "Here's how I heard you. Does this capture it?"
7. **Outputs are final but editable.** Once locked, the Content Factory starts running. Client can adjust anytime in dashboard.

---

## Wizard Flow (10 Sections)

```
SECTION 1: THE FOUNDATION          (WHO + WHY + ENEMY)
  ↓
SECTION 2: BRAND VOICE             (How you sound)
  ↓
SECTION 3: STORY BANK              (Your 20 years distilled)
  ↓
SECTION 4: CONTENT PILLARS         (3-5 topics you own)
  ↓
SECTION 5: YOUR OFFER              (What they're buying)
  ↓
SECTION 6: VISUAL IDENTITY         (Brand assets + feel)
  ↓
SECTION 7: VOICE CLONE             (2-min reference)
  ↓
SECTION 8: COMPETITIVE INTEL       (Who you watch)
  ↓
SECTION 9: SERIES SETUP            (Recurring content)
  ↓
SECTION 10: PLATFORM + SCHEDULE    (Where + when)
  ↓
WIZARD COMPLETE → Content Factory goes live
```

**Total time:** 60-90 minutes (can be split across sessions)
**Output:** Complete `client_dna.yaml` + voice clone + brand assets + platform OAuth

---

## SECTION 1: THE FOUNDATION (15 min)

**Goal:** Nail WHO the client talks to, WHY their content exists, and WHO they're fighting against.

### Q1.1 — Who do you serve?

**Operator asks:**
> "Tell me about your ideal client. Not everyone. The ONE person you want more of. What do they do? What do they struggle with? What do they dream about?"

**Follow-ups:**
- What's their income range?
- What's their biggest frustration right now?
- What have they tried that didn't work?
- What do they WANT that they can't articulate yet?

**Example for Anthony:**
> "I serve independent creators and service business owners making $5K-$50K/month who are stuck trading time for money. They see AI everywhere but don't know how to USE it to escape the grind. They've tried ChatGPT twice, watched 50 YouTube tutorials, bought a course that was outdated in 3 months. What they want is freedom — but they don't know what to build."

**Output:**
```yaml
icp:
  who: _______________
  income_range: _______________
  top_frustration: _______________
  failed_attempts: _______________
  secret_desire: _______________
```

---

### Q1.2 — What transformation do you offer?

**Operator asks:**
> "Finish this sentence: 'I help [WHO] go from [BEFORE STATE] to [AFTER STATE] by [YOUR METHOD].' Don't overthink it. Just say it."

**Follow-ups:**
- What's the BEFORE state in one word? (Stuck? Overwhelmed? Invisible?)
- What's the AFTER state in one word? (Free? Visible? Profitable?)
- What's the ONE thing that makes YOUR method different from everyone else's?

**Example for Anthony:**
> "I help creators and service businesses go from hired gun to business owner by building AI operators that do the work for them."

**Output:**
```yaml
transformation:
  one_liner: "I help [WHO] go from [BEFORE] to [AFTER] by [METHOD]."
  before_state: _______________
  after_state: _______________
  method_differentiator: _______________
```

---

### Q1.3 — Who's the enemy?

**Operator asks:**
> "Every strong brand has an enemy. Not a person — a BELIEF or SYSTEM they're fighting against. What do you stand against? What makes you angry about the industry? What's the 'old way' you're replacing?"

**Follow-ups:**
- What's the common advice in your space that's actually bullshit?
- What are people WRONGLY told they need to do?
- What's the industry pretending is the path to success but isn't?

**Example for Anthony:**
> "The enemy is guru culture + AI hype machine + the belief that you need to be technical to leverage AI. The 'just use ChatGPT' crowd. The people selling $997 courses on AI who've never built anything real. The old way: work 60 hours, post 10 tips a day, grind your way to freedom. That's broken. The new way: build the system once, let operators run it, create at your pace."

**Output:**
```yaml
enemy:
  stands_against: _______________
  old_way: _______________
  industry_lies: _______________
  rage_points:
    - _______________
    - _______________
    - _______________
```

---

### Q1.4 — What do you stand FOR?

**Operator asks:**
> "Now flip it. If the enemy is what you're against — what are you FOR? What's the belief system, the philosophy, the world you're trying to create?"

**Example for Anthony:**
> "I'm for Vibe Creating — vibing with AI at the highest level, no spoon, no gatekeeping. I'm for creators becoming business owners. I'm for principles over hacks. I'm for Think it → Vibe it → Have it. Creator Create."

**Output:**
```yaml
manifesto:
  stands_for: _______________
  core_philosophy: _______________
  signature_belief: _______________
```

---

## SECTION 2: BRAND VOICE (15 min)

**Goal:** Capture HOW the client sounds so every piece of content sounds like them, not generic AI.

### Q2.1 — Describe your voice in 3 words

**Operator asks:**
> "If your best friend described how you talk, what 3 words would they use?"

**Examples:** Direct + raw + energetic. Warm + analytical + playful. Sharp + contrarian + funny.

**Output:**
```yaml
voice_descriptors:
  - _______________
  - _______________
  - _______________
```

---

### Q2.2 — Words you USE (vocabulary)

**Operator asks:**
> "Give me 20 words or phrases you naturally use that feel like YOU. Don't filter — just dump them. Slang, signature phrases, callback words, whatever comes out of your mouth."

**Example for Anthony:**
> "Keep it 100, vibe, creator, create, champ, let's go, Dr. Frankenstein, stitch, 100%, facts, big facts, no spoon, that's fire, gang, ship it, build in public, make sense?, you feel me?"

**Output:**
```yaml
vocabulary:
  signature_phrases: [...]
  slang: [...]
  callback_words: [...]
```

---

### Q2.3 — Words you NEVER use

**Operator asks:**
> "What words make you cringe? What would you NEVER say because it sounds corporate, fake, or not you?"

**Example for Anthony:**
> "Leverage synergy, circle back, at the end of the day, utilize (just say use), game-changer, disruptor, hustler, grind mindset, wantrepreneur, thought leader, crushing it, killing it."

**Output:**
```yaml
never_use:
  banned_words: [...]
  banned_phrases: [...]
  why: "Sound corporate / fake / trendy-for-trendy's-sake"
```

---

### Q2.4 — Energy + pacing

**Operator asks:**
> "Are you calm or hyped? Do you talk fast or slow? Long sentences or short punchy ones? What's your vibe when you're in the flow?"

**Output:**
```yaml
voice_style:
  energy: calm | conversational | energetic | hyped
  pacing: fast | medium | slow | variable
  sentence_style: short_punchy | flowing | mixed
  tone: direct | warm | contrarian | playful | mix
```

---

### Q2.5 — Your signature sign-off

**Operator asks:**
> "How do you close? Do you have a tagline, a sign-off, a phrase that ends everything?"

**Example for Anthony:**
> "Think it → Vibe it → Have it. Creator Create."

**Output:**
```yaml
signature:
  closing: _______________
  intro_tag: _______________ (optional)
```

---

## SECTION 3: STORY BANK (20-30 min)

**Goal:** Extract 20+ stories across the client's career. These become the authenticity fuel for every piece of content.

### Q3.1 — Origin story

**Operator asks:**
> "Take me back to the moment this all started. What were you doing before? What was the turning point that got you here?"

**Follow-ups:**
- What year was it?
- What were you struggling with?
- What made you decide to change?
- What did you do next?

---

### Q3.2 — 3 biggest failures (Adversity bucket fuel)

**Operator asks:**
> "Tell me about 3 times you FAILED. Not little stumbles — the real ones. Where you lost money, lost clients, lost confidence. What happened? What did you learn?"

**Why we need these:** Failure stories build trust faster than any success story. Vulnerability = connection.

---

### Q3.3 — 3 biggest wins (Proof bucket fuel)

**Operator asks:**
> "Tell me about 3 moments you WON. Not participation trophies — the real ones. Where it clicked, where you got the result, where you knew you had it."

**Why we need these:** Wins are the proof. Numbers, dates, specifics. "I made money" = weak. "I turned $47 into $12K in 6 weeks" = strong.

---

### Q3.4 — 3 turning points (Mindset bucket fuel)

**Operator asks:**
> "Tell me about 3 moments that CHANGED how you think. A realization, a lesson, a 'oh shit' moment. The before and after of your own mind."

---

### Q3.5 — Behind-the-scenes moments (BTS bucket fuel)

**Operator asks:**
> "What does your actual day look like? What do you build? What do you struggle with? What would surprise people who only see your highlight reel?"

---

### Q3.6 — Client wins (Community bucket fuel)

**Operator asks:**
> "Tell me about clients you've transformed. Real people, real results. Who were they before? Who are they now?"

**Output for Section 3:**
```yaml
stories:
  origin:
    - title: _______________
      year: _______________
      summary: _______________
      lesson: _______________
      bucket: Origin
      funnel: LIKE/TRUST
      
  failures:
    - [3 stories with same structure]
      
  wins:
    - [3 stories with same structure]
      
  turning_points:
    - [3 stories with same structure]
      
  bts_moments:
    - [3-5 stories]
      
  client_wins:
    - [3-5 stories]
      
# Minimum 20 stories total
```

---

## SECTION 4: CONTENT PILLARS (10 min)

**Goal:** Lock the 3-5 topics the client ALWAYS talks about.

### Q4.1 — What are you known for?

**Operator asks:**
> "If I asked 10 people who know you 'what does [client name] talk about?' — what would they say? What are you the go-to person for?"

---

### Q4.2 — What could you talk about forever?

**Operator asks:**
> "What's the topic where you never run out of things to say? Where you could talk for 4 hours and still have more?"

---

### Q4.3 — What do people ASK you about?

**Operator asks:**
> "When people DM you, email you, or stop you in real life — what do they ask about? That's a pillar."

---

### Q4.4 — The Pillar Lock

**Operator summarizes:**
> "Based on what you've told me, here are your 5 pillars. Let's lock 3-5 of them. We can add more later, but we start narrow so we're KNOWN for something."

**Example for Anthony:**
1. **Vibe Creating** — The philosophy. AI + creativity. No spoon.
2. **Building in Public** — Cocreatiq behind the scenes. Real numbers. Real failures.
3. **The Marketing Machine** — Content at scale. AI operators. DDO.
4. **Creator to Business Owner** — The shift. Pricing. Leverage. Freedom.
5. **The Creative Process** — 20 years of design/photo/video distilled.

**Output:**
```yaml
pillars:
  - name: _______________
    description: _______________
    why_yours: _______________  # What makes this YOUR pillar
    bucket_affinity: [...]      # Which buckets fit this pillar
```

---

## SECTION 5: YOUR OFFER (10 min)

**Goal:** Capture what the client sells so BOFU content and CTAs work.

### Q5.1 — What do you sell?

**Operator asks:**
> "Walk me through everything you sell. Products, services, memberships, courses — all of it. Price and what they get."

---

### Q5.2 — Who is each product for?

**Operator asks:**
> "For each product, who's the perfect buyer? What level are they at? What transformation do they get?"

---

### Q5.3 — Keywords + lead magnets

**Operator asks:**
> "For each product, what's the keyword we use on social? What's the lead magnet — the free thing we give them to start the conversation?"

**Example for Anthony:**
- Product: Cocreatiq | Keyword: OPERATOR | Lead magnet: Free AI readiness audit
- Product: Vibe Creator Community | Keyword: CREATE | Lead magnet: Creator Create starter kit

**Output:**
```yaml
offers:
  - name: _______________
    price: _______________
    who_for: _______________
    transformation: _______________
    keyword: _______________
    lead_magnet: _______________
    funnel_stage: BOFU
```

---

## SECTION 6: VISUAL IDENTITY (10 min + upload time)

**Goal:** Capture brand DNA so every visual looks like it was designed by the client.

### Q6.1 — Brand assets upload

**Operator requests:**
- Logo (SVG or PNG with alpha)
- Color palette (hex codes or brand kit)
- Fonts (files or Google Fonts names)
- Photos (minimum 5 high-res photos of the client)
- Any existing video templates (AE, Premiere, Figma)

### Q6.2 — Visual vibe per bucket

**Operator asks:**
> "For each of the 10 content buckets, what's the visual FEEL? Dark and intense for hot takes? Clean and bright for education? Raw phone footage for behind-the-scenes?"

**Output:**
```yaml
visual_identity:
  brand_assets:
    logo: path/to/logo.svg
    colors:
      primary: "#______"
      accent: "#______"
      background: "#______"
      text: "#______"
    fonts:
      headline: _______________
      body: _______________
      accent: _______________
    photos: [paths]
    
  visual_per_bucket:
    contrarian:
      bg: "Dark + high contrast"
      text: "Bold red accent"
      feel: "Confrontational"
    education:
      bg: "Clean + bright"
      text: "White on dark"
      feel: "Clear, structured"
    # ... for all 10 buckets
```

---

## SECTION 7: VOICE CLONE (5 min)

**Goal:** Capture 2 minutes of clean voice audio for cloning.

### Q7.1 — Voice reference

**Operator guides:**
> "We need 2 minutes of you talking naturally. Quiet room, mic close to mouth. Talk about anything — your day, your business, a story. Keep it conversational. Don't read a script."

**Record in-app OR upload existing high-quality audio.**

**Output:**
```yaml
voice_clone:
  reference_audio: path/to/reference.wav
  status: pending | cloned | deployed
  model: qwen3_tts
  similarity_score: _______________  # Set after training
```

---

## SECTION 8: COMPETITIVE INTEL (10 min)

**Goal:** Identify who we watch for outlier research.

### Q8.1 — Who's winning in your space?

**Operator asks:**
> "Who are 5-10 creators or businesses in your space that you watch? Not just the biggest — the ones who consistently produce content that HITS."

---

### Q8.2 — Who are you NOT like?

**Operator asks:**
> "Who in your space do you specifically NOT want to be like? The people whose content feels fake, off, or wrong to you."

**Output:**
```yaml
competitive_intel:
  watch_list:
    - handle: _______________
      platform: _______________
      what_they_do_well: _______________
    # 5-10 creators
      
  anti_list:
    - handle: _______________
      why_not: _______________
    # 3-5 creators
```

---

## SECTION 9: SERIES SETUP (10 min)

**Goal:** Lock any recurring content series the client wants to run.

### Q9.1 — Do you have any series ideas?

**Operator explains:**
> "A series is recurring content people come back for. Three types: Saga (ongoing, no end), Series (fixed episodes), Recurring (weekly ritual like Framework Friday)."

**Operator asks:**
> "Do you have any series ideas? We start with 1-3 and add more once the rhythm is locked."

**Example for Anthony:**
1. **Saga — "Me & Champ — Road to Generational Wealth"** (2-3x/week)
2. **Recurring — "That's True But That's Not The Truth"** (2-3x/week)
3. More TBD

**Output:**
```yaml
series:
  - name: _______________
    type: Saga | Series | Recurring
    frequency: _______________
    drop_day: _______________
    face: _______________
    format: _______________
    episode_template: _______________
```

---

## SECTION 10: PLATFORM + SCHEDULE (10 min)

**Goal:** Connect accounts + lock posting cadence.

### Q10.1 — Which platforms?

**Operator asks:**
> "Where does your audience actually spend time? Let's connect those accounts first. We recommend starting with 4 platforms — Twitter, Instagram, TikTok, LinkedIn. YouTube is Phase 2."

### Q10.2 — OAuth connection

**Operator walks client through Nango OAuth for each platform.**

### Q10.3 — Posting cadence

**Operator recommends:**
> "Default is 3x/day per platform. Morning TOFU, Afternoon TOFU, Evening MOFU. BOFU 1-2x/week. This is configurable but it's what's proven."

### Q10.4 — Approval mode

**Operator asks:**
> "Two modes: Self Mode — operator creates content, you review and approve before it posts. Auto Mode — operator creates and posts, no human touch. Which do you want to start with?"

**Output:**
```yaml
platforms:
  - name: twitter
    oauth_status: connected
    posts_per_day: 3
    enabled: true
  - name: instagram
    # ...
    
schedule:
  timezone: _______________
  slots:
    - time: "8-10am"
      funnel: TOFU
    - time: "12-2pm"
      funnel: TOFU
    - time: "5-7pm"
      funnel: MOFU
      
approval_mode: self | auto
```

---

## WIZARD COMPLETE — What The System Has Now

After the wizard, the system has `client_dna.yaml`:

```yaml
client_id: _______________
client_name: _______________
wizard_completed: 2026-04-18

# Section 1
icp: {...}
transformation: {...}
enemy: {...}
manifesto: {...}

# Section 2
voice_descriptors: [...]
vocabulary: {...}
never_use: {...}
voice_style: {...}
signature: {...}

# Section 3
stories: {...}  # 20+ stories across 6 categories

# Section 4
pillars: [...]  # 3-5 locked

# Section 5
offers: [...]

# Section 6
visual_identity: {...}

# Section 7
voice_clone: {...}

# Section 8
competitive_intel: {...}

# Section 9
series: [...]

# Section 10
platforms: [...]
schedule: {...}
approval_mode: ___
```

**From this one file, the Content Factory can:**
- Generate hooks that sound like the client
- Write scripts using their stories
- Pick topics matching their pillars
- Attack their enemy with Contrarian content
- Create CTAs with the right keywords
- Produce visuals matching their brand
- Clone their voice for audio
- Research their specific competitors
- Run their series on schedule
- Post on their platforms at their optimal times

**Everything downstream runs from this one onboarding session.**

---

## Operator Logic (How Cocreatiq Runs This)

The Onboarding Operator runs this wizard:

```
1. GREET
   "Hey [name], I'm [operator]. I'm going to help you build your content DNA.
    This takes about 60-90 minutes. We can do it in one session or break it up.
    By the end, your Marketing Machine knows YOU well enough to post as you.
    Ready?"

2. CONVERSATIONAL EXTRACTION
   Operator asks questions from this wizard — voice or text.
   Never feels like a form. Feels like a strategy conversation.
   Operator takes notes, asks follow-ups, clarifies.
   
3. DISTILLATION
   After each section, operator summarizes:
   "Here's how I heard you on [SECTION]: [distilled version]. Does this capture it?"
   Client confirms or corrects.
   
4. STRUCTURED OUTPUT
   Operator writes client_dna.yaml automatically from the conversation.
   Uses LLM to structure the natural speech into the YAML format.
   
5. APPROVAL
   Before going live, operator shows client the full client_dna.yaml:
   "Here's your Content DNA. Review it. Edit anything. Once you approve, the Machine starts running."
   
6. ACTIVATION
   Client approves → Content Factory activates →
   First 48hrs: system generates 10-20 pieces of test content for approval →
   Client approves batch → system goes live →
   Content starts posting on schedule.
```

---

## Next Step: Anthony Runs The Wizard As Client 0

Anthony becomes the first person to walk through this. He'll find:
- Questions that don't make sense
- Missing sections
- Too-long sections
- Examples that don't land
- Outputs that aren't useful

Every friction point gets fixed. By the time Client 1 runs it, the wizard is airtight.

When ready, we do the wizard in a live session:
1. Anthony answers every question
2. The answers become Anthony's `anthony_dna.yaml`
3. This file powers Face 0 (Anthony's clone) in the Content Factory
4. The Marketing Machine posts as Anthony starting day 1

**Plus the wizard itself becomes a Cocreatiq product asset:**
- Part of the $3K setup fee deliverable
- Unique competitive moat (no other AI marketing tool does this depth)
- Generates a reusable document for every client
- Lets clients update their DNA anytime their business evolves
