-- Per-user candidate profile extracted from their uploaded resume, used to
-- personalize job matching. Run this once in the Supabase SQL editor.

create table if not exists public.candidate_profiles (
  user_id            uuid primary key references auth.users(id) on delete cascade,
  skills             text[] not null default '{}',
  preferred_titles   text[] not null default '{}',
  experience_years   int,
  summary            text,
  source_version_id  uuid references public.resume_versions(id),
  extraction_mode    text check (extraction_mode in ('groq', 'rules')),
  updated_at         timestamptz not null default now()
);

alter table public.candidate_profiles enable row level security;

create policy candidate_profiles_owner_all on public.candidate_profiles
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
