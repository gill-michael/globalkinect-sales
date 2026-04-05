# Notion AI Prompts

Use these prompts when setting up or normalizing the Notion workspace for the
GlobalKinect Sales Engine.

Important operating rule for every prompt:

- keep all databases under the shared workspace page named exactly
  `GlobalKinect Sales Engine`
- do not create anything in a private space
- do not create linked databases when a standalone database is requested
- do not rename existing databases unless the prompt explicitly says to
- if a database already exists, normalize that exact database instead of
  creating a duplicate

## 1. Normalize `Lead Discovery`

```text
In the shared workspace page named exactly "GlobalKinect Sales Engine", inspect the standalone database named exactly "Lead Discovery".

Important:
- Only work on the database named exactly "Lead Discovery"
- Do not modify the databases named "Lead Intake", "Leads", "Pipeline", "Solution Recommendations", "Execution Tasks", "Deal Support", "Outreach Queue", or "Sales Engine Runs"
- Do not create a duplicate database
- If "Lead Discovery" already exists, normalize it instead of creating a new one

Ensure the database named exactly "Lead Discovery" has these properties:

Required:
- Company -> Title

Strongly recommended:
- Website URL -> URL
- Source URL -> URL
- Source Type -> Select or Text
- Evidence -> Text
- Contact -> Text
- Role -> Text
- Email -> Email
- LinkedIn URL -> URL
- Company Country -> Text
- Target Country Hint -> Select
- Campaign -> Text
- Notes -> Text
- Status -> Select or Status

Optional tracking properties:
- Confidence Score -> Number
- Qualification Summary -> Text
- Evidence Summary -> Text
- Lead Type -> Select
- Fit Reason -> Text
- Lead Reference -> Text
- Processed At -> Date
- Last Error -> Text

If Target Country Hint is a Select property, add these options:
- United Arab Emirates
- Saudi Arabia
- Egypt
- Qatar
- Kuwait
- Bahrain
- Oman
- Lebanon
- Jordan

If Lead Type is a Select property, add these options:
- direct_eor
- direct_payroll
- recruitment_partner
- hris

If Status is a Select or Status property, ensure these values exist:
- New
- Approved
- Ready
- Promoted
- Review
- Rejected
- Error
- Done
- Archived

Do not remove useful extra properties if they already exist.

At the end, confirm clearly whether the existing database named exactly "Lead Discovery" is now normalized under "GlobalKinect Sales Engine".
```

## 2. Add Optional Discovery Metadata

```text
In the shared workspace page named exactly "GlobalKinect Sales Engine", inspect the standalone database named exactly "Lead Discovery".

Important:
- Only work on the database named exactly "Lead Discovery"
- Do not modify any other database
- Do not create a duplicate database

Add these optional properties if they do not already exist:
- Discovery Key -> Text
- Published At -> Date
- Source Priority -> Number
- Source Trust Score -> Number
- Service Focus -> Select

If Service Focus is a Select property, ensure these options exist:
- payroll
- eor
- partner
- hris

Do not remove any existing properties.
At the end, confirm clearly that the optional metadata fields were added to the existing database named exactly "Lead Discovery".
```

## 3. Create Helpful `Lead Discovery` Views

```text
In the shared workspace page named exactly "GlobalKinect Sales Engine", inspect the standalone database named exactly "Lead Discovery".

Important:
- Only work on the database named exactly "Lead Discovery"
- Do not modify any other database
- Do not create a duplicate database

Create or normalize these views on the existing database named exactly "Lead Discovery":

1. All Discovery
2. Ready
   - filter Status is Ready or Approved or New
3. Promoted
   - filter Status is Promoted
4. Review
   - filter Status is Review
5. Rejected
   - filter Status is Rejected
6. Errors
   - filter Status is Error
7. High Trust Ready
   - filter Status is Ready or Approved or New
   - if the property "Source Trust Score" exists, filter Source Trust Score is greater than or equal to 7
8. HRIS Anywhere
   - if the property "Service Focus" exists, filter Service Focus is hris

If a view cannot be created exactly because a property is missing, keep the view name and use the closest valid configuration without creating extra databases.

At the end, confirm clearly which views now exist on the existing database named exactly "Lead Discovery".
```

