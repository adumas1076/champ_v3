# ANTONIO REPOS BLUEPRINT
## The Complete Parts Shelf — App Clone Reference for Claude Code

> Every repo Antonio built is a proven, production-grade open-source app.
> These are your primary Frankenstein parts. Read this before building ANY clone.
> Each repo has a chapter-by-chapter branch structure — you can checkout any
> exact point in the build and use it as your starting point.

---

## HOW TO USE THIS DOCUMENT

1. Identify which Antonio repo covers the app you're cloning
2. Study the full stack, folder structure, and feature list
3. Clone the repo and checkout the relevant branch
4. Frankenstein what you need — strip what you don't
5. Build only the 20% gap that doesn't exist in the repo

**Workshop access:** Anthony has full access to all video tutorials at
`https://www.codewithantonio.com/workshops/`

---

## REPO 1: RESONANCE — ElevenLabs Clone
**Repo:** `https://github.com/code-with-antonio/resonance`
**What it is:** Open-source ElevenLabs alternative — AI text-to-speech + voice cloning
**Clone target:** Voice/audio layer for cocreatiq's HeyGen clone + GHL voice module

### Stack
| Layer | Technology |
|-------|-----------|
| Framework | Next.js 16, React 19, TypeScript |
| Auth | Clerk (Organizations — multi-tenant) |
| Database | Prisma + Postgres |
| API layer | tRPC |
| Storage | Cloudflare R2 |
| GPU/AI | Modal (serverless NVIDIA A10G) |
| TTS model | Chatterbox TTS (Resemble AI, open source, zero-shot) |
| Audio player | WaveSurfer.js |
| Billing | Polar (usage-based metered billing) |
| UI | shadcn/ui |

### Features Built
- Text-to-speech: adjustable creativity, variety, expression, flow params
- Zero-shot voice cloning: 10s sample minimum, no fine-tuning
- 20 built-in voices: 12 categories, 5 locales
- Waveform audio player: seek, play/pause, download
- Multi-tenant: Clerk Organizations with full data isolation
- Usage-based billing: pay-per-character + pay-per-voice-creation via Polar meters
- Generation history: browse/replay past generations with metadata
- Fully responsive: mobile-first, bottom drawers, compact controls

### Chapter Branch Map
| Branch | Chapter |
|--------|---------|
| `main` | Final project — all chapters combined |
| `02-dashboard` | Dashboard layout and navigation |
| `03-text-to-speech-ui` | Text-to-speech UI |
| `04-backend-infrastructure` | Backend: tRPC + R2 + Prisma |
| `05-voice-selection` | Voice selection and library |
| `06-tts-generation-audio-player` | TTS generation + audio player |
| `07-tts-history-polish` | TTS history and polish |
| `bonus-sentry-error-monitoring` | Sentry error monitoring |
| `08-voice-management` | Voice management and cloning |
| `09-billing` | Billing and usage metering |

### Folder Structure
```
src/
├── app/
│   ├── (dashboard)/          # Protected routes: home, TTS, voices
│   ├── api/                  # Audio proxy routes + tRPC handler
│   ├── sign-in/              # Clerk auth pages
│   └── sign-up/
├── components/               # Shared UI (shadcn/ui + custom)
├── features/
│   ├── dashboard/            # Home page, quick actions
│   ├── text-to-speech/       # TTS form, audio player, settings, history
│   ├── voices/               # Voice library, creation, recording
│   └── billing/              # Usage display, checkout
├── hooks/                    # App-wide hooks
├── lib/                      # Core: db, r2, polar, env, chatterbox client
├── trpc/                     # tRPC routers, client, server helpers
├── generated/                # Prisma client
└── types/                    # Generated API types
```

### Key Setup Steps
```bash
git clone https://github.com/code-with-antonio/resonance.git
cd resonance && npm install
cp .env.example .env

# Polar billing setup — 2 meters:
# 1. voice_creation — Count aggregation
# 2. tts_generation — Sum over characters

npx prisma migrate deploy
modal deploy chatterbox_tts.py   # Deploy GPU TTS to Modal (NVIDIA A10G)
npm run sync-api                 # Generate type-safe Chatterbox client
npx prisma db seed               # Seeds 20 built-in voices
npm run dev
```

### Self-Host Requirements
- PostgreSQL (Prisma Postgres recommended)
- Cloudflare R2 (audio storage)
- Modal (GPU inference — pay-per-second)
- Clerk (auth + multi-tenancy)
- Polar (metered billing)

