-- JobPilot AI: persistent extra candidate information and job preferences.
-- Run once in Supabase Dashboard > SQL Editor after migration 001.

create table if not exists public.candidate_extra_information (
    id uuid primary key,
    skills jsonb not null default '[]'::jsonb check (jsonb_typeof(skills) = 'array'),
    additional_experience jsonb not null default '[]'::jsonb
        check (jsonb_typeof(additional_experience) = 'array'),
    projects jsonb not null default '[]'::jsonb check (jsonb_typeof(projects) = 'array'),
    certifications jsonb not null default '[]'::jsonb
        check (jsonb_typeof(certifications) = 'array'),
    other_information text not null default '',
    updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.job_preferences (
    id uuid primary key,
    target_job_titles jsonb not null default '[]'::jsonb,
    preferred_locations jsonb not null default '[]'::jsonb,
    country text not null default '',
    work_modes jsonb not null default '[]'::jsonb,
    employment_types jsonb not null default '[]'::jsonb,
    minimum_match_score integer not null default 70
        check (minimum_match_score between 0 and 100),
    preferred_industries jsonb not null default '[]'::jsonb,
    excluded_industries jsonb not null default '[]'::jsonb,
    preferred_companies jsonb not null default '[]'::jsonb,
    excluded_companies jsonb not null default '[]'::jsonb,
    language_requirements jsonb not null default '[]'::jsonb,
    maximum_required_experience numeric not null default 5
        check (maximum_required_experience between 0 and 50),
    search_recency text not null default '7 days'
        check (search_recency in ('24 hours', '3 days', '7 days')),
    updated_at timestamptz not null default timezone('utc', now())
);

drop trigger if exists candidate_extra_information_set_updated_at
on public.candidate_extra_information;
create trigger candidate_extra_information_set_updated_at
before update on public.candidate_extra_information
for each row execute function public.set_jobpilot_updated_at();

drop trigger if exists job_preferences_set_updated_at
on public.job_preferences;
create trigger job_preferences_set_updated_at
before update on public.job_preferences
for each row execute function public.set_jobpilot_updated_at();

alter table public.candidate_extra_information enable row level security;
alter table public.job_preferences enable row level security;

-- No public policies: the personal Streamlit server uses its secret/service-role key.
