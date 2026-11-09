-- Jobs for My Love: database objects, all inside their own schema `jobfinder`.
-- Nothing here touches the existing public / JARVIS tables.
-- Safe to re-run (idempotent).  Undo everything with:  drop schema jobfinder cascade;

create schema if not exists jobfinder;

-- ------------------------------------------------------------------------------------
-- One row per job per platform.
-- ------------------------------------------------------------------------------------
create table if not exists jobfinder.postings (
  id               text primary key,                 -- 'jobstreet:95781624'
  platform         text not null,
  platform_id      text not null,
  title            text not null,
  company          text not null default '',
  url              text not null,
  location         text not null default '',
  area             text not null default '',
  address          text not null default '',
  salary           text not null default '',
  work_type        text not null default '',
  company_url      text not null default '',
  description      text not null default '',
  has_description  boolean generated always as (length(description) > 200) stored,
  posted_at        timestamptz,
  posted_precision text not null default 'exact' check (posted_precision in ('exact', 'hour', 'date')),
  roles            text[] not null default '{}',
  resume           text not null default '',
  emails           text[] not null default '{}',
  phones           text[] not null default '{}',
  hidden_reason    text,                             -- null = shown
  experience       text not null default '',          -- 'Fresh graduates OK' / 'Needs 2+ years' / ...
  dedupe_key       text not null,
  first_seen       timestamptz not null default now(),
  last_seen        timestamptz not null default now(),
  is_active        boolean not null default true,
  updated_at       timestamptz not null default now()
);
create index if not exists postings_feed_idx   on jobfinder.postings (is_active, posted_at desc) where hidden_reason is null;
create index if not exists postings_dedupe_idx on jobfinder.postings (dedupe_key);
create index if not exists postings_platform_idx on jobfinder.postings (platform, last_seen);

-- ------------------------------------------------------------------------------------
-- Her Saved / Applied marks. Keyed by dedupe_key so a mark survives when the same job
-- shows up on another platform.
-- ------------------------------------------------------------------------------------
create table if not exists jobfinder.job_status (
  dedupe_key  text primary key,
  saved       boolean not null default false,
  applied     boolean not null default false,
  applied_at  timestamptz,
  note        text not null default '',
  updated_at  timestamptz not null default now()
);

-- ------------------------------------------------------------------------------------
-- One row per source per scraper run (freshness + health on the website).
-- ------------------------------------------------------------------------------------
create table if not exists jobfinder.scrape_runs (
  id          bigint generated always as identity primary key,
  source      text not null,
  mode        text not null check (mode in ('quick', 'full')),
  started_at  timestamptz not null default now(),
  finished_at timestamptz,
  fetched     int not null default 0,
  new_count   int not null default 0,
  ok          boolean,
  error       text not null default ''
);
create index if not exists scrape_runs_source_idx on jobfinder.scrape_runs (source, started_at desc);

-- ------------------------------------------------------------------------------------
-- Small key/value store: roles → resume, areas, extra links (written by the scraper).
-- ------------------------------------------------------------------------------------
create table if not exists jobfinder.meta (
  key        text primary key,
  value      jsonb not null,
  updated_at timestamptz not null default now()
);

-- ------------------------------------------------------------------------------------
-- What the website shows: visible, active jobs from the last 15 days, one row per
-- dedupe_key (main copy: JobStreet > Kalibrr > Indeed > LinkedIn), other copies as also_on.
-- ------------------------------------------------------------------------------------
create or replace view jobfinder.feed with (security_invoker = true) as
with vis as (
  select p.*,
         row_number() over (
           partition by p.dedupe_key
           order by case p.platform when 'JobStreet' then 0 when 'Kalibrr' then 1
                                     when 'Indeed' then 2 when 'LinkedIn' then 3 else 9 end,
                    p.posted_at desc nulls last
         ) as rn
  from jobfinder.postings p
  where p.is_active and p.hidden_reason is null
    and p.posted_at > now() - interval '15 days'
)
select m.id, m.platform, m.platform_id, m.title, m.company, m.url, m.location, m.area, m.address,
       m.salary, m.work_type, m.company_url, left(m.description, 6000) as description,
       m.posted_at, m.posted_precision, m.roles, m.resume, m.emails, m.phones, m.dedupe_key,
       m.first_seen,
       coalesce((select jsonb_agg(jsonb_build_object('platform', o.platform, 'url', o.url))
                 from vis o where o.dedupe_key = m.dedupe_key and o.rn > 1), '[]'::jsonb) as also_on,
       m.experience
from vis m
where m.rn = 1;

-- Jobs removed for her (male only / preferred, senior, overseas): shown in the "Hidden" tab.
create or replace view jobfinder.hidden as
select id, platform, platform_id, title, company, url, location, area, address, salary, work_type,
       left(description, 3000) as description, posted_at, posted_precision, roles, resume,
       emails, phones, dedupe_key, first_seen, hidden_reason, '[]'::jsonb as also_on, experience
from jobfinder.postings
where is_active and hidden_reason is not null
  and hidden_reason in ('male only / male preferred', 'senior / too much experience required', 'overseas', 'internship')
  and posted_at > now() - interval '15 days';

-- Count of hidden jobs by reason (for "N hidden" on the website).
create or replace view jobfinder.hidden_counts as
select hidden_reason, count(*)::int as n
from jobfinder.postings
where is_active and hidden_reason is not null and posted_at > now() - interval '15 days'
group by hidden_reason;

-- Latest run per source (for "Updated 12 min ago · JobStreet ✓").
create or replace view jobfinder.source_status as
select distinct on (source) source, mode, started_at, finished_at, fetched, new_count, ok, error,
       (select max(r2.finished_at) from jobfinder.scrape_runs r2
         where r2.source = r.source and r2.ok) as last_ok_at
from jobfinder.scrape_runs r
order by source, started_at desc;

-- ------------------------------------------------------------------------------------
-- Security: same convention as the rest of this project: RLS on, no policies.
-- Only the service-role key (scraper + website API, both server-side) can read or write.
-- ------------------------------------------------------------------------------------
alter table jobfinder.postings    enable row level security;
alter table jobfinder.job_status  enable row level security;
alter table jobfinder.scrape_runs enable row level security;
alter table jobfinder.meta        enable row level security;

revoke all on schema jobfinder from anon, authenticated;
grant usage on schema jobfinder to service_role;
grant all on all tables in schema jobfinder to service_role;
grant all on all sequences in schema jobfinder to service_role;
alter default privileges in schema jobfinder grant all on tables to service_role;
alter default privileges in schema jobfinder grant all on sequences to service_role;