## 4. Normalize `Lead Intake`

```text
In the shared workspace page named exactly "GlobalKinect Sales Engine", inspect the standalone database named exactly "Lead Intake".

Important:
- Only work on the database named exactly "Lead Intake"
- Do not modify the database named "Leads"
- Do not modify "Lead Discovery", "Pipeline", "Solution Recommendations", "Execution Tasks", "Deal Support", "Outreach Queue", or "Sales Engine Runs"
- Do not create a duplicate database

Ensure the database named exactly "Lead Intake" has these properties:

Required:
- Company -> Title

Strongly recommended:
- Contact -> Text
- Role -> Text
- Email -> Email
- LinkedIn URL -> URL
- Company Country -> Text
- Target Country -> Select
- Lead Type Hint -> Select
- Campaign -> Text
- Notes -> Text
- Status -> Select or Status

Optional tracking properties:
- Lead Reference -> Text
- Fit Reason -> Text
- Processed At -> Date
- Last Error -> Text

If Target Country is a Select property, add these options:
- United Arab Emirates
- Saudi Arabia
- Egypt
- Qatar
- Kuwait
- Bahrain
- Oman
- Lebanon
- Jordan

If Lead Type Hint is a Select property, add these options:
- direct_eor
- direct_payroll
- recruitment_partner
- hris

If Status is a Select or Status property, ensure these values exist:
- New
- Approved
- Ready
- Ingested
- Archived
- Rejected
- Done
- Error

Do not remove useful extra properties if they already exist.

At the end, confirm clearly whether the existing database named exactly "Lead Intake" is now normalized under "GlobalKinect Sales Engine".
```

## 5. Create Helpful `Lead Intake` Views

```text
In the shared workspace page named exactly "GlobalKinect Sales Engine", inspect the standalone database named exactly "Lead Intake".

Important:
- Only work on the database named exactly "Lead Intake"
- Do not modify any other database
- Do not create a duplicate database

Create or normalize these views on the existing database named exactly "Lead Intake":

1. All Intake
2. Ready To Process
   - filter Status is Ready or Approved or New
3. Processed
   - filter Status is Ingested or Done
4. Errors
   - filter Status is Error
5. Rejected
   - filter Status is Rejected

At the end, confirm clearly which views now exist on the existing database named exactly "Lead Intake".
```

## 6. Normalize `Outreach Queue`

```text
In the shared workspace page named exactly "GlobalKinect Sales Engine", inspect the standalone database named exactly "Outreach Queue".

Important:
- Only work on the database named exactly "Outreach Queue"
- Do not modify "Lead Discovery", "Lead Intake", "Leads", "Pipeline", "Solution Recommendations", "Execution Tasks", "Deal Support", or "Sales Engine Runs"
- Do not create a duplicate database

Ensure the database named exactly "Outreach Queue" has these properties:

- Lead Reference -> Title
- Company -> Text
- Contact -> Text
- Role -> Text
- Priority -> Select
- Target Country -> Select
- Sales Motion -> Select
- Primary Module -> Select
- Bundle Label -> Select
- Email Subject -> Text
- Email Message -> Text
- LinkedIn Message -> Text
- Follow-Up Message -> Text
- Status -> Select
- Generated At -> Date
- Run Marker -> Text
- Notes -> Text

Use these Select option labels:

Priority:
- High
- Medium
- Low

Target Country:
- United Arab Emirates
- Saudi Arabia
- Egypt
- Qatar
- Kuwait
- Bahrain
- Oman
- Lebanon
- Jordan

Sales Motion:
- Direct client
- Recruitment partner

Primary Module:
- EOR
- Payroll
- HRIS

Bundle Label:
- EOR only
- Payroll only
- HRIS only
- EOR + Payroll
- Payroll + HRIS
- EOR + HRIS
- Full Platform

Status:
- Ready to send
- Approved
- Sent
- Hold
- Regenerate

Do not remove useful extra properties if they already exist.

At the end, confirm clearly whether the existing database named exactly "Outreach Queue" is now normalized under "GlobalKinect Sales Engine".
```