### Clues Left Behind
- `chatterbox_tts.py` — GPU TTS engine, reads directly from R2 bucket
- Modal secrets needed: `cloudflare-r2`, `chatterbox-api-key`, `hf-token`
- `npm run sync-api` regenerates Chatterbox API types from OpenAPI spec
- Polar meter names must match `POLAR_METER_*` env variables exactly
- System voice WAV files included in repo — from Modal's voice sample pack
- Cold start warning: first request after inactivity takes longer (Modal provisioning)

---

## REPO 2: POLARIS — Cursor/Replit Clone
**Repo:** `https://github.com/code-with-antonio/polaris`
**Branches:** `https://github.com/code-with-antonio/polaris/branches/all`
**What it is:** Browser-based cloud IDE inspired by Cursor AI — real-time collaborative code editing with AI agents
**Clone target:** Internal dev tool for cocreatiq — Polaris = Champ's code editor interface

### Stack
| Layer | Technology |
|-------|-----------|
| Framework | Next.js 16, React 19, TypeScript, Tailwind CSS v4 |
| Code editor | CodeMirror 6 + custom extensions + One Dark theme |
| Database | Convex (real-time DB) |
| Background jobs | Inngest |
| AI | Claude Sonnet 4 (preferred) OR Gemini 2.0 Flash (free tier) |
| Auth | Clerk (with GitHub OAuth) |
| Execution | WebContainer API + xterm.js |
| Web scraping | Firecrawl (docs scraping for AI context) |
| Error tracking | Sentry + LLM monitoring |
| UI | shadcn/ui + Radix UI |

### Features Built — Part 1 (Chapters 1–12)
**Editor:**
- Syntax highlighting: JS, TS, CSS, HTML, JSON, Markdown, Python
- Line numbers, code folding, minimap overview
- Bracket matching + indentation guides
- Multi-cursor editing
- Auto-save with debouncing
- Real-time Convex-powered instant updates + optimistic UI

**AI Features:**
- Real-time code suggestions with ghost text
- Quick edit: Cmd+K (select code + natural language instruction)
- Selection tooltip for quick actions
- Conversation sidebar with message history

**File Management:**
- File explorer with folder hierarchy
- Create, rename, delete files/folders
- VSCode-style file icons
- Tab-based file navigation

### Features Built — Part 2 (Chapters 13–16) ✅ COMPLETE
- AI Agent + tools (file management, AgentKit)
- WebContainer, terminal + live preview
- GitHub import/export
- Billing + final polish

### Chapter Branch Map — ALL 16 CHAPTERS
| Branch | Chapter |
|--------|---------|
| `main` | Final project — all chapters combined |
| `02-authentication` | Clerk auth + protected routes |
| `03-database-setup` | Convex database + real-time setup |
| `04-background-jobs` | Inngest — background jobs + non-blocking UI |
| `04-firecrawl-ai` | Firecrawl — teaching AI with live docs |
| `06-error-tracking` | Sentry — error tracking + LLM monitoring |
| `07-projects` | Projects dashboard + landing page |
| `08-ide-layout` | Project IDE layout + resizable panes |
| `09-file-explorer` | File explorer — full implementation |
| `10-code-editor-state` | Code editor + state management |
| `11-ai-features` | AI suggestions + quick edit |
| `12-conversation-system` | Conversation system |
| `13-ai-agent-tools` | AI agent + tools (AgentKit, file management) |
| `14-webcontainers-terminal-preview` | WebContainer + terminal + preview |
| `15-github-import-export` | GitHub import/export |
| `16-billing-final-polish` | Billing + final polish |

### Folder Structure
```
src/
├── app/
│   ├── api/
│   │   ├── messages/         # Conversation API
│   │   ├── suggestion/       # AI code suggestions
│   │   └── quick-edit/       # Cmd+K editing
│   └── projects/             # Project pages
├── components/
│   ├── ui/                   # shadcn/ui components
│   └── ai-elements/          # AI conversation components
├── features/
│   ├── auth/                 # Authentication
│   ├── conversations/        # AI chat system
│   ├── editor/               # CodeMirror setup
│   │   └── extensions/       # Custom extensions
│   ├── preview/              # WebContainer (Part 2)
│   └── projects/             # Project management
├── inngest/                  # Inngest client
└── lib/                      # Utilities
convex/
├── schema.ts                 # Database schema
├── projects.ts               # Project queries/mutations
├── files.ts                  # File operations
├── conversations.ts          # Conversation operations
└── system.ts                 # Internal API for Inngest
```

