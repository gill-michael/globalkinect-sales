# Global Kinect — Sourcing & Buyer Surface Audit (Updated)
**Author:** Strategy review, April 2026 (revision 2)
**Scope:** Sourcing system, sales engine architecture, and the operating cadence for getting Global Kinect in front of buyers. SEO and AEO have been split out into companion documents.
**Audience:** Michael, founder, operating solo. Will be executed against by Claude Code.
**Companion documents:** `AE_SEO_AEO_AUDIT.md` (for `.ae` search and AI-answer-engine work), `COUK_SEO_AEO_AUDIT.md` (for `.co.uk` search and AI-answer-engine work).

---

## Revision notes — what changed from revision 1

Revision 1 of this audit treated `branding/GLOBAL_KINECT_BRAND.md` as the canonical brand source and flagged the README and the live websites as the things out of sync. **That was the wrong way around.**

Per Michael's correction, **`branding/README.md` is canonical** and the websites are aligned with it. The "100+ countries" coverage claim on `.co.uk`, the unconditional "Book a Demo" primary CTA, and the lack of an SME pricing-led exception in the master rules are all live, correct, and intentional. The supersedes-notice rewrite in `GLOBAL_KINECT_BRAND.md` is itself the document that's contested, not the README.

Three changes from revision 1 follow from that correction:

1. **The "fix the brand drift, kill 100+ countries" thread is removed.** It was misdirected. There is still a real reconciliation question between the README and the brand doc, but it is now the brand doc that needs to align with the README, not the websites that need to align with the brand doc. That reconciliation belongs to the SEO/AEO audits where it has practical consequences for the page checklists.
2. **The SME pricing-led exception is treated as an open question, not a rule to enforce.** The live `.ae` homepage implements a soft hybrid (Book a Demo primary, *"Running payroll in one country? See pricing →"* secondary) which is a sensible compromise that doesn't break the README. I'll flag where this matters for outbound — minimally — and leave the resolution to the SEO/AEO audits and to Michael's call.
3. **The SEO and AEO sections have been removed from this document and split into the two sister audits.** This document is now strictly about sourcing, the sales engine, the trigger surface, and the outbound cadence. Anything that was previously in this audit about country pages, AEO templates, schema, comparison-site SEO, or content publishing has moved to the sister docs.

Everything else from revision 1 stands. The structural finding about the sales engine (built around the wrong inputs), the RHQ goldmine, the five-channel weekly cadence, the trigger sources, the competitor sourcing analysis, the 30/60/90 plan, and the don'ts list — none of those depended on the brand-doc-vs-README question, and they remain the core of the recommendation.

---

## The one thing, if you read nothing else

You have built a Ferrari engine for the wrong race. The sales engine in `/sales` is an impressively engineered, 14-agent autonomous discovery machine fed almost entirely by news RSS feeds. The branding work in `/branding` is — separately — a genuinely strong positioning system. The two are not collaborating: the sales engine is sourcing yesterday's news from publishers, when the buyers it has correctly defined live in entirely different signal-rich systems (LinkedIn Sales Nav, MISA's RHQ list, Crunchbase, MAGNiTT, Companies House, Etimad).

A solo founder will not win by perfecting an autonomous outbound robot. A solo founder wins by **being present in five places at once on a weekly cadence**, with most of those places being inbound surfaces (now covered in the sister audits) that compound while you sleep, and the outbound surfaces being narrow, hand-picked, and trigger-anchored.

The recommendation in this document is therefore: **shrink the sales engine, redirect the time saved into a five-channel weekly cadence, replace the news RSS feed sourcing layer with a small set of trigger-rich list sources, and use the Saudi RHQ programme as the structural high-EV outbound goldmine.**

---

## 1. What you actually have — sales engine

### 1.1 The sales engine repo

