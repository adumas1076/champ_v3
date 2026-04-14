"""
Capture Module — Priestley Lead Gen Framework

Two capture mechanisms per Daniel Priestley's "Over-Subscribed" strategy:

  1. Waitlist (basic) — Email capture for future capacity or current capacity
     File: waitlist.py
     Use: "Join the waitlist" / "Get early access"
     When: Direct landing page CTA, bio links, DM triggers

  2. Assessment / Scorecard (advanced) — Signal of interest via readiness quiz
     File: assessment.py
     Use: "Are you ready for X?" — 20-40 questions, segments leads into pyramid
     When: Primary lead gen tool, 5-10x more captures than direct CTAs

Both feed the same lead pipeline with segmentation data. Assessment responses
ALSO get added to the waitlist automatically (dual capture).

4 pre-built assessments, one per influencer:
  - ai_readiness          (Anthony)         — Are You Ready to Run Your Business on AI?
  - ai_stack_readiness    (Influencer 1)    — Is Your AI Tech Stack Built Right?
  - scale_readiness       (Influencer 2)    — Is Your Business Ready to Scale?
  - brand_readiness       (Influencer 3)    — Does Your Brand Actually Convert?

Business Matrix: 0010_os_business_matrix_priestley_lead_gen.md
"""

from content_engine.capture.waitlist import (
    WaitlistEntry,
    CaptureResult,
    capture_waitlist_lead,
    store_lead,
    send_welcome_email,
    get_waitlist_count,
    get_waitlist_stats,
)

from content_engine.capture.assessment import (
    AssessmentDefinition,
    AssessmentQuestion,
    AssessmentResponse,
    QuestionType,
    ASSESSMENTS,
    get_assessment,
    list_assessments,
    get_assessment_questions,
    submit_assessment,
    score_assessment,
    get_assessment_stats,
)