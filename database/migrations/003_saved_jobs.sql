-- JobPilot AI: persistent saved jobs from public discovery results.
-- Run once in Supabase Dashboard > SQL Editor after migrations 001 and 002.

create table if not exists public.saved_jobs (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    company text not null default 'Not specified',
    location text not null default 'Not specified',
    source text not null,
    url text not null unique,
    description text not null default '',
    posted_date text not null default 'Not specified',
    match_score numeric not null check (match_score between 0 and 100),
    match_explanation text not null default '',
    job_profile jsonb not null default '{}'::jsonb
        check (jsonb_typeof(job_profile) = 'object'),
    match_result jsonb not null default '{}'::jsonb
        check (jsonb_typeof(match_result) = 'object'),
    saved_at timestamptz not null default timezone('utc', now())
);

create index if not exists saved_jobs_match_score_idx
on public.saved_jobs (match_score desc);

alter table public.saved_jobs enable row level security;

-- No public policies: this personal Streamlit server uses its service-role key.
