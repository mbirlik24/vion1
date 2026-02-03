-- ============================================
-- SEED TEST USER
-- ============================================
-- Run this AFTER creating the test user in Supabase Dashboard:
-- Authentication > Users > Add User
-- Email: admin@test.com
-- Password: test123456

-- Update test user with 1,000,000 credits
update public.profiles
set 
  credit_balance = 1000000,
  is_test_user = true
where email = 'admin@test.com';

-- Log the bonus transaction
insert into public.transactions (user_id, amount, credits_added, transaction_type, description)
select 
  id,
  0,
  1000000,
  'bonus',
  'Initial test credits'
from public.profiles
where email = 'admin@test.com';

-- Verify
select 
  id,
  email,
  credit_balance,
  is_test_user
from public.profiles
where email = 'admin@test.com';