- **22 sources across 8 lanes.** ~17 of the 22 are general-business news RSS feeds (Arabian Business, Zawya, The National, MEED, Construction Week, Hospitality Net, HR Grapevine, HR Executive, Business Traveller, Irish Times, Di.se, Wamda, Magnitt RSS). Three are job-board URLs (one of which is a LinkedIn Jobs *search URL*, which won't behave as RSS). One is a manual-strategic-account placeholder. One is a MISA RHQ feed.
- **14 agents** (Discovery, Research, Scoring, Solution Design, Message Writer, CRM Updater, Pipeline Intelligence, Lifecycle, Execution, Proposal Support, Notion Sync, Lead Feedback, Outreach Review, Autonomous Lane).
- **Status:** running in shadow mode, no live outreach yet, in pilot validation. `PIPELINE_GAPS.md` correctly identifies most of the structural problems already.

This is a textbook example of an engineering-led founder building the *system they want to operate* before the *thing they actually need pipeline-wise*. The architecture is clean, the docs are good, the tests are there — and almost none of it is structurally capable of producing the kind of leads you've defined in `ICP_SOURCING_PLAYBOOK.md`. RSS feeds from publications cannot tell you that a UAE company just crossed 50 employees, that an HR Director joined a mid-market German company that has just opened a Riyadh office, or that a B-round MAGNiTT-listed Riyadh fintech just hired its first People Lead. Those signals exist — but on **LinkedIn Sales Navigator, MISA's RHQ list, Crunchbase, MAGNiTT exports, Companies House cross-referenced with DIFC/ADGM, and the Etimad procurement portal**. None of which are in `discovery_sources.json`.

### 1.2 The brand-vs-engine drift that does still matter

Even with the README-as-canonical correction, `sales/ICP_SOURCING_PLAYBOOK.md` is out of sync with `branding/GLOBAL_KINECT_ICP.md` in ways that matter for outbound message generation:

- It defines 5 ICPs (A1/A2/A3/B1/B2), missing **B3 (International MENA Expander)**, **B4 (European-MENA Bridge)**, and **B5 (Platform Integrator)**. The brand doc and the ICP doc both define 8.
- It frames B1 as *"UK/European Company Expanding to GCC"* — the persona that the current ICP map calls **B3**, not B1.
- It uses "GlobalKinect" (one word) throughout — explicitly forbidden by the README.
- It references the recruitment director partner channel — discontinued.

These are all message-quality bugs. If you flip the engine to live outbound today, it will be sourcing-against and writing-for the wrong ICP map. **`sales/ICP_SOURCING_PLAYBOOK.md` needs to be rewritten against `branding/GLOBAL_KINECT_ICP.md` and `branding/README.md` as the source of truth**, before any live outbound goes out. This is a one-session job for Claude Code.

---

## 2. The structural gap — solving the wrong problem

Re-read the brief: *"how we find our clients needs to be efficient and yield success."*

The current architecture answers a different question: *"how do we autonomously surface accounts for outreach?"*

Those are not the same question. "Find clients efficiently as a solo founder" has five components, only one of which is account discovery:

1. **Be present where buyers already look.** SEO, AEO, comparison sites, communities, peer recommendations. **Covered in the SEO/AEO sister audits.**
2. **Be present where buyers go when something breaks.** Triggers — RHQ wins, funding, new country entry, new senior hire, regulatory change. The trigger surface exists but you're not collecting from it. Section 5 below.
3. **Be present in the head of the buyer's network.** LinkedIn personal posting, founder POV, teardowns of payroll horror stories. You have the voice guide; nothing publishing on it. Section 4 below.
4. **Make it cheap and obvious to start a conversation.** Calculators, cost guides, clean pricing pages, demo booking flow. **Covered in the SEO/AEO sister audits.**
5. **Direct outbound, surgically.** Hand-picked, peer-quality, on accounts you would walk into a meeting with. This is what your sales engine is trying to automate at scale. Stop trying. **At your stage and headcount, 25 surgically-picked outbound touches per week beat 500 automated ones, and you can't run 500 anyway.**

Your ICP playbook already contains pristine LinkedIn Sales Navigator queries for every ICP. It just doesn't connect those queries to a workflow you can execute weekly without engineering effort.

---

## 3. How your competitors actually source

I checked the current state of the EOR/global payroll competitive set. The shape is consistent with what you'd expect, with one or two updates worth flagging.

**Deel, Remote, Papaya, Multiplier, Oyster, Velocity, Playroll, Native Teams** all run roughly the same playbook:

1. Massive content/SEO machine. Hundreds of country guides, comparison pages, calculators. (Sister docs.)
2. Aggressive comparison/listicle SEO + paid placement. (Sister docs.)
3. Free tools as lead magnets — calculators, cost-of-employment, misclassification risk. (Sister docs.)
4. **Outbound at scale via SDR teams** — 5–20 SDRs per company, fed by Apollo / Clay / ZoomInfo / LinkedIn Sales Nav, sequenced through Outreach.io or Salesloft.
5. G2, Capterra, TrustRadius reviews — heavily harvested. (Sister docs.)
6. Reddit + nomad community + founder-Slack presence.
7. Channel partners — accounting firms, recruitment agencies, law firms. (Discontinued for Global Kinect per the README.)
8. Heavy paid search on competitor-name keywords.
9. Industry events — HR Tech, RemoteWork Summit, Future of Work, ADIPEC, GITEX, LEAP, FII.

**What this means for sourcing specifically (the rest is in the SEO/AEO docs):**

- You **cannot** out-spend them on paid search or SDR scale. Don't try.
- You **can** absolutely beat them on **MENA-specific outbound trigger volume** because the Saudi RHQ programme and the Vision 2030 supplier ecosystem produce a steady stream of European-buyer signals that none of them are systematically working. Section 6 below is dedicated to this.
- You **can** out-precision them per touch. They send 1,000 SDR emails to land one demo. You can send 25 hand-picked, trigger-anchored, brand-true messages per week and land more demos than that, because each one is to a buyer who has a *named* and *dated* reason to talk to you.

---

## 4. The shrewd play — the five-channel weekly cadence

Here is the operating model I would actually recommend you run, and the reasoning behind each piece. Total weekly time budget: **~13.5 hours**, fitting around platform development, demos, and the rest. Designed so that on any given week, you appear in front of a potential buyer through **at least five distinct surfaces.**

**Note:** Two of the five channels (structured content publication on the websites, and the comparison-site / listicle outreach) are now defined in detail in the SEO/AEO sister documents because the execution is content-heavy. This document defines the three outbound-and-network channels in full, and the two content channels at one-line summary level only.

### Channel 1 — Surgical outbound, one ICP at a time (3 hours/week)

**Cadence:** Monday morning batch. One ICP per week on rotation: **A1 → A3 → B3 → B4 → B1 → repeat**. Skip A2/B2 in outbound — they convert on inbound pricing pages, per the brand work.

**Volume:** 25 hand-picked accounts per week. Decision-maker identified, compliance trigger named, 3-line message drafted referencing the trigger.

**Source:** LinkedIn Sales Navigator, using the queries already written into `ICP_SOURCING_PLAYBOOK.md` section 6 (once that file is rewritten against the corrected ICP map). These queries are excellent — use them. Pair with the MISA RHQ list for B3 weeks. Pair with MAGNiTT/Crunchbase recent funding rounds for A3 weeks.

**Tooling:** Sales Nav + a Notion table + Claude (or Claude Code) doing the enrichment & message drafting against the ICP hook files. **Not the 14-agent system.** Skip Outreach.io / Apollo until you have proof.

**Why this is enough:** 25/week × 50 weeks = 1,250 named, qualified outreach touches per year, all on accounts that genuinely fit. At even a 3% reply rate that's ~37 conversations. At a 10% conversation-to-demo rate, ~4 demos. From your own ICP scoring matrix, accounts at the 25–30 score band are the targets — not the 15–20 band the current automated system would push through.

### Channel 2 — Structured content publication (4 hours/week)

**Cadence:** Tuesday. One published asset per week.

Defined in detail in `AE_SEO_AEO_AUDIT.md` section 4 and `COUK_SEO_AEO_AUDIT.md` section 4. The summary: rotate country pages, compliance deep-dives, calculators, and comparison pages on a weekly cadence, prioritising MENA-specific content because that's where competitors are weakest and the AEO opportunity is largest. Each asset passes the page-checklist in the relevant sister doc before shipping.

**Why it's a sourcing channel even though it's content:** every published page is a buyer-encounter surface that compounds. A single well-built country page or compliance guide delivers buyer impressions in week 1, week 12, and week 52. Outbound delivers impressions only in the week it's sent. Over a year, the content channel produces orders of magnitude more buyer encounters per founder hour invested than outbound does — but only if the indexability triage in section 1 of the sister docs is done first.

### Channel 3 — Founder POV on LinkedIn (1.5 hours/week)

**Cadence:** Wednesday. One post.

**Format:** 150–250 words, written to the standards in `branding/outreach/OUTREACH_VOICE.md` (no leverage, no synergies, no game-changing). Voice: senior operator talking to a peer. Topics rotate:

- **A real teardown of a payroll horror story (anonymised)** — *"Met a CFO in Dubai last week running 6 GCC countries through 5 different bureaus. Here's the real cost of that setup."*
- **A regulatory change explained in plain English** — *"What the new Etimad RHQ exemption actually means for foreign companies bidding on Saudi government work."*
- **A POV on the category** — *"Why MENA depth beats 100+ country claims in every Saudi conversation we have."*
- **A founder note from a Dubai/Riyadh/London trip.**

**Why:** zero of the competitor founders post credibly in this space. The category is owned by faceless brand pages. A real founder voice with operating experience and a real opinion compounds quickly on LinkedIn — and every B1/B3/B4 buyer is on LinkedIn daily.

### Channel 4 — Owned-list / community / comparison-site outreach (2 hours/week)

**Cadence:** Thursday.

Pick one of:

- **Substack/newsletter** to a small but growing list of HR/Finance leaders in your target markets. Monthly is fine. Repurpose the week's deep-dive (channel 2) into a short newsletter with one personal note.
- **Community participation** — find 3–5 active communities and show up properly (not as a vendor): r/PayrollNerds, r/GlobalEntrepreneurship, the People Ops community on Slack, the Riyadh Founders WhatsApp groups, the various MENA HR LinkedIn groups, the CIPD Middle East branch, the Saudi British Joint Business Council. Answer 2–3 questions a week. Linking to your content only when genuinely relevant.
- **Comparison-site outreach** — once per month, instead of community, pitch a comparison/review site (whichpayroll, gloroots, teamed, alcor, costbench, payrolloverview) to add Global Kinect to their MENA-specialist EOR list. The full target list is in the SEO/AEO sister docs section 1.3. One month of these makes you visible on inbound queries you currently get nothing from.

### Channel 5 — Trigger-driven warm reach (3 hours/week)

**Cadence:** Friday afternoon.

**This is the channel your sales engine was trying to be — but built on the wrong source.** Replace the 17 publication RSS feeds with a small, sharp set of trigger sources you actually mine:

| Source | What it tells you | What it triggers |
|---|---|---|
| **MISA RHQ list & press releases** | A new multinational just got an RHQ licence | Day-one Saudi payroll need. B3 priority. |
| **Etimad procurement portal** (Saudi gov contracts) | Foreign company won a Saudi gov contract | Same as above + named contract value. |
| **MAGNiTT funding rounds** (filtered: GCC, Seed–Series C, 50–300 employees) | Funded scale-up | A3 priority. |
| **Crunchbase/PitchBook alerts** (UK, IE, DE, NL, SE companies with new ME office) | European company opening Dubai/Riyadh office | B1 / B3 priority. |
| **Companies House watch** (UK companies registering DIFC/ADGM equivalent) | UK company with new MENA entity | B4 priority. |
| **LinkedIn Sales Navigator alerts** (saved ICP queries with "new in role" + "company added location") | New senior HR/Finance hire OR new office added | All ICPs. |
| **Google Alerts** on competitor names + "switch", "frustrated", "leaving" | Buyers actively dissatisfied | All ICPs. |
| **Saudi Press Agency / Argaam / Wamda** for giga-project supplier announcements | NEOM / Red Sea / Qiddiya supplier wins | A3, B3 priority. |

These are all publicly accessible. None require enterprise tools. Most can be set up in an hour. **They produce signals your current engine cannot.**

For each trigger that hits, the routine is: 15 minutes to verify the account, 10 minutes to identify the decision maker, 10 minutes to draft a hook. Five accounts per week. That's 250 trigger-based touches per year on accounts that have a *named, dated reason* to talk to you. **This is where the conversion is.**

### What the week looks like, in one table

| Day | Channel | Time | Output | Buyers reached |
|---|---|---|---|---|
| Mon | Surgical outbound | 3h | 25 LinkedIn touches on one ICP | 25 |
| Tue | Structured content (sister docs) | 4h | 1 published asset (page/calc/guide) | Compounding inbound |
| Wed | LinkedIn POV post | 1.5h | 1 founder post | LinkedIn impressions |
| Thu | Community / newsletter / comparison-site outreach | 2h | 1 owned/earned touch | Network |
| Fri | Trigger-driven warm reach | 3h | 5 hand-picked, trigger-anchored touches | 5 |
| **Total** | | **~13.5h** | | **~30 direct touches/week + compounding inbound** |

**Frequency-in-front-of-buyers metric:** ~30 direct touches/week + 1 piece of compounding owned content + 1 LinkedIn organic post that 3,000–10,000 buyers can see + comparison-site / community presence. That is 5 surfaces, every week, every week, every week.

---

## 5. What to do with the sales engine

Don't delete it. But do **stop building it as a sourcing platform** and re-cast it as something more honest about your stage.

### Keep:
- **`SolutionDesignAgent`** — this is the commercially useful core. Lead in, recommended bundle out. Keep it.
- **`MessageWriterAgent`** — useful as an *enrichment helper*, not as a sourcing pipeline. Use it interactively, ideally as a Claude Code agent or a Claude Skill rather than as part of an autonomous loop.
- **The Notion intake / queue surfaces** — these are your weekly working surface.
- **Supabase as the persistence layer** — fine, you're going to need it later anyway.
- **The ICP scoring matrix** — use it manually as the rubric for whether an account enters your weekly batch.

### Cut, hide, or defer:
- **The 17 publication RSS feeds.** Delete. They're producing noise the playbook itself defines as noise.
- **The 14-agent autonomous loop.** Stop running it as a discovery engine. Let it sit until you have enough deal volume that the *operational* parts (lifecycle, follow-up, deal support) are actually moving things you need them to move.
- **Lane-based discovery as currently configured.** Replace with the 8 trigger sources in section 4 above, fed into a simple Notion intake board.
- **The shadow-mode pilot itself.** It will not validate the workflow because the input data is structurally wrong. End it. Run the new operating model for 30 days and judge that.

### Add:
- **A weekly Claude Skill that runs once on Monday morning** to enrich a list of 25 accounts (you paste in names) with: company size, country mix, recent news, decision-maker LinkedIn URL, hook draft based on the matching ICP file. This is what AI is actually good at in this loop. It is not good at sourcing.
- **A Friday Claude Skill** that takes the week's trigger-source outputs and produces a deduplicated, ranked top-5 with hook drafts.
- **A page-checklist Claude Skill** that runs the brand quality checklists from the SEO/AEO sister docs against any new published page before it ships.

The principle: **AI for enrichment and writing, not for sourcing.** Sourcing is best done by structured, signal-rich list APIs (LinkedIn Sales Nav, MISA, MAGNiTT, Crunchbase). AI's job is to read what's in front of it and write the right thing.

### Do first: rewrite `sales/ICP_SOURCING_PLAYBOOK.md`

Before any of the above, do one specific cleanup. The current `sales/ICP_SOURCING_PLAYBOOK.md` is the file that the message-writing agents read for hooks and ICP definitions, and it is out of sync with the canonical brand work in three concrete ways:

- It defines 5 ICPs instead of 8 (missing B3, B4, B5)
- It frames B1 as the MENA expander persona that the current ICP map calls B3
- It uses "GlobalKinect" (one word) throughout

Have Claude Code rewrite `sales/ICP_SOURCING_PLAYBOOK.md` against `branding/GLOBAL_KINECT_ICP.md` and `branding/README.md` as the source of truth, in a single session. This is a prerequisite to any live outbound.

---

## 6. The RHQ goldmine — specific tactical play

This is the highest-EV tactical move in the entire estate.

**The fact pattern:**

- **700+ multinationals** now hold a Saudi RHQ licence (MISA confirmed early 2026; the original 2030 target of 500 has already been overshot).
- The programme requires each RHQ to incorporate in KSA, hire a minimum of 15 FTEs in year one (3 of which must be senior executive), commence operations within 6 months of licence, and run Saudi payroll from day one (GOSI, Mudad, Nitaqat, EOSB).
- Every one of these companies, by definition, is a B3 ICP at the moment they're licensed. Most are B4 if they also have European operations.
- MISA publishes new licence holders. Your sales engine has *one* MISA source sitting in *one* lane and isn't structured to act on it.
- Your `branding/sites/COUK_BRAND_BRIEF.md` already names "Saudi RHQ Programme" as the highest-value sales trigger for B3.
- None of Deel, Remote, or Papaya has a credible Saudi-payroll-day-one positioning. Their MENA pages are afterthoughts. **This is open ground.**

**The play:**

1. **Build a single Notion database — *RHQ Watch* — and seed it with every RHQ licence-holder published since January 2024.** ~700 rows. This is a one-time scrape; takes a half-day with Claude Code.
2. **Enrich each row with:** country of origin (UK / DE / NL / SE / IE / FR are highest priority for B3 outbound), sector, current global headcount, named Global HR / People / CFO contact on LinkedIn.
3. **Rank by ICP fit using your existing 30-point matrix.** The top ~150 are your B3 priority pipeline for the next two quarters.
4. **Build the two RHQ-specific landing pages** (`/saudi-rhq-payroll` on `.co.uk` and an equivalent on `.ae`) — defined in detail in the SEO/AEO sister docs section 4. These pages serve both the cold buyer who Googles "Saudi RHQ payroll" and the warm buyer you've sent the trigger-based message to.
5. **The Friday warm-reach channel works through this list, 5 per week, every week, until exhausted.** 150 priority accounts × 5/week ≈ 30 weeks of pipeline from this single source.
6. **MISA's ongoing announcements feed the list permanently.** Set a Google Alert on `site:misa.gov.sa "regional headquarters"` and on `"RHQ licence" Saudi`. Every new licence is a fresh row in the Notion database within 24 hours of publication.

**Why this beats everything else:** every other ICP requires you to *infer* the buying trigger. RHQ licence holders have a *legally mandated* one. They have to run Saudi payroll within 6 months of licence. You are the only credible MENA-native specialist with European HQ presence. The match is structural.

---

## 7. Measurement — replace "vibes" with frequency

You said the goal is to increase the number of times you put yourself in front of potential buyers. Don't run that as a feel — run it as a number.

**Weekly metric (the only one that matters at your stage):**

> *"How many qualified ICP buyers were exposed to Global Kinect — through any channel — in the last 7 days?"*

Count:
- Direct outbound touches that landed (LinkedIn message delivered, email opened) — 1 each
- LinkedIn organic post impressions to ICP-matched audiences (LinkedIn gives you this) — divide by 100
- Newsletter sends to ICP subscribers — 1 each
- Website visits from organic search to a page tagged to an ICP — 1 each (but this metric is meaningless until the SEO/AEO indexability triage in the sister docs is complete)
- Demo bookings — 5 each (they're the goal)
- Pricing page completions — 3 each
- Trigger-anchored warm reach (Friday channel) — 2 each (weighted higher because they're better)

Target for end of month 1: **150 weekly buyer exposures.**
Target for end of month 3: **500 weekly buyer exposures.**
Target for end of month 6: **1,500 weekly buyer exposures**, dominated by inbound (organic + AI citation + comparison-site referrals — assuming the SEO/AEO work is also being executed in parallel).

Track in a single Notion dashboard. Re-look every Friday afternoon. If a channel isn't producing, kill it and reallocate. If a channel is overperforming, double it.

---

## 8. The 30/60/90 plan

### Days 1–30: Fix, align, run the new cadence

**Week 1 — Brand/sales alignment cleanup**
- Have Claude Code rewrite `sales/ICP_SOURCING_PLAYBOOK.md` to reflect the 8-ICP map and the README-as-canonical brand rules. 2 hours of Claude Code time.
- Pause the shadow-mode sales engine. Don't delete; just stop the discovery loop.
- Begin the indexability triage from the SEO/AEO sister docs in parallel.

**Week 2 — Set up the cadence infrastructure**
- Build the *RHQ Watch* Notion database. Seed with 700 RHQ holders.
- Set up the trigger-source list (Google Alerts, MAGNiTT email digests, LinkedIn Sales Nav saved searches, MISA monitoring).
- Build the Notion *Weekly Buyers* board with the 5 channels as columns.
- Set up the Claude Skills for Monday enrichment, Friday trigger ranking, and page-checklist validation.

**Week 3 — Start running**
- Mon outbound on A1 (week 3) → Tue first content publication (per sister doc plan) → Wed first founder LinkedIn post → Thu first community participation round → Fri first 5 trigger touches.

**Week 4 — Measure & adjust**
- Count weekly buyer exposures. Adjust which channels need more/less.
- Pitch the first comparison/review site (whichpayroll, gloroots, teamed) for inclusion.

### Days 31–60: Compound

- Continue the weekly cadence. Rotate ICPs through outbound. Content publication continues per sister doc cadence.
- Begin enriching and outreach-ing the top 50 RHQ list entries (that's 10 weeks of Friday channel).
- Get listed on at least two comparison/listicle sites.
- Record and publish a second founder video — a teardown / point-of-view piece, not a product walkthrough.

### Days 61–90: Validate & narrow

- Look at the data. Which channels actually produced demos? Which trigger sources produced replies?
- Cut the bottom 20%. Double the top 20%.
- Decide whether to revive any of the original sales-engine agents to automate the bits of the new cadence that have proven valuable (e.g. if Friday triggers are producing real conversations, automate the enrichment step).
- Begin AI answer engine monitoring: is Global Kinect being cited yet for MENA payroll queries on ChatGPT/Claude/Perplexity? Track monthly. (Sister doc territory but the result feeds back into sourcing prioritisation.)

---

## 9. What NOT to do

A short list, because it's at least as important as the recommendations.

1. **Don't build more agents.** The temptation will be strong because you enjoy the engineering. Resist. Every hour spent on the sales engine is an hour not spent in front of a buyer or shipping content. The unit economics of "founder engineering time vs. founder pipeline time" overwhelmingly favour pipeline at your stage.
2. **Don't go to G2 / Capterra reviews yet.** Wait until you have 10+ live clients you can credibly ask. Premature reviews look thin. (The unclaimed listings in the sister-doc indexability work are different — those are about creating a backlink and a placeholder, not soliciting reviews.)
3. **Don't run paid search.** You will lose to Deel's CAC. Save the cash for the office expansions and the platform team.
4. **Don't hire an SDR.** Not yet. The cadence above is a single-founder operating model and the marginal SDR adds overhead before it adds throughput. Reconsider after 4 demos/week sustained for 8 weeks.
5. **Don't enable the Arabic flag, ever, without a native operator's review pass.** Anything else creates a credibility problem you can't easily undo.
6. **Don't reference the partner network anywhere.** Still discontinued. Still must not appear in any client-facing surface, including outbound messages and case studies.
7. **Don't optimise for volume of leads.** Optimise for volume of times a real ICP buyer encounters Global Kinect in a week. Those are different numbers.
8. **Don't run live outbound from the sales engine until `sales/ICP_SOURCING_PLAYBOOK.md` is rewritten.** The current file will produce mis-segmented, off-brand messages.

---

## 10. Closing — the honest summary

The branding work is excellent. The eight-ICP map, the dual-site logic, the AEO templates — these are the things that will eventually make Global Kinect known in its category. They are mostly waiting on execution rather than redesign.

The sales engine is engineered with care but pointing at the wrong inputs and optimising for the wrong outcome. Replace it as a *sourcing system* with a *weekly cadence* you can run by hand, fed by signal-rich sources, with AI doing enrichment rather than discovery. Reuse its persistence and message-writing components later, when there's a real volume of deals to operate against.

The single biggest tactical play in the sourcing layer specifically is the **RHQ list**, because the buying trigger is structurally guaranteed and the volume is large enough to feed the Friday channel for two quarters with no other source. The single biggest *overall* unlock is the SEO/AEO indexability triage in the sister documents, because it is the gating issue for all of the compounding inbound channels — but that is a different document and a different operating mode than this one.

Run the five-channel cadence for 30 days. Measure weekly buyer exposures. If the number isn't 4–5x what it is today by day 30, the model is wrong and we revisit. I don't think it will be.

The only reason a solo operator wins against Deel and Remote in this category is **specificity** — being the obvious answer to a small, well-defined question (*"who runs Saudi payroll for European companies entering under the RHQ programme?"*) rather than a vague one (*"who runs global payroll?"*). You have already done the hard work of defining the question. Now show up, on cadence, in the places the people asking it are looking. That's the whole game.

---

*End of sourcing audit (revision 2). Companion documents: `AE_SEO_AEO_AUDIT.md` and `COUK_SEO_AEO_AUDIT.md`.*