### Key Setup Steps
```bash
git clone https://github.com/code-with-antonio/polaris.git
cd polaris && npm install
cp .env.example .env.local
# Keys needed: Clerk, Convex, Anthropic OR Google AI, Firecrawl, Sentry

npx convex dev          # Start Convex dev server (terminal 1)
npm run dev             # Start Next.js (terminal 2)
npx inngest-cli@latest dev  # Start Inngest (terminal 3)
```

### ENV Variables
```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
CLERK_SECRET_KEY=
NEXT_PUBLIC_CONVEX_URL=
CONVEX_DEPLOYMENT=
POLARIS_CONVEX_INTERNAL_KEY=   # Random string
ANTHROPIC_API_KEY=              # Claude Sonnet 4 — preferred
GOOGLE_GENERATIVE_AI_API_KEY=   # Gemini 2.0 Flash — free alternative
FIRECRAWL_API_KEY=              # Optional
SENTRY_DSN=                     # Optional
```

### Clues Left Behind
- `POLARIS_CONVEX_INTERNAL_KEY` — generate any random string for Convex internal auth
- Three terminals needed: Convex + Next.js + Inngest all run simultaneously
- Firecrawl is the "teach the AI" feature — scrapes docs for context
- AI provider is interchangeable: Claude Sonnet 4 OR Gemini 2.0 Flash
- Convex handles real-time without extra websocket setup
- Part 2 branches (13–16) are fully committed and checkable even though "coming soon" in README

---

## REPO 3: NODEBASE — n8n/Zapier Clone
**Repo:** `https://github.com/code-with-antonio/nodebase`
**What it is:** Visual drag-drop workflow automation — n8n/Zapier alternative
**Clone target:** Core workflow automation engine for cocreatiq's GHL clone

### Stack (Inferred from branch names + standard Antonio pattern)
| Layer | Technology |
|-------|-----------|
| Framework | Next.js (App Router) |
| Auth | Clerk or NextAuth (branch 04-authentication) |
| Database | Postgres via Prisma or Drizzle (branch 02-database) |
| API layer | tRPC (branch 03-trpc-setup) |
| Background jobs | Inngest (branch 06-background-jobs) |
| AI providers | Multiple — branch 07-ai-providers |
| Payments | Stripe (branch 10-payments) |
| Error tracking | Sentry (branch 08-error-tracking) |
| UI | shadcn/ui + Tailwind |

### Features Built — 29 Chapters
**Foundation (Chapters 1–10):**
- Database setup
- tRPC setup
- Authentication
- Background jobs (Inngest)
- Theme + styling
- Background jobs
- AI provider integration
- Error tracking (Sentry)
- Sidebar layout
- Payments (Stripe)

**Canvas/Editor (Chapters 11–21):**
- Workflows CRUD
- Workflows pagination
- Workflows UI
- Workflow page
- Visual node editor
- Node selector
- Editor state management
- Node execution engine
- Node variables
- Node templating
- Node real-time updates

**Integrations (Chapters 22–29):**
- Google Form trigger
- Stripe trigger
- AI nodes
- Credentials management
- Discord + Slack nodes
- Execution history
- Credential encryption
- GitHub + Google OAuth

### Complete Chapter Branch Map — ALL 29 CHAPTERS
| Branch | Chapter |
|--------|---------|
| `main` | Final project |
| `02-database` | Database setup |
| `03-trpc-setup` | tRPC setup |
| `04-authentication` | Authentication |
| `05-theme-styling` | Theme + styling |
| `06-background-jobs` | Inngest background jobs |
| `07-ai-providers` | AI provider integration |
| `08-error-tracking` | Sentry error tracking |
| `09-sidebar-layout` | Sidebar layout |
| `10-payments` | Payments (Stripe) |
| `11-workflows-crud` | Workflows CRUD |
| `12-workflows-pagination` | Workflows pagination |
| `13-workflows-ui` | Workflows UI |
| `14-workflow-page` | Workflow page |
| `15-editor` | Visual node editor |
| `16-node-selector` | Node selector |
| `17-editor-state` | Editor state management |
| `18-node-execution` | Node execution engine |
| `19-node-variables` | Node variables |
| `20-node-templating` | Node templating |
| `21-node-realtime` | Node real-time updates |
| `22-google-form-trigger` | Google Form trigger |
| `23-stripe-trigger` | Stripe trigger |
| `24-ai-nodes` | AI nodes |
| `25-credentials` | Credentials management |
| `26-discord-slack-nodes` | Discord + Slack nodes |
| `27-executions-history` | Execution history |
| `28-encrypting-credentials` | Credential encryption |
| `29-github-google-auth` | GitHub + Google OAuth |

