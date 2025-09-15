-- Migration: Add pgvector support to nuq.queue_scrape table
-- This migration adds vector storage capabilities while preserving existing functionality

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add vector columns to the existing queue_scrape table
-- Using vector(1024) for embeddings dimension as specified in requirements
ALTER TABLE nuq.queue_scrape 
ADD COLUMN IF NOT EXISTS content_vector vector(1024),
ADD COLUMN IF NOT EXISTS title text,
ADD COLUMN IF NOT EXISTS domain text,
ADD COLUMN IF NOT EXISTS repository_name text,
ADD COLUMN IF NOT EXISTS repository_org text,
ADD COLUMN IF NOT EXISTS content_type text,
ADD COLUMN IF NOT EXISTS file_path text;

-- Add indexes for vector similarity search using HNSW algorithm
-- Using cosine distance as specified in the architecture docs
CREATE INDEX IF NOT EXISTS queue_scrape_content_vector_cosine_idx 
ON nuq.queue_scrape USING hnsw (content_vector vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Add indexes for metadata filtering to support search queries
CREATE INDEX IF NOT EXISTS queue_scrape_domain_idx ON nuq.queue_scrape USING btree (domain);
CREATE INDEX IF NOT EXISTS queue_scrape_repository_org_idx ON nuq.queue_scrape USING btree (repository_org);
CREATE INDEX IF NOT EXISTS queue_scrape_repository_name_idx ON nuq.queue_scrape USING btree (repository_name);
CREATE INDEX IF NOT EXISTS queue_scrape_content_type_idx ON nuq.queue_scrape USING btree (content_type);

-- Add composite index for common filtering scenarios
CREATE INDEX IF NOT EXISTS queue_scrape_repo_composite_idx 
ON nuq.queue_scrape USING btree (repository_org, repository_name, content_type);

-- Add index for completed jobs with vectors for search queries
CREATE INDEX IF NOT EXISTS queue_scrape_completed_vectors_idx 
ON nuq.queue_scrape USING btree (status, finished_at) 
WHERE (status = 'completed'::nuq.job_status AND content_vector IS NOT NULL);