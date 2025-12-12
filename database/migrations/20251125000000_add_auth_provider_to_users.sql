-- Migration: Add auth_provider column to public.users table
-- Date: 2025-11-25
-- Purpose: Track authentication provider (anonymous, email, google, apple, microsoft, etc.)
--
-- Background:
-- - Supabase manages authentication in auth.users and auth.identities tables
-- - However, we use public.users for application-level user profiles
-- - This migration adds auth_provider to track which authentication method the user used
--
-- Future scalability:
-- - Supports multiple OAuth providers (Google, Apple, Microsoft, GitHub, etc.)
-- - CHECK constraint ensures only valid providers are stored
-- - Easy to extend by modifying CHECK constraint

-- Step 1: Add auth_provider column (TEXT with CHECK constraint)
ALTER TABLE public.users
ADD COLUMN auth_provider TEXT DEFAULT 'email';

-- Step 2: Add CHECK constraint for valid providers
ALTER TABLE public.users
ADD CONSTRAINT users_auth_provider_check
CHECK (
  auth_provider IN (
    'anonymous',  -- Anonymous authentication
    'email',      -- Email/password authentication
    'google',     -- Google OAuth
    'apple',      -- Apple Sign In
    'microsoft',  -- Microsoft OAuth
    'github',     -- GitHub OAuth
    'facebook',   -- Facebook OAuth
    'twitter'     -- Twitter OAuth
  )
);

-- Step 3: Create index for faster queries by auth_provider
CREATE INDEX idx_users_auth_provider ON public.users(auth_provider);

-- Step 4: Update existing records based on email patterns
-- Anonymous users: email = 'anonymous'
UPDATE public.users
SET auth_provider = 'anonymous'
WHERE email = 'anonymous';

-- All other existing users are assumed to be email/password users
-- (This is safe because Google OAuth was just added and hasn't been used yet)
UPDATE public.users
SET auth_provider = 'email'
WHERE email != 'anonymous' AND auth_provider IS NULL;

-- Step 5: Make auth_provider NOT NULL after setting defaults
ALTER TABLE public.users
ALTER COLUMN auth_provider SET NOT NULL;

-- Step 6: Add comment for documentation
COMMENT ON COLUMN public.users.auth_provider IS 'Authentication provider: anonymous, email, google, apple, microsoft, github, facebook, twitter';

-- ============================================================================
-- Rollback Instructions (if needed)
-- ============================================================================
-- To rollback this migration:
--
-- DROP INDEX IF EXISTS idx_users_auth_provider;
-- ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_auth_provider_check;
-- ALTER TABLE public.users DROP COLUMN IF EXISTS auth_provider;
