-- schema_migrations is created automatically by runner.py; do not declare here.
-- Seeds the policy-level contact suppression list (HubSpot ID + email + reason).
-- Idempotent: ON CONFLICT DO NOTHING on the unique hubspot_id index.
-- The SELECT-from-users subquery resolves Michael's UUID at apply time
-- (he is seeded by migration 0006, so he exists by the time 0009 runs).

INSERT INTO contact_suppressions (hubspot_id, email, reason, suppressed_by) VALUES (
    '756684767454',
    'tomgill@risecontracts.co.uk',
    'Personal contact — Michaels father; not a sales prospect',
    (SELECT id FROM users WHERE lower(email) = 'michael.gill@globalkinect.co.uk')
) ON CONFLICT (hubspot_id) DO NOTHING;

INSERT INTO contact_suppressions (hubspot_id, email, reason, suppressed_by) VALUES (
    '756684874987',
    'message@adobe.com',
    'Vendor noise — generic marketing address, not a sales prospect',
    (SELECT id FROM users WHERE lower(email) = 'michael.gill@globalkinect.co.uk')
) ON CONFLICT (hubspot_id) DO NOTHING;

INSERT INTO contact_suppressions (hubspot_id, email, reason, suppressed_by) VALUES (
    '756711564489',
    'annasobal75209@github.com',
    'GitHub auto-generated transactional alias — not a real outreach target',
    (SELECT id FROM users WHERE lower(email) = 'michael.gill@globalkinect.co.uk')
) ON CONFLICT (hubspot_id) DO NOTHING;

INSERT INTO contact_suppressions (hubspot_id, email, reason, suppressed_by) VALUES (
    '756691243195',
    'bh@hubspot.com',
    'HubSpot sample contact (Brian Halligan) — auto-created in every portal',
    (SELECT id FROM users WHERE lower(email) = 'michael.gill@globalkinect.co.uk')
) ON CONFLICT (hubspot_id) DO NOTHING;

INSERT INTO contact_suppressions (hubspot_id, email, reason, suppressed_by) VALUES (
    '756698566847',
    'bingwb@microsoft.com',
    'Vendor noise — Bing Webmaster Tools transactional address',
    (SELECT id FROM users WHERE lower(email) = 'michael.gill@globalkinect.co.uk')
) ON CONFLICT (hubspot_id) DO NOTHING;

INSERT INTO contact_suppressions (hubspot_id, email, reason, suppressed_by) VALUES (
    '756690252006',
    'emailmaria@hubspot.com',
    'HubSpot sample contact (Maria Johnson) — auto-created in every portal',
    (SELECT id FROM users WHERE lower(email) = 'michael.gill@globalkinect.co.uk')
) ON CONFLICT (hubspot_id) DO NOTHING;

INSERT INTO contact_suppressions (hubspot_id, email, reason, suppressed_by) VALUES (
    '756709400815',
    'googlecloud@google.com',
    'Vendor noise — Google Cloud transactional address',
    (SELECT id FROM users WHERE lower(email) = 'michael.gill@globalkinect.co.uk')
) ON CONFLICT (hubspot_id) DO NOTHING;

INSERT INTO contact_suppressions (hubspot_id, email, reason, suppressed_by) VALUES (
    '756711515364',
    'onboarding@resend.dev',
    'Vendor noise — Resend onboarding transactional email',
    (SELECT id FROM users WHERE lower(email) = 'michael.gill@globalkinect.co.uk')
) ON CONFLICT (hubspot_id) DO NOTHING;

INSERT INTO contact_suppressions (hubspot_id, email, reason, suppressed_by) VALUES (
    '756709632241',
    'receipts+acct_16lx2yge9hkvlnum@stripe.com',
    'Vendor noise — Stripe receipts transactional address',
    (SELECT id FROM users WHERE lower(email) = 'michael.gill@globalkinect.co.uk')
) ON CONFLICT (hubspot_id) DO NOTHING;
