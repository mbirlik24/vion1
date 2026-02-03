-- ============================================
-- CHATOW DATABASE SCHEMA
-- ============================================
-- Run this in Supabase SQL Editor

-- ============================================
-- 1. PROFILES TABLOSU (User Profiles)
-- ============================================
create table public.profiles (
  id uuid references auth.users on delete cascade primary key,
  email text,
  credit_balance float default 0,
  is_test_user boolean default false,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

-- Enable RLS
alter table public.profiles enable row level security;

-- Users can view own profile
create policy "Users can view own profile"
  on public.profiles for select
  using ((select auth.uid()) = id);

-- Users can update own profile
create policy "Users can update own profile"
  on public.profiles for update
  using ((select auth.uid()) = id);

-- Service role has full access (for backend)
create policy "Service role has full access"
  on public.profiles for all
  using (auth.role() = 'service_role');

-- ============================================
-- 2. CHAT_SESSIONS TABLOSU (Chat Sessions)
-- ============================================
create table public.chat_sessions (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references public.profiles(id) on delete cascade not null,
  title text default 'New Chat',
  summary text,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

-- Enable RLS
alter table public.chat_sessions enable row level security;

-- Users can view own sessions
create policy "Users can view own sessions"
  on public.chat_sessions for select
  using ((select auth.uid()) = user_id);

-- Users can create own sessions
create policy "Users can create own sessions"
  on public.chat_sessions for insert
  with check ((select auth.uid()) = user_id);

-- Users can update own sessions
create policy "Users can update own sessions"
  on public.chat_sessions for update
  using ((select auth.uid()) = user_id);

-- Users can delete own sessions
create policy "Users can delete own sessions"
  on public.chat_sessions for delete
  using ((select auth.uid()) = user_id);

-- ============================================
-- 3. CHAT_MESSAGES TABLOSU (Messages)
-- ============================================
create table public.chat_messages (
  id uuid default gen_random_uuid() primary key,
  session_id uuid references public.chat_sessions(id) on delete cascade not null,
  role text not null check (role in ('user', 'assistant', 'system')),
  content text not null,
  model_used text,
  credits_used float default 0,
  created_at timestamp with time zone default now()
);

-- Enable RLS
alter table public.chat_messages enable row level security;

-- Users can view own messages (through session)
create policy "Users can view own messages"
  on public.chat_messages for select
  using (
    session_id in (
      select id from public.chat_sessions
      where user_id = (select auth.uid())
    )
  );

-- Users can insert messages to own sessions
create policy "Users can insert own messages"
  on public.chat_messages for insert
  with check (
    session_id in (
      select id from public.chat_sessions
      where user_id = (select auth.uid())
    )
  );

-- ============================================
-- 4. TRANSACTIONS TABLOSU (Credit Transactions)
-- ============================================
create table public.transactions (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references public.profiles(id) on delete cascade not null,
  amount float not null,
  credits_added float not null,
  transaction_type text not null check (transaction_type in ('purchase', 'usage', 'bonus')),
  lemon_squeezy_order_id text,
  description text,
  created_at timestamp with time zone default now()
);

-- Enable RLS
alter table public.transactions enable row level security;

-- Users can view own transactions
create policy "Users can view own transactions"
  on public.transactions for select
  using ((select auth.uid()) = user_id);

-- ============================================
-- 5. TRIGGER: Auto-create profile on signup
-- ============================================
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
  insert into public.profiles (id, email, credit_balance, is_test_user)
  values (
    new.id,
    new.email,
    0,
    false
  );
  return new;
end;
$$;

-- Create trigger
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- ============================================
-- 6. Enable Realtime for profiles (credit updates)
-- ============================================
alter publication supabase_realtime add table public.profiles;

-- ============================================
-- 7. Indexes for performance
-- ============================================
create index idx_chat_sessions_user_id on public.chat_sessions(user_id);
create index idx_chat_sessions_updated_at on public.chat_sessions(updated_at desc);
create index idx_chat_messages_session_id on public.chat_messages(session_id);
create index idx_chat_messages_created_at on public.chat_messages(created_at);
create index idx_transactions_user_id on public.transactions(user_id);
create index idx_profiles_email on public.profiles(email);
