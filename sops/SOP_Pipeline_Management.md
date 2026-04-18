# SOP: Pipeline Management

Version: 1.0
Owner: Global Kinect
Last updated: April 2026

## Purpose

Keep the Notion sales pipeline and dashboard current. This SOP ensures the pipeline reflects reality at all times — no stale deals, no unactioned replies, no overdue tasks.

## Scope

Daily and weekly pipeline hygiene for the Global Kinect sales operation. Covers the sales dashboard, Outreach Queue, Execution Tasks, Pipeline DB, and Response Inbox.

## Prerequisites

- Access to the sales dashboard at `localhost:5174`
- Access to the Notion sales pipeline databases (Outreach Queue, Pipeline DB, Execution Tasks, Response Inbox, Lead Discovery DB)
- Access to the sales engine sourcing scan

## Process

1. **Open the sales dashboard daily.** Navigate to `localhost:5174` at the start of each working day. Review the summary view for any items requiring immediate attention.

2. **Review the Outreach Queue.** Check for any leads that have replied. Action all replied leads within **24 hours** — this means reading their response, classifying the reply (positive, negative, question, out of office), and taking the appropriate next step:
   - Positive reply → book demo (per SOP_Demo_Preparation.md)
   - Question → respond with a helpful, specific answer
   - Negative reply → mark as closed-lost with reason
   - Out of office → reschedule the next touch

3. **Review Execution Tasks.** Check for any overdue or upcoming tasks. Complete overdue tasks immediately or reschedule them with a new date and a note explaining the delay. Do not let tasks sit overdue without action.

4. **Update Pipeline DB deal stages.** After any prospect interaction — email reply, demo, call, proposal sent — update the deal stage in the Pipeline DB. Stages must reflect the current state of the conversation, not the last recorded action.

5. **Check the Response Inbox.** Review any new inbound responses that have arrived since the last check. For each response:
   - Classify the response type
   - Draft a reply
   - Queue the reply or send immediately depending on urgency

6. **Run the sourcing scan weekly.** Once per week, trigger the sales engine sourcing scan to discover new leads and replenish the Lead Discovery DB. Review the results for quality before adding to the outreach queue.

7. **Weekly pipeline review.** At the end of each week, review the full Pipeline board:
   - Move deals that have been inactive for 14+ days to **hold** status
   - Move deals with no response after full outreach cadence to **closed-lost**
   - Verify all active deals have a scheduled next action
   - Check overall pipeline health — are there enough leads at each stage?

## Quality checks

- [ ] Dashboard reviewed daily
- [ ] All replied leads actioned within 24 hours
- [ ] No execution tasks overdue without rescheduling
- [ ] Pipeline DB stages current after every interaction
- [ ] Response Inbox cleared daily
- [ ] Sourcing scan run weekly
- [ ] Weekly pipeline review completed — stale deals moved to hold or closed-lost

## Related files

- `C:\dev\globalkinect\sales\sops\SOP_Demo_Preparation.md`
- `C:\dev\globalkinect\sales\sops\SOP_Sales_Outreach.md`
- `C:\dev\globalkinect\marketing\sops\SOP_Email_Outreach.md`

## Change log

| Date | Version | Change | Author |
|------|---------|--------|--------|
| April 2026 | 1.0 | Initial SOP created | Global Kinect |
