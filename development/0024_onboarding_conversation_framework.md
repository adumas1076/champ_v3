# 0024 — Onboarding Conversation Framework
**Date:** 2026-04-10
**Category:** OS Onboarding / UX / Conversation Design
**Status:** Design Phase

---

## The Principle

Every screen is a conversation, not a form. The onboarding guide ASKS the user — out loud on voice, as a headline on screen. The UI elements (inputs, buttons, cards) are how the user ANSWERS. No form labels. No "Step 4 of 11." Just a person talking to you.

3 C's govern every screen:
- **Convenience** — one question per screen, skip buttons on optional steps
- **Clarity** — user always knows what's next and why
- **Confidence** — by the end, the OS knows them better than any tool they've ever used

---

## Screen 1: Language

**Guide says:** "What language do you speak?"

**UI:** Language tiles (English, Espanol, Francais, more). Tap to select. Auto-advances.

**Data stored:** `user.language` → Supabase `mem_profile`

**Voice path:** Guide speaks this in English first, then the selected language confirms.

**Skip?** No — required.

---

## Screen 2: Choose Your Onboarding Guide

**Guide says:** *(no guide yet — this IS the choice)*

**Screen text:** "Choose your guide."

**UI:** Two avatar cards side by side — male voice, female voice. Tap one, hear a 3-second sample: "Hey, I'm going to walk you through setting up your OS. Let's go." Auto-advances after selection.

**Data stored:** `user.guide_voice` → used for TTS in screens 3-10

**Voice path:** Both samples play on hover/tap. Selected guide takes over from screen 3.

**Skip?** No — required. The OS needs a voice.

---

## Screen 3: Sign In

**Guide says:** "Let's get you set up — sign in so I can remember you next time."

**UI:** Three buttons — Google OAuth, Microsoft OAuth, Email/Password. Clean, centered. Logo at top.

**Data stored:** `user_id` created in Supabase. Auth token. Email.

**Voice path:** Guide says the line, waits for tap. After sign in: "Got it, you're in."

**Skip?** No — required. Everything after this is tied to their account.

**On success:** Guide says "Nice, welcome. Let me learn a little about you."

---

## Screen 4: Who Are You?

**Guide says:** "Tell me about yourself — what's your name, and what do you do?"

**UI:**
- Name field (text input)
- Business type (dropdown or tiles: Creator, Agency, SaaS, Freelancer, E-commerce, Coach, Other)
- Role (dropdown: Founder, CEO, Marketer, Developer, Creator, Freelancer, Other)
- Team size (tiles: Just me, 2-5, 6-20, 20+)

**Data stored:** All → Supabase `mem_profile` (key/value pairs: name, business_type, role, team_size)

**Voice path:** Guide asks each sub-question conversationally:
- "What's your name?"
- *(user answers)*
- "Nice to meet you, [name]. What kind of business do you run?"
- *(user answers)*
- "And is it just you or do you have a team?"
- *(user answers)*
- "Got it. Let's connect your tools."

**Skip?** Name required. Business type and role optional but encouraged.

**On complete:** Guide says "Got it, [name]. Let's connect your tools."

---

## Screen 5: Connect Your Stack

**Guide says:** "What tools are you already using? Let's connect them so your team can reach them."

**UI:** Grid of integration tiles with logos:
- Gmail / Outlook
- Google Calendar
- Slack
- Notion
- Stripe
- GitHub
- YouTube
- Instagram
- LinkedIn
- CRM (HubSpot / Salesforce)

Each tile: tap to connect (Nango OAuth flow), checkmark when connected. "Skip for now" button at bottom.

**Data stored:** Nango connection tokens per service. List of connected services → `mem_profile.connected_apps`

**Voice path:** Guide says the line. As user connects each one: "Gmail connected. Nice." / "Stripe connected — your operators can handle payments now." After 2-3 connections or skip: "That's a good start. You can always add more later."

**Skip?** Yes — "Skip for now" button. Guide says "No worries, you can connect these anytime."

**On complete:** Guide says "Your operators can reach [Gmail, Calendar, Slack] now. Let me introduce you to the team."

---

## Screen 6: Meet Your Team

**Guide says:** "These are your operators — tap any of them to hear how they sound."

