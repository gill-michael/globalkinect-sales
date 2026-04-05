# Agent Registry

## Registry Purpose

This document defines the active agent estate for the GlobalKinect Sales Engine and clarifies which paths are preferred versus legacy-compatible.

## LeadResearchAgent

- Purpose: produce structured lead records for target commercial motions
- Inputs: campaign brief
- Outputs: `Lead`
- Status: built

## LeadScoringAgent

- Purpose: apply deterministic scoring, priority, and recommended angle logic
- Inputs: `Lead`
- Outputs: scored `Lead`
- Status: built

## LeadFeedbackAgent

- Purpose: collect existing outreach and pipeline state from Notion and turn it
  into reusable feedback signals
- Inputs: Notion `Outreach Queue`, Notion `Pipeline`, `Lead`
- Outputs: `LeadFeedbackIndex`, `LeadFeedbackSignal`
- Preferred path: active discovery suppression and scoring-adjustment flow
- Status: built

## OutreachReviewAgent

- Purpose: sync operator decisions from Notion `Outreach Queue` back into live
  pipeline state before the next daily discovery and packaging run
- Inputs: Notion `Outreach Queue`, Supabase `PipelineRecord`
- Outputs: updated `PipelineRecord`, `OutreachReviewSyncResult`
- Preferred path: live daily operator workflow
- Status: built

## SolutionDesignAgent

- Purpose: convert lead context into the commercially correct solution configuration
- Inputs: `Lead`, optional `PipelineRecord`
- Outputs: `SolutionRecommendation`
- Preferred path: primary commercial source of truth
- Status: built

## CRMUpdaterAgent

- Purpose: create and update timestamped pipeline records
- Inputs: `Lead`, `OutreachMessage`, `SolutionRecommendation`, `PipelineRecord`
- Outputs: `PipelineRecord`
- Preferred path: `create_pipeline_records_with_solution(...)`
- Legacy compatibility: `create_pipeline_records(...)` remains available
- Status: built

## MessageWriterAgent

- Purpose: draft commercially realistic outreach content
- Inputs: `Lead`, optional `SolutionRecommendation`
- Outputs: `OutreachMessage`
- Preferred path: `generate_messages_with_solution(...)`
- Legacy compatibility: `generate_messages(...)` remains available
- Status: built

## PipelineIntelligenceAgent

- Purpose: evaluate deterministic stage progression and next-action coherence
- Inputs: `PipelineRecord`
- Outputs: updated `PipelineRecord`, high-value deal filtering
- Preferred path: active execution flow
- Status: built

## LifecycleAgent

- Purpose: detect stale deals and refresh follow-up or escalation actions from timestamps
- Inputs: `PipelineRecord`
- Outputs: updated `PipelineRecord`
- Preferred path: active execution flow
- Status: built

## ExecutionAgent

- Purpose: convert pipeline state into concrete operator tasks
- Inputs: `PipelineRecord`
- Outputs: `ExecutionTask`
- Preferred path: active execution flow
- Status: built

## ProposalSupportAgent

- Purpose: generate call prep, recap, proposal framing, next steps, and objection support
- Inputs: `Lead`, `PipelineRecord`, optional `SolutionRecommendation`
- Outputs: `DealSupportPackage`
- Preferred path: `create_deal_support_packages_with_solution(...)`
- Legacy compatibility: legacy package-generation methods remain available
- Status: built

## NotionSyncAgent

- Purpose: coordinate deterministic syncing of generated entities into Notion operating views
- Inputs: leads, pipeline records, solution recommendations, execution tasks, deal support packages
- Outputs: Notion page upserts through `NotionService`
- Preferred path: active integration flow when Notion is configured
- Status: built

## Service Notes

- `SupabaseService` is the live-ready persistence layer for core commercial entities
- `NotionService` is the live-ready operating-sync layer for Notion databases
- `OperatorConsoleService` is the local operator-facing read/write layer over the
  existing Notion workflow and queue decisions
- `SolutionDesignAgent` remains the commercial source of truth for sales motion, primary module, bundle label, and recommended modules
- Solution-led paths should be used by default wherever they exist