### Clues Left Behind
- 29 chapters = most comprehensive of all 4 repos
- Chapter 15 (`15-editor`) is the visual canvas starting point
- Chapters 22–26 are the integration nodes pattern — use these to add custom nodes
- Chapter 25 (`25-credentials`) shows how to store encrypted API credentials per user
- Chapter 28 (`28-encrypting-credentials`) — important for storing social media API keys securely
- The branch naming pattern reveals the build order — follow it exactly when Frankenshteining

---

## REPO 4: NEXTJS-VIBE — AI Vibe Coding Platform (Bolt/v0 Clone)
**Repo:** `https://github.com/code-with-antonio/nextjs-vibe`
**What it is:** AI-powered web app builder — chat with AI to create Next.js apps in real-time sandboxes
**Clone target:** Scaffold pattern for cocreatiq — E2B sandbox integration, agent tools pattern

### Stack
| Layer | Technology |
|-------|-----------|
| Framework | Next.js 15, React 19, TypeScript, Tailwind CSS v4 |
| Auth | Clerk |
| Database | Prisma ORM + PostgreSQL |
| API layer | tRPC |
| Background jobs | Inngest |
| AI | OpenAI, Anthropic OR Grok (interchangeable) |
| Sandboxes | E2B Code Interpreter (real-time Next.js sandboxes) |
| UI | shadcn/ui + Radix UI + Lucide React |

### Features Built
- AI-powered code generation via chat with AI agents
- Real-time Next.js app development in E2B sandboxes
- Live preview + code preview with split-pane interface
- File explorer with syntax highlighting + code theme
- Conversational project development with message history
- Smart usage tracking + rate limiting
- Subscription management with pro features
- Authentication (Clerk)
- Background job processing (Inngest)
- Project management + persistence

### Chapter Branch Map — 19 Chapters
| Branch | Chapter |
|--------|---------|
| `main` | Final project |
| `02-database` | Database setup |
| `03-trpc-setup` | tRPC setup |
| `04-background-jobs` | Background jobs |
| `05-ai-jobs` | AI background jobs |
| `06-e2b-sandboxes` | E2B sandbox integration |
| `07-agent-tools` | Agent tools |
| `08-messages` | Messages system |
| `09-projects` | Projects management |
| `10-messages-ui` | Messages UI |
| `11-project-header` | Project header |
| `12-fragment-view` | Fragment/code view |
| `13-code-view` | Code view |
| `14-home-page` | Home page |
| `15-theme` | Theme/styling |
| `16-authentication` | Authentication |
| `17-billing` | Billing |
| `18-agent-memory` | Agent memory |
| `19-bug-fixes` | Bug fixes |

### Folder Structure
```
src/
├── app/                      # Next.js app router pages
├── components/               # Reusable UI + file explorer
├── modules/                  # Feature modules: projects, messages, usage
├── inngest/                  # Background job functions + AI agent logic
├── lib/                      # Utilities + database client
└── trpc/                     # tRPC router + client setup
prisma/                       # Database schema + migrations
sandbox-templates/            # E2B sandbox templates
```

### ENV Variables
```
DATABASE_URL=
NEXT_PUBLIC_APP_URL=http://localhost:3000
OPENAI_API_KEY=
E2B_API_KEY=
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
CLERK_SECRET_KEY=
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
```

### Key Setup Steps
```bash
git clone https://github.com/code-with-antonio/nextjs-vibe.git
cd nextjs-vibe && npm install
cp env.example .env

# REQUIRED: Build E2B sandbox template (Docker must be running)
npm i -g @e2b/cli
e2b auth login
cd sandbox-templates/nextjs
e2b template build --name your-template-name --cmd "/compile_page.sh"
# Update template name in src/inngest/functions.ts

npx prisma migrate dev  # "init" for migration name
npm run dev
```

