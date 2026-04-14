# 0028 — OS Business Matrix: Alex Hormozi — Unit Economics & LTV
**Specialist:** Alex Hormozi
**Source:** $100M Offers, $100M Leads, Acquisition.com workshops
**Category:** Unit Economics — the math behind every business decision
**Operator Target:** Operations Operator, Sales Operator, Retention Operator
**Date:** 2026-04-11

---

## Why This Matters

"The company that can spend the most to acquire a customer wins." — Hormozi

Every decision in Click to Client comes down to math. How much does it cost to get a customer? How much is that customer worth over their lifetime? If LTV > CAC, you have a business. If not, you have a hobby that burns money.

---

## Core Formula

```
LTV:CAC Ratio = Customer Lifetime Value / Customer Acquisition Cost
```

### Target Ratios by Business Type

| Business Type | Target Ratio | Example |
|--------------|-------------|---------|
| No human interaction | 3:1 | SaaS tool, self-serve |
| Some human element | 6:1 | Community + group calls |
| Multiple human touchpoints | 9:1+ | Done-for-you services |

**Cocreatiq Target:**
- Community ($97/mo) = 3:1 minimum (low-touch, self-serve)
- OS ($299/mo) = 6:1 minimum (operator setup + support)

---

## LTV Calculation

```
LTV = Price × (1 / Churn Rate) + Cross-sells + Upsells - COGS
```

### Breaking It Down

| Component | Formula | Anthony's Numbers |
|-----------|---------|-------------------|
| **Monthly Price** | What they pay | $97 (community) / $299 (OS) |
| **Churn Rate** | % who leave per month | Target: 5% (industry avg: 8-13%) |
| **Average Lifespan** | 1 / Churn Rate (months) | 1/0.05 = 20 months |
| **Base LTV** | Price × Lifespan | $97 × 20 = $1,940 / $299 × 20 = $5,980 |
| **Cross-sells** | Additional products sold | Community → OS upgrade ($299) |
| **Upsells** | Higher tier sold | OS Standard → OS Pro ($499) |
| **COGS** | Cost to deliver | API costs, compute, support |

### Churn Impact (Why Retention Is Everything)

| Monthly Churn | Avg Lifespan | LTV ($97) | LTV ($299) |
|--------------|-------------|-----------|------------|
| 13% (bad) | 7.7 months | $747 | $2,302 |
| 8% (average) | 12.5 months | $1,213 | $3,738 |
| 5% (good) | 20 months | $1,940 | $5,980 |
| 3% (excellent) | 33 months | $3,201 | $9,867 |

**Reducing churn from 13% to 3% = 4.3x increase in LTV.** That's the difference between a struggling business and a multi-million dollar one. Same number of customers.

---

## CAC Calculation

```
CAC = (Marketing Spend + Sales Payroll + Ad Costs + Tool Costs) / Customers Acquired
```

### Anthony's CAC Structure (AI-Powered = Low CAC)

| Cost | Traditional Business | Cocreatiq (AI Operators) |
|------|---------------------|------------------------|
| Marketing team | $5,000-15,000/mo | $0 (Marketing Operator) |
| Sales team | $8,000-20,000/mo | $0 (Sales Operator) |
| Ad spend | $3,000-10,000/mo | $3,000/mo (still need budget) |
| Tools | $500-2,000/mo | $500/mo (APIs, compute) |
| **Total** | **$16,500-47,000/mo** | **$3,500/mo** |

If $3,500/mo in total cost acquires 50 customers:
- CAC = $3,500 / 50 = $70
- LTV ($97 at 5% churn) = $1,940
- **LTV:CAC = 27.7:1** (insanely healthy)

Even at 20 customers:
- CAC = $175
- **LTV:CAC = 11:1** (still excellent)

**This is the AI operator advantage.** Traditional business needs $47K/mo in payroll. Anthony needs $3.5K/mo in API costs. Same output. 13x cost reduction.

---

