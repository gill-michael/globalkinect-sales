# Platform Realignment Audit

## Purpose

This document records the current mismatch between the system's working assumptions and GlobalKinect's actual commercial model. It is intended as a reviewable transition artifact before deeper refactoring begins.

## 1. What The System Currently Assumes

The current system still carries service-line assumptions in several places:

- `lead_type` is often treated as if it directly represents the product being sold
- scoring logic uses lead-type categories such as `direct_eor`, `direct_payroll`, `recruitment_partner`, and `hris` as the main commercial signal
- message generation still frames outreach primarily around one immediate service motion
- proposal support still produces offer framing that is usually tied to a single service-led entry point
- persistence currently stores lead and proposal context without an explicit model for bundle configuration

Current practical effect:

- one lead is often interpreted as one service line
- buyer motion and recommended solution bundle are not yet separated
- the system can execute sales workflow steps, but it does not yet consistently express the modular platform truth

## 2. What The Business Reality Actually Is

GlobalKinect sells one modular employment infrastructure platform across:

- UAE
- Saudi Arabia
- Egypt

That platform is configured across three modules:

- EOR
- Payroll
- HRIS

The platform may be sold as:

- EOR only
- Payroll only
- HRIS only
- EOR + Payroll
- Payroll + HRIS
- EOR + HRIS
- EOR + Payroll + HRIS

Commercially, this means the system must distinguish between:

1. sales motion or buyer motion
2. actual recommended solution bundle
3. primary commercial entry point

Examples:

- a direct client may enter through Payroll but still be recommended Payroll + HRIS
- a direct client may enter through EOR but be commercially better suited to the full platform
- a recruitment partner may still map to EOR + Payroll support even though the buyer motion is partner-led rather than direct-client-led

## 3. Files Most Affected By The Mismatch

### Core model assumptions

- `app/models/lead.py`
  The model still uses `lead_type` as the main commercial category and does not yet hold explicit bundle recommendation fields.

### Scoring logic

- `app/agents/lead_scoring_agent.py`
  Scoring still weights the current lead-type categories directly, which is useful operationally but not yet bundle-aware.

### Messaging logic

- `app/agents/message_writer_agent.py`
  Messaging adapts to current service-led entry motions and does not yet explicitly reflect modular bundle recommendations.

### Proposal and deal support logic

- `app/agents/proposal_support_agent.py`
  Proposal framing still maps closely to the current lead type, even though the commercial recommendation may be a broader platform bundle.

### Persistence model assumptions

- `app/services/supabase_service.py`
  Current persistence supports leads, outreach, pipeline records, and deal support packages, but not solution bundle recommendations.

### Orchestration assumptions

- `main.py`
  The runtime flow executes lead research, scoring, messaging, pipeline creation, and proposal support, but until now it has lacked an explicit bundle-design step.

### Test assumptions

- `tests/test_message_writer_agent.py`
- `tests/test_proposal_support_agent.py`
- `tests/test_supabase_service.py`

These tests validate the current service-led logic and persistence behavior. They are still valid for the current transition state, but they do not yet encode the full modular platform model.

## 4. What Should Happen Next

The transition should proceed in controlled steps:

### Step 1: Introduce canonical platform vocabulary

- define platform modules
- define sales motion separately from solution bundle
- define canonical bundle labels

### Step 2: Add a transition-layer recommendation model

- create a dedicated solution recommendation object
- infer bundle configuration from current lead context without rewriting every agent immediately

### Step 3: Generate solution recommendations alongside the current flow

- keep scoring, messaging, proposal support, and persistence working as-is
- add a reviewable layer that explicitly shows what GlobalKinect should actually sell

### Step 4: Review downstream dependencies

After the solution-design layer is reviewed, the following modules should be updated in sequence:

- scoring logic
- messaging logic
- proposal support logic
- persistence schema and storage methods
- tests and documentation

### Step 5: Refactor toward platform truth

Longer term, the system should evolve from:

- lead_type-driven single-service assumptions

to:

- sales motion
- recommended bundle
- primary module
- platform expansion path

This audit does not change that downstream behavior by itself. It creates the review basis for the next refactoring pass.