### Clues Left Behind
- E2B template MUST be built before running — Docker required
- `sandbox-templates/nextjs/compile_page.sh` — key entrypoint for sandboxes
- Template name in `src/inngest/functions.ts` must match built template name
- Chapter 07 (`07-agent-tools`) — the agent tools pattern (Frankenstein for Champ's tool system)
- Chapter 18 (`18-agent-memory`) — agent memory pattern (useful for Champ's memory integration)
- AI provider is fully interchangeable: OpenAI, Anthropic, or Grok — same pattern as other repos

---

## CROSS-REPO PATTERNS (The Clues Antonio Always Leaves)

### Universal Stack Pattern
Every Antonio repo follows the same foundation:
```
Framework:      Next.js (App Router) + React 19 + TypeScript
Auth:           Clerk (Organizations for multi-tenant)
Database:       Prisma or Drizzle + Postgres
API:            tRPC
Background:     Inngest
UI:             shadcn/ui + Tailwind v4
Monitoring:     Sentry
Billing:        Polar (usage-based) OR Stripe
Deployment:     Vercel or Railway
```

### The Branch Checkout Pattern
```bash
# To start from any chapter in any repo:
git clone https://github.com/code-with-antonio/[repo].git
cd [repo]
git checkout [chapter-branch]
npm install
cp .env.example .env
# Fill in API keys
npm run dev
```

### The 3-Terminal Pattern (Polaris + Nodebase)
When using Convex + Inngest:
```bash
# Terminal 1
npx convex dev

# Terminal 2
npm run dev

# Terminal 3
npx inngest-cli@latest dev
```

### The tRPC Router Pattern
All repos use tRPC for type-safe API calls:
- Server: `src/trpc/` or `src/server/`
- Client: `src/trpc/client.ts`
- Routers: feature-based in `src/features/[feature]/`
- This means zero manual API typing — it's all inferred

### The Feature Folder Pattern
Every repo organizes code by feature, not by type:
```
src/features/
  [feature-name]/
    actions.ts      # Server actions
    hooks.ts        # Client hooks
    schema.ts       # Zod schemas
    types.ts        # Types
    components/     # Feature-specific components
    queries.ts      # DB queries
```

### The Inngest Pattern (Background Jobs)
Used across all 4 repos for long-running operations:
```typescript
// Fire and forget — non-blocking UI
await inngest.send({ name: "app/task.started", data: { ... } })

// Inngest function handles the heavy work async
export const myFunction = inngest.createFunction(
  { id: "my-function" },
  { event: "app/task.started" },
  async ({ event, step }) => { ... }
)
```

### The Polar Billing Pattern (Resonance)
Usage-based metering — template for cocreatiq's credit system:
```
Meter 1: tts_generation → Sum over "characters" field
Meter 2: voice_creation → Count
Product: recurring subscription with metered prices
Starts at $0/month → scales with usage
```

### The Modal GPU Pattern (Resonance)
For any GPU workload (avatar rendering, TTS, image gen):
```python
# chatterbox_tts.py pattern
@app.function(gpu="A10G", secrets=[...])
def generate(...):
    # GPU work here
    pass
```
- Deploy with: `modal deploy [file].py`
- Cold start on first request after inactivity
- Mount R2 bucket for audio file access
- Protect endpoint with API key secret

---

## WHICH REPO TO FRANKENSTEIN FOR WHICH CLONE

| Building... | Start With | Key Chapters |
|-------------|-----------|-------------|
| Voice/TTS module | Resonance `main` | 04 (backend), 08 (voice clone), 09 (billing) |
| Workflow automation | Nodebase `main` | 15 (editor), 18 (execution), 22–26 (integrations) |
| AI code assistant | Polaris `main` | 11 (AI features), 13 (agent tools), 12 (conversations) |
| App scaffold | nextjs-vibe `main` | 05 (AI jobs), 07 (agent tools), 18 (agent memory) |
| Billing system | Any repo `billing` branch | Polar pattern (Resonance) or Stripe (Nodebase) |
| Auth + multi-tenant | Any repo `authentication` branch | Clerk Organizations pattern |
| Background jobs | Any repo `background-jobs` branch | Inngest pattern |
| Real-time features | Polaris (Convex) or Nodebase | Convex schema + queries pattern |
| Node/integration | Nodebase `24-ai-nodes` | Integration node pattern |
| Agent memory | nextjs-vibe `18-agent-memory` | Memory integration pattern |

---

## QUICK CLONE COMMAND REFERENCE

```bash
# Resonance (ElevenLabs clone)
git clone https://github.com/code-with-antonio/resonance.git

# Polaris (Cursor clone) — full 16 chapters
git clone https://github.com/code-with-antonio/polaris.git

# Nodebase (n8n/Zapier clone) — full 29 chapters
git clone https://github.com/code-with-antonio/nodebase.git

# nextjs-vibe (Bolt/v0 clone) — full 19 chapters
git clone https://github.com/code-with-antonio/nextjs-vibe.git

# Jump to specific chapter in any repo
git checkout [chapter-branch-name]

# Example — start Nodebase at the visual editor chapter
git clone https://github.com/code-with-antonio/nodebase.git
git checkout 15-editor
```

---

*This document represents the full blueprint of Antonio's 4 repos.*
*Combined: 73 chapter branches across 4 production-grade open-source apps.*
*Every clone cocreatiq needs is partially or fully solved in these repos.*
*Lives in: `champ_v3/development/ANTONIO_REPOS_BLUEPRINT.md`*