## The $3M to $10M Value Zone

**Hormozi's key insight for exits/scaling:**

| Revenue | Typical Multiple | Enterprise Value |
|---------|-----------------|-----------------|
| $1M | 1x | $1M |
| $3M | 1-2x | $3-6M |
| $10M | 4-6x | $40-60M |

Going from $3M to $10M doesn't just 3.3x revenue — **the multiple itself expands from ~1x to ~4x**, creating a 13.2x return on enterprise value ($3M → $40M).

**Anthony's Path:**
- $97 × 3,000 members = $291K/mo = $3.5M/year (entering the zone)
- $97 × 3,000 + $299 × 500 = $440K/mo = $5.3M/year (in the zone)
- At $10M/year with 4x multiple = $40M enterprise value

---

## Improving the Ratio

### Increase LTV (top of the ratio)

| Lever | Action | Impact |
|-------|--------|--------|
| Decrease churn | 14 retention strategies (see 0013) | Massive — churn is the #1 LTV killer |
| Increase price | Add value first, then raise price | Direct LTV increase |
| Add cross-sells | Community → OS upgrade path | New revenue from existing customers |
| Add upsells | OS Standard → Pro → Enterprise | Higher ARPU |
| Premium tier | Done-for-you operator setup ($999/mo) | Captures willingness to pay |

### Decrease CAC (bottom of the ratio)

| Lever | Action | Impact |
|-------|--------|--------|
| Content marketing | Fixed cost, unlimited reach | CAC approaches zero over time |
| Referral program | Customers acquire customers | CAC = referral commission only |
| Optimize ads | 70/20/10 system (see 0027) | Lower CPL over time |
| Improve conversion | Better landing page, better offer | Same spend, more customers |
| Speed-to-lead | < 60 second response time | 70% close rate vs 20% |

---

## Break-Even Analysis

### Community ($97/month)

| Monthly Costs | Amount |
|--------------|--------|
| API/compute (per user) | ~$5/mo |
| Platform costs (shared) | $500/mo |
| Ad spend | $3,000/mo |
| Total fixed | $3,500/mo |
| Variable per user | $5/mo |

**Break-even:** $3,500 / ($97 - $5) = **38 members**

### OS ($299/month)

| Monthly Costs | Amount |
|--------------|--------|
| API/compute (per user) | ~$20/mo |
| Platform costs (shared) | $1,000/mo |
| Ad spend | $3,000/mo |
| Total fixed | $4,000/mo |
| Variable per user | $20/mo |

**Break-even:** $4,000 / ($299 - $20) = **15 users**

### Combined
At 38 community members + 15 OS users, Anthony is break-even. Everything after that is profit with 60-80% margins.

---

## Operator SOP: Unit Economics Monitoring

**When to use:** Monthly financial review, pricing decisions, channel evaluation, or scaling decisions.

1. Calculate current LTV (Price × 1/Churn + cross-sells + upsells - COGS)
2. Calculate current CAC (total spend / customers acquired)
3. Compute LTV:CAC ratio
4. Compare to target (3:1 for community, 6:1 for OS)
5. If ratio < target: diagnose whether LTV is too low or CAC is too high
6. Apply levers from the improvement tables above
7. Track monthly: churn rate, ARPU, CAC, LTV:CAC, break-even point

**Red flags:**
- Churn > 10% monthly → activate retention operator immediately
- CAC rising month-over-month → ad fatigue, rotate creative
- LTV:CAC < 2:1 → bleeding money, pause growth and fix unit economics first

---

## The Competitive Moat Formula

```
Higher LTV:CAC = ability to outspend competitors on acquisition
Outspending on acquisition = winning more customers
More customers = more data = better operators = higher LTV
Higher LTV = higher LTV:CAC ratio
= Flywheel
```

"The company that can spend the most to acquire a customer — ethically — wins." This is why fixing churn matters more than finding more leads. A 3% churn business can outspend a 13% churn business by 4.3x on the same revenue.