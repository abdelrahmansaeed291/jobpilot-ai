-- JobPilot AI: persistent single-user candidate profile and private CV storage.
-- Run this file once in Supabase Dashboard > SQL Editor.

create table if not exists public.candidate_profiles (
    id uuid primary key,
    name text not null default '',
    email text not null default '',
    location text not null default '',
    professional_summary text not null default '',
    education jsonb not null default '[]'::jsonb
        check (jsonb_typeof(education) = 'array'),
    work_experience jsonb not null default '[]'::jsonb
        check (jsonb_typeof(work_experience) = 'array'),
    technical_skills jsonb not null default '[]'::jsonb
        check (jsonb_typeof(technical_skills) = 'array'),
    languages jsonb not null default '[]'::jsonb
        check (jsonb_typeof(languages) = 'array'),
    certifications jsonb not null default '[]'::jsonb
        check (jsonb_typeof(certifications) = 'array'),
    projects jsonb not null default '[]'::jsonb
        check (jsonb_typeof(projects) = 'array'),
    cv_file_path text,
    parsed_cv_text text not null default '',
    updated_at timestamptz not null default timezone('utc', now())
);

create or replace function public.set_jobpilot_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = timezone('utc', now());
    return new;
end;
$$;

drop trigger if exists candidate_profiles_set_updated_at
on public.candidate_profiles;

create trigger candidate_profiles_set_updated_at
before update on public.candidate_profiles
for each row execute function public.set_jobpilot_updated_at();

alter table public.candidate_profiles enable row level security;

-- The bucket is private. The local Streamlit server uses the service-role key,
-- which bypasses RLS. No anon/authenticated policies are intentionally created.
insert into storage.buckets (
    id,
    name,
    public,
    file_size_limit,
    allowed_mime_types
)
values (
    'candidate-cvs',
    'candidate-cvs',
    false,
    10485760,
    array['application/pdf']
)
on conflict (id) do update set
    public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;
