# Explorium plaintext-email + mobile + LinkedIn investigation

**Date:** 2026-04-27
**Status:** Investigation complete. Implementation pending Michael's confirmation.
**Authority:** Explorium developer docs — [developers.explorium.ai](https://developers.explorium.ai/) (April 2026).

---

## TL;DR (the headline)

`POST /v1/prospects` is the wrong endpoint to ask for plaintext contact data. It only ever returns `professional_email_hashed`. Plaintext addresses, mobile numbers, and richer LinkedIn-derived profile fields all live behind **separate paid enrichment endpoints**:

| Want | Endpoint | Per-prospect cost | Bulk? |
|---|---|---|---|
| Plaintext email | `POST /v1/prospects/contacts_information/bulk_enrich` (`contact_types=["email"]`) | **2 credits** | up to 50/call |
| Plaintext mobile + email together | `POST /v1/prospects/contacts_information/bulk_enrich` (default `contact_types`) | **5 credits** | up to 50/call |
| Richer LinkedIn profile (experience, education, skills, company_linkedin, job_level enums) | `POST /v1/prospects/profiles/enrich` | **uncertain — not documented** | no bulk variant |

Our current scan script (`scripts/vibe_prospecting_scan.py`) calls neither. That's why every Notion `Email`, `Mobile`, and richer-profile field is blank for Vibe-sourced rows.

**Note on LinkedIn URL specifically:** the basic `/v1/prospects` endpoint *already returns* `linkedin_url_array` for free. The scan script already extracts the first entry into the Notion `LinkedIn URL` property. So if "enrich LinkedIn" means just the URL, that's already happening — verifiable by running the existing dry-run. If it means richer profile data (experience history, skills, education, company LinkedIn URL), that needs the profile-enrichment endpoint.

The fix is additive — add a third step to the existing two-step flow. See "Recommended next step" at the bottom.

---

## 1. What Explorium's API actually returns

### `POST /v1/prospects` (the endpoint we currently use, "full" mode)

The response object exposes:
- `professional_email_hashed` — a SHA-style hash of the email, never plaintext.
- No `professional_email`, `email`, `work_email`, `personal_email`, `verified_email`, `business_email`, or `email_address` field exists in the documented schema.
- Switching from `mode: "preview"` to `mode: "full"` does not unmask the email — the hashed-only behaviour holds in both modes.

There is no `enrich_emails`, `include_pii`, `unmask_emails`, or equivalent flag on the prospects endpoint.

### `POST /v1/prospects/contacts_information/enrich` (single, paid)

Per [the Contact details enrichment doc](https://developers.explorium.ai/reference/prospects/enrichments/contacts_information.md):

- **Method/path:** `POST /v1/prospects/contacts_information/enrich`
- **Request body:** `{"prospect_id": "<40-hex>", "parameters": {"contact_types": ["email"]}}` — `parameters` is optional; default returns both email and phone.
- **Response (plaintext):**
  - `professions_email` — string, plaintext professional email
  - `professional_email_status` — enum `"valid" | "catch-all" | "invalid"`
  - `emails` — array of `{address, type}` objects (`type` = `"personal" | "professional"`)
  - `mobile_phone` — string, plaintext
  - `phone_numbers` — array of plaintext phone objects
- **Cost:**
  - Email only: **2 credits** per prospect
  - Phone only: 5 credits per prospect
  - Both (default): 5 credits per prospect

### `POST /v1/prospects/contacts_information/bulk_enrich` (batched, paid)

Per [the Contact details (Bulk) doc](https://developers.explorium.ai/reference/prospects/enrichments/bulk/prospects_contacts_information_bulk_enrich.md):

- **Method/path:** `POST /v1/prospects/contacts_information/bulk_enrich`
- **Request body:** `{"prospect_ids": ["<40-hex>", ...]}` — between 1 and 50 IDs, regex `^[a-f0-9]{40}$`.
- **Response:** plaintext per prospect — `professions_email`, `professional_email_status`, `emails[]` (with `address` + `type`), **plus `mobile_phone` and `phone_numbers[]` when phone is requested**.
- **Pricing:** assumed same per-prospect as the single endpoint (2 email-only / 5 both); not restated in the bulk doc.

**This is the right endpoint for email + mobile.** We already have prospect_ids in hand from the existing `/v1/prospects` call.

### `POST /v1/prospects/profiles/enrich` (single, paid — for richer LinkedIn data)

Per [the Professional profile doc](https://developers.explorium.ai/reference/prospects/enrichments/professional_profile_contact_and_workplace.md):

- **Method/path:** `POST /v1/prospects/profiles/enrich`
- **Request body:** `{"prospect_id": "<40-hex>"}`. No `parameters` needed for default behaviour.
- **Response:** plaintext-rich LinkedIn-derived profile data:
  - `linkedin` (URN) and `linkedin_url_array` (URLs)
  - `company_name`, `company_website`, `company_linkedin`
  - `job_title`, `job_department_main`, `job_level_main`
  - `experience[]` (work history with company, title, dates)
  - `education[]`
  - `skills[]`, `interests[]`
  - `full_name`
- **Cost:** **not documented**. The probe script will surface the actual cost via Explorium's response headers if available, otherwise via the credit-balance change on Michael's account.
- **No bulk variant.** If we want richer profile data on every prospect, we'd be hitting this endpoint once per prospect — at full monthly-scan volume that's 3,200 individual calls.

---

## 2. What our request currently does

### Filter construction

`build_prospect_filters()` in [scripts/vibe_prospecting_scan.py:209-227](../scripts/vibe_prospecting_scan.py#L209-L227) emits a body shaped like:

```json
{
  "mode": "full",
  "page": 1,
  "page_size": 100,
  "filters": {
    "country_code": {"values": ["ae", "sa", ...]},
    "business_id": {"values": ["<id1>", "<id2>", ...]},
    "job_department": {"values": ["human resources", "finance"]},
    "job_level": {"values": ["c-suite"]}
  }
}
```

`mode: "full"` is already being sent. We've confirmed against the docs that this does not change email visibility.

### Response field extraction

`normalise_result()` in [scripts/vibe_prospecting_scan.py:330-350](../scripts/vibe_prospecting_scan.py#L330-L350) tries — in order — these fields for plaintext:

```python
"email_plain": first(record.get("email"), record.get("work_email"), record.get("professional_email")),
"email_hashed": record.get("professional_email_hashed"),
```

**None of `email`, `work_email`, or `professional_email` are documented to be returned by `POST /v1/prospects`.** That's why `email_plain` is `(none)` on every row in dry-run output. The fallback `email_hashed` is correctly populated, but a hash is useless for outreach.

### Notion write

`write_intake_page()` writes `email_plain` (when truthy) into the Notion `Email` property. Since `email_plain` is never truthy, the property stays blank. The hash is appended to `Notes` for traceability.

---

## 3. Field names Explorium might return plaintext under

Per the docs we fetched (`/v1/prospects` and `/v1/prospects/contacts_information/enrich`):

| Field name | Where it lives | Plaintext? |
|---|---|---|
| `professional_email_hashed` | `/v1/prospects` response | **Hash only** |
| `professions_email` | enrichment endpoints | **Plaintext** |
| `professional_email_status` | enrichment endpoints | enum (valid/catch-all/invalid) |
| `emails[].address` | enrichment endpoints | **Plaintext** |
| `emails[].type` | enrichment endpoints | enum (personal/professional) |
| `email`, `work_email`, `verified_email`, `business_email`, `email_address`, `personal_email` (top-level) | (not documented anywhere) | — |

The current scan script's fallback list (`email`, `work_email`, `professional_email`) checks fields that the prospects endpoint **never returns**. Even if some live response under `mode: "full"` did include one of them, that would be undocumented behaviour — the fix should depend on the documented enrichment endpoint, not on field-name guesswork.

---

## 4. Hypothesis tree (ranked by probability)

### #1 — Plaintext is gated behind a separate enrichment endpoint we don't call. **CONFIRMED.**
The `/v1/prospects` endpoint is by design a hash-only endpoint. Plaintext emails come from `POST /v1/prospects/contacts_information/bulk_enrich`. Our scan script never calls it.
→ **Operator action:** code fix — add an enrichment step. Cost: 2 credits per prospect for email-only.

### #2 — Plan tier doesn't include email enrichment. **POSSIBLE, REQUIRES MICHAEL'S CONFIRMATION.**
The docs document the enrichment endpoint but don't enumerate which plan tiers include it. Michael's Explorium account either has enrichment credits or it doesn't. The single enrichment endpoint's published cost (2 credits / prospect for email-only) suggests credits are pay-per-call rather than tier-gated, but the only way to be sure is to look at the account.
→ **Operator action:** check Explorium dashboard — confirm the plan permits enrichment calls and there's a credit budget that covers ~6,400/month at the current monthly-scan volumes (see cost projection below).

### #3 — Wrong API parameter on the prospects call. **REJECTED.**
There is no `enrich_emails`, `include_pii`, `unmask_emails`, or similar parameter documented on `POST /v1/prospects`. We're not missing a flag; we're missing an entire endpoint call.

### #4 — Different field name on the prospects response. **REJECTED.**
Documented prospects schema only contains `professional_email_hashed`. Even if undocumented fields exist, relying on them would be brittle. The supported path is the enrichment endpoint.

### #5 — Explorium changed their API. **REJECTED.**
Both `/v1/prospects` and the enrichment endpoints are documented as currently active. The behaviour we observe matches the docs.

### #6 — Extraction logic is checking wrong fields. **PARTIALLY TRUE BUT INSUFFICIENT.**
The fallback list `email / work_email / professional_email` would never match the documented prospects response. Fixing the extraction without adding the enrichment call wouldn't help — the right fields aren't on the response in the first place.

---

## Cost projection for the current monthly scan

`scripts/run_monthly_scan.ps1` requests these limits across 7 ICP × region combos = 3,200 prospects/month total.

| Enrichment | Per prospect | Monthly cost (3,200 prospects) |
|---|---:|---:|
| Email only (`contact_types=["email"]`) | 2 credits | **6,400 credits/month** |
| Email + mobile (default `contact_types`) | 5 credits | **16,000 credits/month** |
| Richer LinkedIn profile (`/v1/prospects/profiles/enrich`) | unknown | **3,200 × ?** |

**LinkedIn URL only** is already captured for free on the basic prospects endpoint (`linkedin_url_array`). No additional credits needed if a URL is sufficient.

If Michael wants to throttle, three natural levers:
- Lower the per-ICP limits in `run_monthly_scan.ps1`.
- Skip enrichment for prospects that already have a Notion intake row with a plaintext email or mobile.
- Tier the enrichment — email + mobile for high-priority ICPs (A1, B1, B3), email-only for the rest, profile enrichment only for high-priority that pass scoring.

---

## 5. Proposed test — `scripts/explorium_email_probe.py`

A standalone diagnostic that fetches 3 prospects from the existing prospects endpoint, then exercises both enrichment endpoints (contact info + profile) on the same 3 IDs and prints all responses with PII redaction.

The script is at [scripts/explorium_email_probe.py](../scripts/explorium_email_probe.py) — **do not run it without Michael's go-ahead**. Cost per run:

- 3 × 5 credits = **15 credits** for the bulk contact enrichment (email + mobile)
- 3 × ? credits = **3 × profile-enrichment cost** for the profile endpoint

Usage when ready:
```powershell
.\venv\Scripts\python.exe scripts\explorium_email_probe.py --region gcc --icp A1
```

Output (in order):
- The first 3 prospect records as returned by `/v1/prospects` (showing `professional_email_hashed` and that no plaintext email/mobile is present)
- The matching enrichment block from `/v1/prospects/contacts_information/bulk_enrich` (plaintext `professions_email`, `mobile_phone`, `emails[]`, `phone_numbers[]` if the account/credits allow)
- The matching profile-enrichment block from `/v1/prospects/profiles/enrich` (LinkedIn URL list, company LinkedIn, experience, education, skills) for the first prospect only — to gauge whether richer profile data is worth the cost
- A side-by-side summary listing every email-shaped and phone-shaped value found, by field path

---

## 6. Recommended next step

> **Michael — three questions to answer:**
>
> 1. Does your Explorium account have enrichment credits enabled, and can it sustain the per-month cost of contact enrichment? At full monthly-scan volume that's 6,400/month for email-only or 16,000/month for email + mobile.
> 2. Do you want **mobile numbers** on every Vibe-sourced row (cost: 5 credits/prospect total) or just **email** (2 credits/prospect)?
> 3. Do you want the **richer LinkedIn profile** (experience, education, skills, company_linkedin) enriched too — or is the LinkedIn URL alone (already captured today) enough? The profile-enrichment cost is undocumented; the probe will surface it.
>
> Once decided:
> - Run `scripts/explorium_email_probe.py --region gcc --icp A1` once to confirm plaintext flows for the actual API key. Cost: ~15 credits + 3 × profile cost.
> - Then I'll wire `bulk_enrich` (and optionally `/profiles/enrich`) into `vibe_prospecting_scan.py` as a third step after the existing `/businesses` → `/prospects` flow. About 60-90 LOC depending on how much of the profile data you want surfaced into Notion. No new dependencies.
>
> If credits are constrained, levers in priority order:
> - Drop monthly-scan limits to fit the budget.
> - Only enrich a curated short-list (e.g., top-50 per ICP after scoring).
> - Skip mobile (email-only saves 60% on contact credits).
> - Skip profile enrichment entirely; rely on the free `linkedin_url_array` from the prospects endpoint.

No code changes to `vibe_prospecting_scan.py` are made in this commit. Implementation comes after the answers above.

---

## Files in this commit

- `docs/EXPLORIUM_EMAIL_INVESTIGATION.md` — this report
- `scripts/explorium_email_probe.py` — diagnostic script, **not run, not invoked from anywhere**

## References

- `https://developers.explorium.ai/reference/prospects/fetch_prospects.md` — prospects endpoint
- `https://developers.explorium.ai/reference/prospects/enrichments/contacts_information.md` — single contact (email + mobile) enrichment
- `https://developers.explorium.ai/reference/prospects/enrichments/bulk/prospects_contacts_information_bulk_enrich.md` — bulk contact (email + mobile) enrichment
- `https://developers.explorium.ai/reference/prospects/enrichments/professional_profile_contact_and_workplace.md` — LinkedIn profile enrichment
- `https://developers.explorium.ai/llms.txt` — full doc index
