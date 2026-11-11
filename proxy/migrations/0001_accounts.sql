create table users (
  id uuid primary key default gen_random_uuid(),
  google_sub text not null unique,
  email text not null,
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  daily_limit integer,
  disabled boolean not null default false,
  contribute_opt_in boolean not null default false,
  consent_version text,
  consent_at timestamptz
);

-- One row per extraction attempt. Metadata only: no image, page title or URL.
create table usage_events (
  id bigint generated always as identity primary key,
  user_id uuid references users (id) on delete set null,
  caller text not null,
  created_at timestamptz not null default now(),
  status text not null,
  model text,
  latency_ms integer,
  prompt_tokens integer,
  output_tokens integer,
  thought_tokens integer,
  event_count integer
);

create index usage_events_created_at on usage_events (created_at);
create index usage_events_user_created on usage_events (user_id, created_at);
