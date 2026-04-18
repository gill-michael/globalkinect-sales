# SOP: Sales Outreach

Version: 1.0
Owner: Global Kinect
Last updated: April 2026

## Purpose

End-to-end direct outbound sales process from lead to demo booked. This SOP governs how new leads are classified, prioritised, contacted, and moved through the outreach pipeline until a demo is secured.

## Scope

All outbound sales activity originating from the Global Kinect sales engine. Covers LinkedIn outreach, email outreach, and follow-up cadences for all ICP segments.

## Prerequisites

- Access to the Lead Discovery DB in the sales engine
- Access to the Outreach Queue DB
- Access to the Pipeline DB
- Access to ICP hook files: `C:\dev\globalkinect\branding\outreach\icp-hooks\`
- Access to `C:\dev\globalkinect\sales\sops\SOP_Email_Outreach.md` (referenced for email cadence)

## Process

1. **Lead enters the pipeline.** A new lead enters the Lead Discovery DB via the sales sourcing engine. Confirm the lead record includes company name, contact name, role, and countries of operation at minimum.

2. **Assign ICP.** Classify the lead into one of the seven ICP segments:
   - **A1** — GCC enterprise, multi-country payroll
   - **A2** — GCC SME, single-country payroll
   - **A3** — GCC enterprise, EOR need
   - **B1** — European enterprise, multi-country payroll
   - **B2** — European SME, single-country payroll
   - **B3** — European enterprise, EOR need
   - **B4** — European enterprise, HRIS-led

3. **Score the lead.** Assign a priority level based on fit and signal strength:
   - **High** — strong ICP fit, active pain signal, decision-maker contact
   - **Medium** — good ICP fit, no immediate pain signal or contact is an influencer
   - **Low** — marginal fit or limited information available

4. **Select outreach channel.** Use LinkedIn as the primary channel. If the prospect has no LinkedIn presence or a connection request has gone unanswered for 7+ days, switch to email.

5. **Select the hook.** Open the ICP hook file for the prospect's segment from `branding\outreach\icp-hooks\`. Choose the hook that best matches the prospect's situation and pain signal.

6. **Personalise the message.** Customise the outreach with specific details:
   - Name their countries of operation
   - Reference their role
   - Reference their specific pain signal (e.g. "managing payroll across 4 GCC countries with different providers")
   - Do not use generic or templated language

7. **Queue the message.** Add the personalised message to the Outreach Queue DB with the appropriate status and scheduled send time.

8. **Run the follow-up cadence.** If the initial outreach is via email, follow the full cadence defined in `SOP_Email_Outreach.md`. If via LinkedIn, follow up with a second message on Day 5–7 if no reply, then move to email if still no response.

9. **On positive reply — book the demo.** When a prospect responds positively, book a demo within **24 hours**. Do not let warm leads cool. Send a calendar invite with the demo link and a brief agenda.

10. **Log all activity.** Record every touchpoint — messages sent, replies received, demo booked, status changes — in the Pipeline DB. No activity should go unlogged.

## Quality checks

- [ ] Lead has a confirmed ICP classification before outreach begins
- [ ] Lead is scored (high/medium/low)
- [ ] Outreach message is personalised with specific countries, role, and pain signal
- [ ] Hook matches the prospect's ICP segment
- [ ] Follow-up cadence follows SOP_Email_Outreach.md timing
- [ ] Demo booked within 24 hours of positive reply
- [ ] All activity logged in Pipeline DB

## Related files

- `C:\dev\globalkinect\branding\outreach\icp-hooks\` (ICP hook files)
- `C:\dev\globalkinect\sales\sops\SOP_Email_Outreach.md`
- `C:\dev\globalkinect\marketing\sops\SOP_Email_Outreach.md`

## Change log

| Date | Version | Change | Author |
|------|---------|--------|--------|
| April 2026 | 1.0 | Initial SOP created | Global Kinect |
