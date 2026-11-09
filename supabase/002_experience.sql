-- Migration 002: store the experience label (Fresh graduates OK / Needs 2+ years / ...).
-- Run once in the Supabase SQL Editor. Safe to re-run.

alter table jobfinder.postings add column if not exists experience text not null default '';

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

create or replace view jobfinder.hidden as
select id, platform, platform_id, title, company, url, location, area, address, salary, work_type,
       left(description, 3000) as description, posted_at, posted_precision, roles, resume,
       emails, phones, dedupe_key, first_seen, hidden_reason, '[]'::jsonb as also_on, experience
from jobfinder.postings
where is_active and hidden_reason is not null
  and hidden_reason in ('male only / male preferred', 'senior / too much experience required', 'overseas', 'internship')
  and posted_at > now() - interval '15 days';

notify pgrst, 'reload schema';
