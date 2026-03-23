# 0018 — Cocreatiq OS Launch Checklist (Customer Zero: Anthony)
**Date:** 2026-03-21
**Goal:** Get Anthony's business running on Cocreatiq OS — from zero to live

---

## Phase 1: Foundation (Build the OS for one user)

### 1.1 Operator Type Configs
- [ ] Sales Operator YAML + superpowers (Hormozi CLOSER, AAA, objections)
- [ ] Lead Gen Operator YAML + superpowers (Priestley assessment, Gian ads)
- [ ] Marketing/Creator Operator YAML + superpowers (Lamar quality, Gary Vee volume, autoresearch loop)
- [ ] Onboarding Operator YAML + superpowers (Platten 3 C's)
- [ ] Retention Operator YAML + superpowers (Hormozi retention, escalation, ascension)
- [ ] Operations Operator YAML + superpowers (Hormozi scaling, diagnostics)

### 1.2 Business Matrix → Knowledge Blocks
- [ ] Convert each matrix .md file into loadable knowledge blocks
- [ ] Wire knowledge block loading into operator spawn (type → loads relevant blocks)
- [ ] Test: spawn Sales operator → verify CLOSER framework is in context
- [ ] Test: spawn Marketing operator → verify Lamar + Gary Vee is in context

### 1.3 Multi-User Support
- [ ] Replace hardcoded "anthony" with user account system
- [ ] Per-user memory scope in Supabase
- [ ] Per-user operator instances in Registry
- [ ] User auth (Google/Microsoft OAuth)

---

## Phase 2: Anthony's Business Setup

### 2.1 Business Profile
- [ ] Define Anthony's business: what he sells, who he serves, his ICP
- [ ] Define Anthony's SOPs for each business function
- [ ] Define Anthony's brand voice / communication style
- [ ] Define Anthony's tech stack (Figma, Vercel, Railway, Supabase, Claude, LiveKit, ElevenLabs)

### 2.2 Operator Personas (Anthony's Team)
- [ ] Name each operator (Champ stays as personal operator)
- [ ] Set voice for each operator
- [ ] Set boundaries for each operator (what needs approval, what's auto)
- [ ] Set which operators can delegate to which (A2A routing)

### 2.3 Connect Business Stack
- [ ] Gmail / email integration
- [ ] Calendar integration
- [ ] Social media API connections (YouTube, Instagram, LinkedIn, Twitter/X, TikTok)
- [ ] Stripe / payment integration
- [ ] CRM setup (or Supabase as CRM)
- [ ] GitHub / dev tools (for Creator/Builder operator)

---

## Phase 3: Content Engine (3 Influencer Strategy)

### 3.1 Clone Setup
- [ ] Collect photos for face cloning (5+ photos per influencer)
- [ ] Collect 30-sec voice samples for voice cloning (ElevenLabs)
- [ ] Define brand voice / content style per influencer
- [ ] Define niche per influencer (tech/AI, business/entrepreneur, creative/agency)
- [ ] Define target platforms per influencer

### 3.2 Autoresearch Loop
- [ ] YouTube Reporting API integration (pull analytics)
- [ ] Instagram API integration (pull analytics)
- [ ] Build binary eval criteria from Business Matrix (Lamar + Gary Vee frameworks)
- [ ] Wire eval scoring into Marketing Operator
- [ ] Wire feedback memory (Letta knowledge block — self-improving rules)
- [ ] Wire Self Mode for fast iteration (generate 3 → score → improve → repeat)
- [ ] Test: generate 10 thumbnails, score against criteria, verify improvement

### 3.3 Content Pipeline
- [ ] Pillar content creation workflow (1 piece → 64+ micro pieces)
- [ ] Platform-specific formatting (YouTube, IG Reels, TikTok, LinkedIn, Twitter)
- [ ] Scheduling / auto-posting via platform APIs
- [ ] Content funnel tracking (TOF 50% / MOF 30% / BOF 20%)
- [ ] All content funnels back to Cocreatiq OS waitlist/landing page

---

## Phase 4: Frontend (What Users See)

### 4.1 Onboarding Wizard
- [ ] Screen 1: Welcome to Cocreatiq OS (dark, particle wave, "Get Started")
- [ ] Screen 2: Sign In (Google/Microsoft/Email — mobile + desktop)
- [ ] Screen 3: Staff Your First Operator (role selection cards)
- [ ] Screen 4: Connect Your Business Stack (auto-detect + OAuth connectors)
- [ ] Screen 5: Meet Your Operator (voice greeting, name input, call starts)

### 4.2 Core App Screens
- [ ] Call Screen (voice-first interface — already exists, needs polish)
- [ ] Dashboard / Home (active operators, recent activity, costs)
- [ ] Operator Profile (configure persona, skills, boundaries, SOPs)
- [ ] Admin Panel (manage operators, permissions, connectors, billing)

### 4.3 Landing Page / Marketing Site
- [ ] Cocreatiq OS landing page (Vercel)
- [ ] "Changing the way businesses interact with technology"
- [ ] Waitlist / sign-up flow
- [ ] Demo video showing operator in action
- [ ] Pricing page (finalize later)

---

## Phase 5: Deploy

### 5.1 Infrastructure
- [ ] Brain API → Railway
- [ ] LiteLLM → Railway
- [ ] LiveKit agent → Railway (or LiveKit Cloud)
- [ ] Frontend → Vercel
- [ ] Supabase → Cloud (already connected)
- [ ] Letta → Docker on Railway (or skip for V1, graceful degradation)
- [ ] Domain: cocreatiq.com (or whatever the domain is)
- [ ] SSL / HTTPS
- [ ] Environment variables / secrets management

### 5.2 Monitoring
- [ ] Error logging (Supabase or Sentry)
- [ ] Cost tracking per operator per user
- [ ] Uptime monitoring
- [ ] API health checks

---

## Phase 6: Test (Anthony + Partner)

### 6.1 Self-Test Checklist
- [ ] Sign up flow works end-to-end
- [ ] Can staff each of the 6 operator types
- [ ] Can talk to operator via voice call
- [ ] Operator knows Business Matrix frameworks (ask it to run CLOSER, it can)
- [ ] Operator can browse the web (nodriver)
- [ ] Operator can take screenshots and analyze (active vision)
- [ ] Operator can research (YouTube transcripts, web content, PDFs)
- [ ] Operator can estimate cost before doing expensive tasks
- [ ] Operator can run Self Mode (autonomous multi-step tasks)
- [ ] Operator remembers across sessions (Supabase memory)
- [ ] A2A works: one operator can delegate to another
- [ ] Loop selection works: "open Spotify" = Action loop, "build me a scraper" = Autonomous loop

### 6.2 Content Engine Test
- [ ] Marketing operator generates content from a pillar piece
- [ ] Content follows Lamar retention structure (Hook → Lead → Meat → Payoff)
- [ ] Content gets repurposed into multiple formats (Gary Vee model)
- [ ] Autoresearch loop pulls analytics and scores content
- [ ] System improves over time (eval scores go up)

### 6.3 Business Function Tests
- [ ] Lead Gen operator can capture and score leads
- [ ] Sales operator can run CLOSER framework on a practice call
- [ ] Onboarding operator walks through the 3 C's process
- [ ] Retention operator handles a mock escalation
- [ ] Operations operator runs a business diagnostic

### 6.4 Partner Test
- [ ] Partner signs up as separate user
- [ ] Partner staffs their own operators
- [ ] Partner's memory is separate from Anthony's
- [ ] Partner's operators work independently

---

## Phase 7: Fix & Ship

- [ ] Fix everything that broke in Phase 6
- [ ] Polish the worst UX friction points (not everything — just the worst)
- [ ] Record demo video of the system working
- [ ] Launch 3 influencer channels
- [ ] Open waitlist / beta access
- [ ] Ship

---

## Priority Order (What to Build First)

| Priority | What | Why |
|---|---|---|
| 1 | Operator Type Configs (Phase 1.1) | Can't test operators without them |
| 2 | Knowledge Block Loading (Phase 1.2) | Operators need superpowers to be useful |
| 3 | Anthony's Business Profile (Phase 2.1) | Need real data to test with |
| 4 | Deploy to Railway + Vercel (Phase 5.1) | Need it live to test real usage |
| 5 | Frontend: Onboarding + Call Screen (Phase 4.1-4.2) | Users need to be able to get in |
| 6 | Self-Test (Phase 6.1) | Find what breaks |
| 7 | Content Engine + Clones (Phase 3) | Marketing starts generating traffic |
| 8 | Fix & Ship (Phase 7) | Launch |

---

## What We're NOT Building Before Launch

- FlashHead custom avatar (use existing or no avatar)
- Full MCP Bridge (add connectors post-launch)
- Email/SMS/webhook channels (voice-first, add later)
- Full observability dashboard (log to Supabase, dashboard later)
- Myron Golden offers framework (matrix is strong enough)
- Perfect UI polish (functional > pretty)
- Persistent state machine (nice to have, not blocking)

---

## The Line

**8 priorities. Ship when Phase 6 passes. Everything else comes after.**