## 7. Create Helpful `Outreach Queue` Views

```text
In the shared workspace page named exactly "GlobalKinect Sales Engine", inspect the standalone database named exactly "Outreach Queue".

Important:
- Only work on the database named exactly "Outreach Queue"
- Do not modify any other database
- Do not create a duplicate database

Create or normalize these views on the existing database named exactly "Outreach Queue":

1. All Outreach
2. Ready To Send
   - filter Status is Ready to send
3. Approved
   - filter Status is Approved
4. Sent
   - filter Status is Sent
5. Hold
   - filter Status is Hold
6. High Priority Ready
   - filter Status is Ready to send
   - filter Priority is High

At the end, confirm clearly which views now exist on the existing database named exactly "Outreach Queue".
```

## 8. Normalize `Sales Engine Runs`

```text
In the shared workspace page named exactly "GlobalKinect Sales Engine", inspect the standalone database named exactly "Sales Engine Runs".

Important:
- Only work on the database named exactly "Sales Engine Runs"
- Do not modify "Lead Discovery", "Lead Intake", "Outreach Queue", "Leads", "Pipeline", "Solution Recommendations", "Execution Tasks", or "Deal Support"
- Do not create a duplicate database

Ensure the database named exactly "Sales Engine Runs" has these properties:

- Run Marker -> Title
- Status -> Select
- Started At -> Date
- Completed At -> Date
- Lead Count -> Number
- Outreach Count -> Number
- Pipeline Count -> Number
- Task Count -> Number
- Error Summary -> Text
- Triggered By -> Select
- Notes -> Text

Optional property:
- Run Mode -> Select

Use these Select option labels:

Status:
- Running
- Completed
- Failed
- Partial

Triggered By:
- Manual
- Scheduler

If the optional property Run Mode exists, use these Select option labels:
- Live
- Shadow

Do not remove useful extra properties if they already exist.

At the end, confirm clearly whether the existing database named exactly "Sales Engine Runs" is now normalized under "GlobalKinect Sales Engine".
```

## 9. Create Helpful `Sales Engine Runs` Views

```text
In the shared workspace page named exactly "GlobalKinect Sales Engine", inspect the standalone database named exactly "Sales Engine Runs".

Important:
- Only work on the database named exactly "Sales Engine Runs"
- Do not modify any other database
- Do not create a duplicate database

Create or normalize these views on the existing database named exactly "Sales Engine Runs":

1. All Runs
2. Recent
   - sort Started At descending
3. Completed
   - filter Status is Completed
4. Failed
   - filter Status is Failed
5. Shadow Runs
   - if the property "Run Mode" exists, filter Run Mode is Shadow
6. Live Runs
   - if the property "Run Mode" exists, filter Run Mode is Live

At the end, confirm clearly which views now exist on the existing database named exactly "Sales Engine Runs".
```

## 10. Create `Sales Ops Daily Dashboard`

```text
In the shared workspace page named exactly "GlobalKinect Sales Engine", create a new page named exactly "Sales Ops Daily Dashboard".

Important:
- Create the page in the same shared workspace as the existing sales databases
- Do not create it in a private space
- Do not create new databases on this page
- Use linked views of the existing databases only
- Do not rename any existing database

On the page named exactly "Sales Ops Daily Dashboard", add these sections in this order:

1. Lead Discovery
- linked view of the database named exactly "Lead Discovery"
- prefer the view named "Ready"

2. Lead Intake
- linked view of the database named exactly "Lead Intake"
- prefer the view named "Ready To Process"

3. Outreach Queue
- linked view of the database named exactly "Outreach Queue"
- prefer the view named "Ready To Send"
- also add a second linked view for "High Priority Ready" if that view exists

4. Sales Engine Runs
- linked view of the database named exactly "Sales Engine Runs"
- prefer the view named "Recent"

5. Pipeline
- linked view of the database named exactly "Pipeline"

6. Execution Tasks
- linked view of the database named exactly "Execution Tasks"

At the end, confirm clearly that the page named exactly "Sales Ops Daily Dashboard" was created under "GlobalKinect Sales Engine" and that it uses linked views of the existing databases.
```
