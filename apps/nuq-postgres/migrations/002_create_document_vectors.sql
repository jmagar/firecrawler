-- Migration: Create document_vectors table for vector storage
-- This table stores document embeddings separately from the queue

-- Ensure pgvector extension is enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the document_vectors table
CREATE TABLE IF NOT EXISTS nuq.document_vectors (
  job_id VARCHAR(255) PRIMARY KEY,
  content_vector vector(1024),
  metadata JSONB,
  content TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for efficient similarity search
CREATE INDEX IF NOT EXISTS idx_document_vectors_similarity 
ON nuq.document_vectors 
USING hnsw (content_vector vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Create index for metadata queries
CREATE INDEX IF NOT EXISTS idx_document_vectors_metadata 
ON nuq.document_vectors 
USING gin (metadata);

-- Create index for timestamp-based queries
CREATE INDEX IF NOT EXISTS idx_document_vectors_created_at
ON nuq.document_vectors
USING btree (created_at DESC);

-- Create composite index for common query patterns
CREATE INDEX IF NOT EXISTS idx_document_vectors_domain_type
ON nuq.document_vectors
USING btree ((metadata->>'domain'), (metadata->>'content_type'));

-- Grant necessary permissions
GRANT ALL ON nuq.document_vectors TO postgres;