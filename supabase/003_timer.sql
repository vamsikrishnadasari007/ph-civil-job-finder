-- Migration 003: reliable 30-minute trigger (GitHub's own cron skips runs on new repos).
-- Supabase's pg_cron calls the website's /api/tick, which starts the GitHub scrape workflow.
-- Replace __CRON_SECRET__ with the CRON_SECRET value (the filled-in copy is 003_timer.local.sql,
-- which is gitignored). Safe to re-run.  Undo:  select cron.unschedule('jobfinder-quick');
--                                              select cron.unschedule('jobfinder-full');

create extension if not exists pg_cron;
create extension if not exists pg_net;

-- Keep the secret in Supabase Vault, not in the job definition.
delete from vault.secrets where name = 'jobfinder_cron_secret';
select vault.create_secret('__CRON_SECRET__', 'jobfinder_cron_secret');

create or replace function jobfinder.tick(mode text default 'quick') returns bigint
language sql security definer set search_path = '' as $$
  select net.http_post(
    url     := 'https://ph-civil-job-finder.vercel.app/api/tick?mode=' || mode,
    headers := jsonb_build_object(
                 'Content-Type', 'application/json',
                 'Authorization', 'Bearer ' || (select decrypted_secret from vault.decrypted_secrets
                                                where name = 'jobfinder_cron_secret')),
    body    := '{}'::jsonb
  );
$$;
revoke all on function jobfinder.tick(text) from public, anon, authenticated;

-- Every 30 minutes (quick: only new postings) and nightly at 2:17 AM Manila (full sweep).
select cron.schedule('jobfinder-quick', '7,37 * * * *', $$select jobfinder.tick('quick')$$);
select cron.schedule('jobfinder-full',  '17 18 * * *',  $$select jobfinder.tick('full')$$);

-- Check it:  select jobname, schedule, active from cron.job where jobname like 'jobfinder%';
--            select status, return_message, start_time from cron.job_run_details
--              order by start_time desc limit 5;
