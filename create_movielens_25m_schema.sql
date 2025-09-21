-- =====================================================
-- Database Schema for MovieLens 25M Dataset
-- DiskANN and Apache AGE Demo
-- =====================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS age;

-- Load AGE extension
LOAD 'age';

-- Set search path to include AGE catalog
SET search_path = ag_catalog, "$user", public;

-- =====================================================
-- CORE TABLES
-- =====================================================

-- Movies table with rich metadata
CREATE TABLE IF NOT EXISTS movies (
    movie_id INTEGER PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    genres TEXT[],
    imdb_id VARCHAR(20) UNIQUE,
    tmdb_id INTEGER UNIQUE,
    embedding VECTOR(768),
    tsv_title TSVECTOR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    embedding VECTOR(768),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Ratings table
CREATE TABLE IF NOT EXISTS ratings (
    user_id INTEGER REFERENCES users(user_id),
    movie_id INTEGER REFERENCES movies(movie_id),
    rating NUMERIC(2,1) NOT NULL,
    timestamp BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, movie_id)
);

-- Tags table (user-applied tags)
CREATE TABLE IF NOT EXISTS tags (
    tag_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id),
    movie_id INTEGER REFERENCES movies(movie_id),
    tag VARCHAR(255) NOT NULL,
    timestamp BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Genome Tags table (vocabulary of tags for Tag Genome)
CREATE TABLE IF NOT EXISTS genome_tags (
    tag_id INTEGER PRIMARY KEY,
    tag VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Genome Scores table (relevance scores between movies and genome tags)
CREATE TABLE IF NOT EXISTS genome_scores (
    movie_id INTEGER REFERENCES movies(movie_id),
    tag_id INTEGER REFERENCES genome_tags(tag_id),
    relevance NUMERIC(5,4) NOT NULL,
    PRIMARY KEY (movie_id, tag_id)
);

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

-- Vector similarity indexes (HNSW for DiskANN)
CREATE INDEX IF NOT EXISTS idx_movies_embedding_hnsw 
ON movies USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_users_embedding_hnsw 
ON users USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- GIN Indexes for Genres array
CREATE INDEX IF NOT EXISTS idx_movies_genres_gin ON movies USING GIN (genres);

-- Text search indexes
CREATE INDEX IF NOT EXISTS idx_movies_tsv_title 
ON movies USING GIN (tsv_title);

-- Standard indexes for common queries
CREATE INDEX IF NOT EXISTS idx_ratings_user_id ON ratings(user_id);
CREATE INDEX IF NOT EXISTS idx_ratings_movie_id ON ratings(movie_id);
CREATE INDEX IF NOT EXISTS idx_ratings_rating ON ratings(rating);
CREATE INDEX IF NOT EXISTS idx_ratings_timestamp ON ratings(timestamp);

CREATE INDEX IF NOT EXISTS idx_tags_user_id ON tags(user_id);
CREATE INDEX IF NOT EXISTS idx_tags_movie_id ON tags(movie_id);
CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);

CREATE INDEX IF NOT EXISTS idx_genome_scores_movie_id ON genome_scores(movie_id);
CREATE INDEX IF NOT EXISTS idx_genome_scores_tag_id ON genome_scores(tag_id);

-- =====================================================
-- FUNCTIONS FOR DATA PROCESSING
-- =====================================================

-- Function to update text search vectors for movie titles
CREATE OR REPLACE FUNCTION update_movie_tsv_title() RETURNS TRIGGER AS $$
BEGIN
    NEW.tsv_title := to_tsvector('english', COALESCE(NEW.title, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically update text search vectors for movie titles
DROP TRIGGER IF EXISTS trigger_update_movie_tsv_title ON movies;
CREATE TRIGGER trigger_update_movie_tsv_title
    BEFORE INSERT OR UPDATE ON movies
    FOR EACH ROW EXECUTE FUNCTION update_movie_tsv_title();

-- =====================================================
-- APACHE AGE GRAPH SETUP
-- =====================================================

-- Create the graph (will be populated by separate script)
SELECT ag_catalog.create_graph('movielens_25m');

-- =====================================================
-- SAMPLE DATA VALIDATION QUERIES
-- =====================================================

-- Query to check table sizes after data load
CREATE OR REPLACE VIEW data_load_summary_25m AS
SELECT 
    'movies' as table_name, COUNT(*) as record_count FROM movies
UNION ALL
SELECT 'users' as table_name, COUNT(*) as record_count FROM users
UNION ALL
SELECT 'ratings' as table_name, COUNT(*) as record_count FROM ratings
UNION ALL
SELECT 'tags' as table_name, COUNT(*) as record_count FROM tags
UNION ALL
SELECT 'genome_tags' as table_name, COUNT(*) as record_count FROM genome_tags
UNION ALL
SELECT 'genome_scores' as table_name, COUNT(*) as record_count FROM genome_scores;

-- Query to check embedding coverage
CREATE OR REPLACE VIEW embedding_coverage_25m AS
SELECT 
    'movies' as entity_type,
    COUNT(*) as total_records,
    COUNT(embedding) as records_with_embeddings,
    ROUND(COUNT(embedding)::numeric / COUNT(*) * 100, 2) as embedding_coverage_pct
FROM movies
WHERE movie_id IS NOT NULL
UNION ALL
SELECT 
    'users' as entity_type,
    COUNT(*) as total_records,
    COUNT(embedding) as records_with_embeddings,
    ROUND(COUNT(embedding)::numeric / COUNT(*) * 100, 2) as embedding_coverage_pct
FROM users
WHERE user_id IS NOT NULL;

-- =====================================================
-- CLEANUP FUNCTIONS (FOR DEVELOPMENT)
-- =====================================================

-- Function to reset all data (use with caution)
CREATE OR REPLACE FUNCTION reset_all_data_25m()
RETURNS VOID AS $$
BEGIN
    -- Drop graph if exists
    BEGIN
        PERFORM ag_catalog.drop_graph('movielens_25m', true);
    EXCEPTION
        WHEN OTHERS THEN
            -- Graph doesn't exist, continue
            NULL;
    END;
    
    -- Clear all tables
    TRUNCATE TABLE genome_scores CASCADE;
    TRUNCATE TABLE genome_tags CASCADE;
    TRUNCATE TABLE tags CASCADE;
    TRUNCATE TABLE ratings CASCADE;
    TRUNCATE TABLE movies CASCADE;
    TRUNCATE TABLE users CASCADE;
    
    -- Recreate graph
    PERFORM ag_catalog.create_graph('movielens_25m');
    
    RAISE NOTICE 'All MovieLens 25M data has been reset. Tables are empty and graph is recreated.';
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- COMPLETION MESSAGE
-- =====================================================

DO $$
BEGIN
    RAISE NOTICE 'MovieLens 25M database schema created successfully!';
    RAISE NOTICE 'Tables created: movies, users, ratings, tags, genome_tags, genome_scores';
    RAISE NOTICE 'Indexes created for vector similarity, GIN for genres, and text search';
    RAISE NOTICE 'Views created for common query patterns';
    RAISE NOTICE 'Apache AGE graph "movielens_25m" created';
    RAISE NOTICE 'Ready for data loading!';
END $$;