**UI:** 9 operator cards in a grid or horizontal scroll:

| Operator | One-liner |
|---|---|
| Champ | Your personal AI partner. Handles anything. |
| Sales | Closes deals. Runs the CLOSER framework. |
| Marketing | Creates content. Builds your brand. |
| Lead Gen | Captures and qualifies leads. |
| Research | Deep research and competitive intel. |
| Operations | System health and scaling. |
| Onboarding | Onboards your clients seamlessly. |
| Retention | Prevents churn. Keeps clients engaged. |
| QA | Checks every operator's work before it ships. |

Each card: tap to hear a 5-second voice sample from that operator. Long-press or expand to see their specialty, tools, and voice options. User can swap voices per operator if they want.

**Data stored:** Voice selections per operator → `mem_profile.operator_voices`

**Voice path:** Guide introduces the team: "You've got nine operators. Each one has a specialty. Champ is your default — he handles anything. Tap any card to hear how they sound."

**Skip?** No — but voice customization is optional. They must SEE the team.

**On complete:** Guide says "That's your team. Now let's teach them how YOU do things."

---

## Screen 7: Connect Your SOPs

**Guide says:** "How do you run your business? Upload your playbooks and your operators will learn your way."

**UI:**
- Drag-and-drop upload zone (accepts PDF, DOCX, MD, TXT, Google Docs link)
- Example prompts below: "Sales scripts", "Client onboarding checklist", "Content calendar", "Pricing guide", "Team SOPs"
- "Skip for now" button

**Data stored:** Files → Supabase Storage. Parsed text → operator knowledge blocks. File metadata → `mem_profile.sops_uploaded`

**Voice path:** Guide explains: "Your operators are smart — but they need YOUR playbooks to be smart about YOUR business. Drop in your sales scripts, onboarding checklists, content calendars — whatever you use. They'll learn your way, not the generic way."

After upload: "Got it — your [Sales] operator now knows your pricing guide. That's powerful."

If skip: "No worries. Your operators will start with proven frameworks and learn your style as you work together."

**Skip?** Yes — this is high-value but optional. Many users won't have SOPs ready.

**On complete:** Guide says "Now let's talk about where you're headed."

---

## Screen 8: Business Goals

**Guide says:** "What does success look like for you in 90 days?"

**UI:**
- One big text input field (free text) — "Describe your version of success"
- Below: quick-select tiles for common goals:
  - Hit $X revenue
  - Launch a product
  - Get first 100 customers
  - Scale content output
  - Hire / build team
  - Reduce workload
  - "Something else"
- Revenue target field (optional): "$_____ / month"

**Data stored:** `mem_profile.goals_90day`, `mem_profile.revenue_target`

**Voice path:** Guide asks: "What does success look like for you in ninety days? Not what you think I want to hear — what would actually make you say 'this was worth it'?"

*(user answers)*

"That's clear. Your operators will track that. Now tell me what's in the way."

**Skip?** No — this is critical. Even a vague answer helps.

**On complete:** Guide says "[name], that's a solid target. Now tell me what's slowing you down."

---

## Screen 9: Bottlenecks

**Guide says:** "What's the one thing slowing you down the most right now?"

**UI:**
- Quick-select tiles (pick 1-3):
  - Not enough leads
  - Can't close sales
  - No time for content
  - Operations are chaos
  - Can't retain clients
  - Marketing isn't working
  - Too much manual work
  - "I don't know yet"
- Optional text field: "Tell me more..."

**Data stored:** `mem_profile.bottlenecks` (array), `mem_profile.bottleneck_detail`

**Voice path:** Guide asks: "What's the one thing slowing you down the most right now? Be real with me."

*(user answers)*

Guide maps it: "So leads are the bottleneck. That means Lead Gen and Marketing are going to be your heaviest hitters. They're ready."

If "I don't know yet": "That's okay — Champ will help you figure it out. That's what he does."

**Skip?** No — even "I don't know yet" is an answer.

**On complete:** Guide says "Got it. Give me a sec — I'm setting everything up."

---

## Screen 10: Connecting...

**Guide says:** "Give me a sec — I'm setting everything up for you."

