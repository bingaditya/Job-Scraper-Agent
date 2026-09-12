-- Resume version history for the multi-user resume upload/tailoring feature.
-- Run this once in the Supabase SQL editor for your project.

create table if not exists public.resume_versions (
  id                   uuid primary key default gen_random_uuid(),
  user_id              uuid not null references auth.users(id) on delete cascade,
  version_number       int not null,
  is_current           boolean not null default false,
  source               text not null check (source in ('upload', 'ai_tailored')),
  parent_version_id    uuid references public.resume_versions(id),
  storage_path         text not null,
  original_filename    text not null,
  file_size_bytes      int not null,
  mime_type            text not null default
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  job_title            text,
  job_description      text,
  job_id                text,
  tailoring_mode       text check (tailoring_mode in ('groq', 'rules')),
  tailoring_summary    text,
  keywords_emphasized  text[],
  missing_keywords     text[],
  fit_score            int,
  created_at           timestamptz not null default now(),
  unique (user_id, version_number)
);

-- At most one "current" version per user.
create unique index if not exists ux_resume_versions_current_per_user
  on public.resume_versions (user_id)
  where is_current;

create index if not exists ix_resume_versions_user_created
  on public.resume_versions (user_id, created_at desc);

alter table public.resume_versions enable row level security;

create policy resume_versions_owner_all on public.resume_versions
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Private storage bucket for the actual .docx bytes.
insert into storage.buckets (id, name, public)
values ('resumes', 'resumes', false)
on conflict (id) do nothing;

create policy resumes_owner_rw on storage.objects
  for all
  using (
    bucket_id = 'resumes'
    and (storage.foldername(name))[1] = auth.uid()::text
  )
  with check (
    bucket_id = 'resumes'
    and (storage.foldername(name))[1] = auth.uid()::text
  );
