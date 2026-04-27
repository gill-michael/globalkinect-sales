# Explorium probe — results

**Run timestamp (UTC):** 2026-04-27T20:05:23Z
**Command:** `python scripts/explorium_email_probe.py --region gcc --icp A1`
**Decision:** Proceed to Task 2 — plaintext emails flow from `bulk_enrich`.

---

## Headline

`POST /v1/prospects/contacts_information/bulk_enrich` returns plaintext emails for our API key on the GCC × A1 sample. Mobile / phone fields came back **null** for every prospect in this sample. Richer LinkedIn profile data flows correctly from `POST /v1/prospects/profiles/enrich`.

---

## Endpoint summary

| Endpoint | Result | Notes |
|---|---|---|
| `POST /v1/prospects` | hashed only (`professional_email_hashed`) | as expected per docs |
| `POST /v1/prospects/contacts_information/bulk_enrich` | **plaintext emails returned** | `professions_email` + `emails[]` array with `address` + `type` |
| `POST /v1/prospects/profiles/enrich` | rich LinkedIn data returned | nested under `data.{...}`: experience, country, region, city, linkedin URL |

---

## Per-prospect findings

The sample was 3 prospects from the GCC region matching ICP A1 (Frustrated GCC Operator). Email format below is illustrative — actual addresses redacted.

### Prospect 1 (`prospect_id=34f48c69…`)
- **`/v1/prospects` response:** `professional_email_hashed: <hash>`, no plaintext fields.
- **`bulk_enrich` response:**
  - `professions_email: f**@***ple.com` (status: `valid`)
  - `emails[0]: f**@***ple.com (type: personal)`
  - `emails[1]: f**@***ple.com (type: personal)`
  - `emails[2]: f**@***ple.com (type: current)`
  - `mobile_phone: null`
  - `phone_numbers: null`
- **`/profiles/enrich` response:** full experience array (6 prior roles incl. CFO / Group CFO / SVP Finance), country, region, city, LinkedIn URL.

### Prospect 2 (`prospect_id=aaaaaa73…`)
- **`bulk_enrich` response:**
  - `professions_email: s**@***ple.com` (status: `valid`)
  - `emails[0]: s**@***ple.com (type: current)`
  - `emails[1]: s**@***ple.com (type: personal)`
  - `mobile_phone: null`
  - `phone_numbers: null`

### Prospect 3 (`prospect_id=74cccb14…`)
- **`bulk_enrich` response:**
  - `professions_email: b**@***ple.com` (status: `valid`)
  - `emails[0]: b**@***ple.com (type: current)`
  - `mobile_phone: null`
  - `phone_numbers: null`

---

## Field-presence matrix

| Field | `/v1/prospects` | `bulk_enrich` | `/profiles/enrich` |
|---|---|---|---|
| `professional_email_hashed` | ✅ all 3 | not returned | not returned |
| `professions_email` (plaintext) | not returned | ✅ all 3, all status `valid` | not returned |
| `emails[]` (plaintext array) | not returned | ✅ 1-3 per prospect | not returned |
| `mobile_phone` | not returned | **null on all 3** | not returned |
| `phone_numbers[]` | not returned | **null on all 3** | not returned |
| `linkedin_url_array` | ✅ all 3 (free) | not returned | ✅ via `data.linkedin` |
| `experience[]` | not returned | not returned | ✅ rich employment history |
| `education[]`, `skills[]`, `interests[]` | not returned | not returned | not surfaced in this sample (uncertain whether Explorium had data or whether the script's redaction obscured them) |

---

## Interpretation: why phone fields came back null

Three possible reasons, ranked by likelihood:

1. **Sample-specific.** Three GCC senior-finance leaders may simply not have public mobile numbers in Explorium's data set. With `n=3`, this is plausible. A larger probe might surface phone numbers for a fraction of records.
2. **Plan tier doesn't include phone enrichment.** Even though we sent `contact_types=["email", "phone"]`, the API may silently drop the phone request if the account isn't entitled. Email status came back successfully so the call wasn't rejected — but the phone bit may have been ignored.
3. **Phone enrichment costs more credits and the call short-circuits.** Less likely; the docs imply 5 credits covers both for entitled accounts.

**Out of scope this session.** The user's brief excludes mobile and LinkedIn-profile enrichment; the email-only path is what we need to wire. Mobile is a question for a future session (probably "spend a few credits on a larger probe to sample for phone presence").

---

## Credits consumed

The Explorium API did **not** surface credit consumption in any response we received (no header, no body field). What we sent:
- 1 × `/v1/businesses` query (paged through ~200 results, 2 pages × ~100 each — pricing per docs is preview mode, billing rate uncertain)
- 1 × `/v1/prospects` query for 3 results (full mode, free per the inspection diagnosis)
- 1 × `bulk_enrich` for 3 prospects with `contact_types=["email", "phone"]` — documented at **5 credits / prospect = 15 credits**
- 1 × `/profiles/enrich` for 1 prospect — undocumented cost

Estimated total this run: **~16-20 credits**. The actual figure is in Michael's Explorium dashboard.

---

## Decision

**Proceed to Task 2.** Plaintext emails confirmed flowing from `bulk_enrich`. Implementation can begin with `contact_types=["email"]` (cheaper at 2 credits / prospect) since:
- Email-only matches the user's stated scope this session
- Mobile came back null on every sample anyway
- Profile enrichment is explicitly out of scope

The bulk_enrich response shape consumed by `vibe_prospecting_scan.py` should be:
```python
response["data"]  # list of {prospect_id, data: {emails, professions_email, professional_email_status, ...}}
```
Each prospect's plaintext is at `data[i]["data"]["professions_email"]` (preferred) with `data[i]["data"]["emails"][0]["address"]` as a fallback. Status flag at `data[i]["data"]["professional_email_status"]` ∈ `{"valid", "catch-all", "invalid"}`.