**UI:** 
- Loading animation (cosmic gradient, pulsing)
- Progress messages cycling:
  - "Loading your memory..."
  - "Registering your operators..."
  - "Building your team's knowledge..."
  - "Connecting your tools..."
  - "Personalizing your experience..."
  - "Almost ready..."

**What actually happens:**
1. Write all collected data to Supabase `mem_profile`
2. Register all 9 operators via `registry.register_config()`
3. Load SOPs into knowledge blocks
4. Build OS System Prompt with user's data
5. Spawn Champ with full context

**Data stored:** Everything written, operators registered, Champ spawned.

**Voice path:** Guide narrates the progress: "Loading your memory... registering your operators... almost there..."

**Skip?** No — system is booting.

**Duration:** 3-8 seconds real, feels intentional.

**On complete:** Guide says "You're all set. Meet Champ."

---

## Screen 11: Meet Champ

**Guide says:** *(Guide steps aside. Champ takes over.)*

**Champ says:** "Yo [name], welcome to the team. I already know your business, your goals, and what's in the way. What do you want to work on first?"

**UI:** Full-screen conversation interface. Voice waveform or avatar. Text input at bottom as fallback. The OS is live.

**What Champ knows (from onboarding):**
- User's name, business type, role, team size
- Connected apps
- SOPs and playbooks (if uploaded)
- 90-day success definition
- Revenue target
- Top bottlenecks
- Preferred voice/channel
- Language

**Data stored:** First session begins. Transcript logging starts. Learning loop active.

**Voice path:** Champ's first line is conversational, warm, and proves he knows them. Not "How can I help you today?" — that's a chatbot. "Yo [name], welcome to the team" — that's an operator.

**Skip?** No — this IS the product.

---

## Conversation Flow Summary

```
Screen 1: "What language do you speak?"
    ↓
Screen 2: "Choose your guide." [male / female]
    ↓ guide takes over
Screen 3: "Let's get you set up — sign in so I can remember you next time."
    ↓
Screen 4: "Tell me about yourself — what's your name, and what do you do?"
    ↓
Screen 5: "What tools are you already using? Let's connect them."
    ↓
Screen 6: "These are your operators — tap any to hear how they sound."
    ↓
Screen 7: "How do you run your business? Upload your playbooks."
    ↓
Screen 8: "What does success look like for you in 90 days?"
    ↓
Screen 9: "What's the one thing slowing you down the most right now?"
    ↓
Screen 10: "Give me a sec — I'm setting everything up for you."
    ↓
Screen 11: "Yo [name], welcome to the team."
```

---

## Data Flow: What Gets Stored Where

| Screen | Data | Supabase Table | Used By |
|---|---|---|---|
| 1 | Language | `mem_profile` | All operators (localization) |
| 2 | Guide voice | session config | Onboarding TTS only |
| 3 | User ID, email | `auth.users` | Everything |
| 4 | Name, business, role, team size | `mem_profile` | All operators |
| 5 | Connected apps | `mem_profile` + Nango | Operators that need app access |
| 6 | Voice selections | `mem_profile` | Each operator's TTS config |
| 7 | SOPs / playbooks | Supabase Storage + knowledge blocks | Operators matching the SOP domain |
| 8 | 90-day goals, revenue target | `mem_profile` | All operators (purpose) |
| 9 | Bottlenecks | `mem_profile` | OS routing (priority operators) |
| 10 | — | All tables written | — |
| 11 | First conversation | `sessions` + `transcripts` | Learning loop |

---

## Design Rules

1. **One question per screen.** If it has two questions, it's two screens.
2. **The guide's question IS the headline.** No form labels above it.
3. **Every screen has a skip option** except: Language (1), Guide (2), Sign In (3), Goals (8), Bottlenecks (9), Connecting (10), Meet Champ (11).
4. **Progress dots at the bottom.** 11 dots. User always knows where they are.
5. **Dark mode default.** Cosmic gradient background. Light mode available.
6. **Voice and tap are parallel paths.** Every screen works both ways.
7. **The guide adapts.** Uses the user's name after screen 4. References their business type. Gets more specific as it learns more.
8. **No back-tracking friction.** User can go back to any screen and change answers.
9. **Total time: 2-4 minutes** tapping through, 4-6 minutes on voice path.