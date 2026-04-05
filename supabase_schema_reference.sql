create extension if not exists pgcrypto;

create table if not exists leads (
    id uuid primary key default gen_random_uuid(),
    lead_reference text,
    company_name text not null,
    contact_name text not null,
    contact_role text not null,
    email text,
    linkedin_url text,
    company_country text,
    target_country text,
    lead_type text,
    fit_reason text,
    status text not null default 'new',
    score integer,
    priority text,
    recommended_angle text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_leads_lead_reference on leads (lead_reference);

create table if not exists outreach_messages (
    id uuid primary key default gen_random_uuid(),
    lead_reference text not null,
    company_name text not null,
    contact_name text not null,
    contact_role text not null,
    lead_type text not null,
    target_country text not null,
    sales_motion text,
    primary_module text,
    bundle_label text,
    linkedin_message text not null,
    email_subject text not null,
    email_message text not null,
    follow_up_message text not null,
    created_at timestamptz not null default now()
);

create index if not exists idx_outreach_messages_lead_reference
    on outreach_messages (lead_reference);

create table if not exists solution_recommendations (
    id uuid primary key default gen_random_uuid(),
    lead_reference text not null,
    company_name text not null,
    contact_name text not null,
    target_country text not null,
    sales_motion text not null,
    recommended_modules text[] not null,
    primary_module text not null,
    bundle_label text not null,
    commercial_strategy text not null,
    rationale text not null,
    created_at timestamptz not null default now(),
    constraint uq_solution_recommendations_lead_reference unique (lead_reference)
);

create index if not exists idx_solution_recommendations_lead_reference
    on solution_recommendations (lead_reference);

create table if not exists pipeline_records (
    id uuid primary key default gen_random_uuid(),
    lead_reference text not null,
    company_name text not null,
    contact_name text not null,
    lead_type text not null,
    target_country text not null,
    score integer not null,
    priority text not null,
    sales_motion text,
    primary_module text,
    bundle_label text,
    recommended_modules text[],
    stage text not null,
    outreach_status text not null,
    created_at timestamptz not null default now(),
    last_updated_at timestamptz not null default now(),
    last_outreach_at timestamptz,
    last_response_at timestamptz,
    last_contacted timestamptz,
    next_action text,
    notes text,
    constraint uq_pipeline_records_lead_reference unique (lead_reference)
);

create index if not exists idx_pipeline_records_lead_reference
    on pipeline_records (lead_reference);
create index if not exists idx_pipeline_records_stage
    on pipeline_records (stage);
create index if not exists idx_pipeline_records_priority
    on pipeline_records (priority);
create index if not exists idx_pipeline_records_bundle_label
    on pipeline_records (bundle_label);

create table if not exists deal_support_packages (
    id uuid primary key default gen_random_uuid(),
    lead_reference text not null,
    company_name text not null,
    contact_name text not null,
    lead_type text not null,
    target_country text not null,
    sales_motion text,
    primary_module text,
    bundle_label text,
    recommended_modules text[],
    stage text not null,
    call_prep_summary text not null,
    recap_email_subject text not null,
    recap_email_body text not null,
    proposal_summary text not null,
    next_steps_message text not null,
    objection_response text not null,
    created_at timestamptz not null default now()
);

create index if not exists idx_deal_support_packages_lead_reference
    on deal_support_packages (lead_reference);

create table if not exists execution_tasks (
    id uuid primary key default gen_random_uuid(),
    lead_reference text not null,
    task_type text not null,
    description text not null,
    priority text not null,
    due_in_days integer not null,
    status text not null default 'open',
    created_at timestamptz not null default now()
);

create index if not exists idx_execution_tasks_lead_reference
    on execution_tasks (lead_reference);
create index if not exists idx_execution_tasks_priority
    on execution_tasks (priority);
