-- Migration: Add prefecture and city columns to subjects table
-- Date: 2025-12-03
-- Purpose: Add location information (prefecture and city) to observation subjects
--
-- Background:
-- - iOS app displays a map with the subject's location
-- - Currently "横浜市" is hardcoded in SubjectTabView.swift
-- - This migration adds prefecture and city columns to store actual location data
--
-- Usage:
-- - prefecture: 都道府県 (e.g., "神奈川県", "東京都")
-- - city: 市区町村 (e.g., "横浜市", "渋谷区")
--
-- Notes:
-- - Both columns are optional (NULL allowed)
-- - Initially focused on Japan (47 prefectures)
-- - Can be extended to support international locations in the future

-- Step 1: Add prefecture column
ALTER TABLE public.subjects
ADD COLUMN prefecture TEXT;

-- Step 2: Add city column
ALTER TABLE public.subjects
ADD COLUMN city TEXT;

-- Step 3: Add comment for documentation
COMMENT ON COLUMN public.subjects.prefecture IS 'Prefecture or state (e.g., "神奈川県", "東京都")';
COMMENT ON COLUMN public.subjects.city IS 'City or municipality (e.g., "横浜市", "渋谷区")';
