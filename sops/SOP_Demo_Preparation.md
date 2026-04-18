# SOP: Demo Preparation

Version: 1.0
Owner: Global Kinect
Last updated: April 2026

## Purpose

Prepare and run a 20-minute platform demo for a prospect. This SOP ensures every demo is tailored to the prospect's specific countries and needs, never generic.

## Scope

All live platform demos delivered to prospects as part of the Global Kinect sales process. Covers preparation, delivery structure, and post-demo follow-up.

## Prerequisites

- Prospect's discovery notes with confirmed countries of operation
- Access to the Global Kinect platform demo environment
- Access to post-demo email templates: `C:\dev\globalkinect\sales\templates\emails\`
- Knowledge of MENA compliance requirements (WPS, GOSI, EOSB, Saudization) if the prospect operates in MENA

## Process

1. **Confirm the prospect's countries.** Review discovery notes and verify which countries the prospect operates in. If this information is incomplete or unclear, contact the prospect before the demo to confirm. Do not run a demo without knowing the exact country setup.

2. **Log into the demo environment.** Access the Global Kinect platform demo environment. Ensure it is functional and up to date before the scheduled demo time.

3. **Configure the demo for their specific countries.** Set up the demo environment to reflect the prospect's actual countries of operation. Do not show a generic country mix or a default configuration — the prospect should see their own setup.

4. **Prepare MENA compliance talking points.** If the prospect operates in any MENA country, prepare relevant compliance talking points:
   - **UAE**: WPS (Wage Protection System) file generation, GPSSA contributions
   - **Saudi Arabia**: GOSI (General Organization for Social Insurance) reporting, EOSB (End of Service Benefits) calculations, Saudization quota tracking
   - **Other MENA**: relevant statutory requirements for their specific countries
   
   Only raise the compliance points that apply to their countries — do not deliver a generic MENA overview.

5. **Run the demo using this structure (20 minutes total):**

   a. **The problem (2 min)** — Name the prospect's specific situation back to them. Reference their countries, their current pain, and what prompted them to take the call. Do not open with a company overview or generic slides.

   b. **The platform overview (3 min)** — Show the core value proposition: one submission, one view across all their countries. Keep this high-level and visual.

   c. **Their countries live (10 min)** — This is the core of the demo. Run a payroll cycle for their actual country setup. Show data entry, calculations, statutory outputs, and reporting for their specific configuration. This section must feel real, not theoretical.

   d. **HRIS and app (3 min)** — Show the connected HR layer: org structure, leave management, document handling. Then show the employee portal app — payslips, leave requests, document access from the employee's perspective.

   e. **Next step (2 min)** — Close with a specific next step: either a tailored proposal or a scoping call to confirm requirements. Do not end with "any questions?" as the final word — always propose a concrete next action.

6. **Send the follow-up within 2 hours.** After the demo, send a follow-up email using the appropriate post-demo template from `sales\templates\emails\`. Personalise it with key points discussed during the demo and the agreed next step.

## Quality checks

- [ ] Prospect's countries confirmed before demo
- [ ] Demo environment configured for their specific countries — not generic
- [ ] MENA compliance talking points prepared (if applicable)
- [ ] Demo follows the 5-part structure and stays within 20 minutes
- [ ] Demo closes with a specific next step, not "any questions?"
- [ ] Follow-up email sent within 2 hours of demo completion

## Related files

- `C:\dev\globalkinect\sales\templates\emails\email-post-demo-ae.html`
- `C:\dev\globalkinect\sales\templates\emails\email-post-demo-couk.html`

## Change log

| Date | Version | Change | Author |
|------|---------|--------|--------|
| April 2026 | 1.0 | Initial SOP created | Global Kinect |
