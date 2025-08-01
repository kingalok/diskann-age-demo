-- =====================================================
-- Database Schema Creation for DiskANN and Apache AGE Demo
-- MovieLens Dataset Schema
-- =====================================================

-- Create the demo database (run this as superuser)
-- CREATE DATABASE movielens_demo;

-- Connect to the demo database
-- \c movielens_demo;

-- =====================================================
-- EXTENSION INSTALLATION
-- =====================================================

-- Install required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS age;

-- Load AGE extension
LOAD 'age';

-- Set search path to include AGE
SET search_path = ag_catalog, "$user", public;

-- Verify extensions are installed
SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector', 'age');

-- =====================================================
-- TABLE CREATION
-- =====================================================

-- Users table with vector embedding support
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    age INTEGER,
    gender CHAR(1),
    occupation VARCHAR(50),
    zip_code VARCHAR(10),
    embedding vector(128),  -- 128-dimensional embedding vector
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Movies table with vector embedding support and genre flags
CREATE TABLE movies (
    movie_id INTEGER PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    release_date DATE,
    imdb_url VARCHAR(255),
    -- Genre boolean flags (18 genres from MovieLens)
    genre_action BOOLEAN DEFAULT FALSE,
    genre_adventure BOOLEAN DEFAULT FALSE,
    genre_animation BOOLEAN DEFAULT FALSE,
    genre_children BOOLEAN DEFAULT FALSE,
    genre_comedy BOOLEAN DEFAULT FALSE,
    genre_crime BOOLEAN DEFAULT FALSE,
    genre_documentary BOOLEAN DEFAULT FALSE,
    genre_drama BOOLEAN DEFAULT FALSE,
    genre_fantasy BOOLEAN DEFAULT FALSE,
    genre_film_noir BOOLEAN DEFAULT FALSE,
    genre_horror BOOLEAN DEFAULT FALSE,
    genre_musical BOOLEAN DEFAULT FALSE,
    genre_mystery BOOLEAN DEFAULT FALSE,
    genre_romance BOOLEAN DEFAULT FALSE,
    genre_sci_fi BOOLEAN DEFAULT FALSE,
    genre_thriller BOOLEAN DEFAULT FALSE,
    genre_war BOOLEAN DEFAULT FALSE,
    genre_western BOOLEAN DEFAULT FALSE,
    embedding vector(128),  -- 128-dimensional embedding vector
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Ratings table for user-movie interactions
CREATE TABLE ratings (
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    movie_id INTEGER REFERENCES movies(movie_id) ON DELETE CASCADE,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    timestamp INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, movie_id)
);

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

-- Traditional indexes for relational queries
CREATE INDEX idx_ratings_user_id ON ratings(user_id);
CREATE INDEX idx_ratings_movie_id ON ratings(movie_id);
CREATE INDEX idx_ratings_rating ON ratings(rating);
CREATE INDEX idx_ratings_timestamp ON ratings(timestamp);

CREATE INDEX idx_users_age ON users(age);
CREATE INDEX idx_users_gender ON users(gender);
CREATE INDEX idx_users_occupation ON users(occupation);

CREATE INDEX idx_movies_title ON movies(title);
CREATE INDEX idx_movies_release_date ON movies(release_date);

-- Genre indexes for filtering
CREATE INDEX idx_movies_genre_action ON movies(genre_action) WHERE genre_action = true;
CREATE INDEX idx_movies_genre_comedy ON movies(genre_comedy) WHERE genre_comedy = true;
CREATE INDEX idx_movies_genre_drama ON movies(genre_drama) WHERE genre_drama = true;
CREATE INDEX idx_movies_genre_romance ON movies(genre_romance) WHERE genre_romance = true;
CREATE INDEX idx_movies_genre_thriller ON movies(genre_thriller) WHERE genre_thriller = true;

-- =====================================================
-- VECTOR INDEXES FOR DISKANN
-- =====================================================

-- Note: These indexes should be created AFTER embeddings are populated
-- Uncomment and run these after running generate_embeddings.py

-- HNSW indexes for vector similarity search (preferred for DiskANN)
-- CREATE INDEX idx_movies_embedding_hnsw 
-- ON movies USING hnsw (embedding vector_cosine_ops)
-- WITH (m = 16, ef_construction = 64);

-- CREATE INDEX idx_users_embedding_hnsw 
-- ON users USING hnsw (embedding vector_cosine_ops)
-- WITH (m = 16, ef_construction = 64);

-- Alternative: IVFFlat indexes (if HNSW is not available)
-- CREATE INDEX idx_movies_embedding_ivfflat 
-- ON movies USING ivfflat (embedding vector_cosine_ops) 
-- WITH (lists = 100);

-- CREATE INDEX idx_users_embedding_ivfflat 
-- ON users USING ivfflat (embedding vector_cosine_ops) 
-- WITH (lists = 100);

-- =====================================================
-- HELPER VIEWS
-- =====================================================

-- View for movie statistics
CREATE VIEW movie_stats AS
SELECT 
    m.movie_id,
    m.title,
    COUNT(r.rating) as num_ratings,
    AVG(r.rating::numeric) as avg_rating,
    STDDEV(r.rating::numeric) as rating_stddev,
    MIN(r.rating) as min_rating,
    MAX(r.rating) as max_rating,
    -- Genre concatenation for display
    ARRAY_TO_STRING(
        ARRAY[
            CASE WHEN m.genre_action THEN 'Action' END,
            CASE WHEN m.genre_adventure THEN 'Adventure' END,
            CASE WHEN m.genre_animation THEN 'Animation' END,
            CASE WHEN m.genre_children THEN 'Children' END,
            CASE WHEN m.genre_comedy THEN 'Comedy' END,
            CASE WHEN m.genre_crime THEN 'Crime' END,
            CASE WHEN m.genre_documentary THEN 'Documentary' END,
            CASE WHEN m.genre_drama THEN 'Drama' END,
            CASE WHEN m.genre_fantasy THEN 'Fantasy' END,
            CASE WHEN m.genre_film_noir THEN 'Film-Noir' END,
            CASE WHEN m.genre_horror THEN 'Horror' END,
            CASE WHEN m.genre_musical THEN 'Musical' END,
            CASE WHEN m.genre_mystery THEN 'Mystery' END,
            CASE WHEN m.genre_romance THEN 'Romance' END,
            CASE WHEN m.genre_sci_fi THEN 'Sci-Fi' END,
            CASE WHEN m.genre_thriller THEN 'Thriller' END,
            CASE WHEN m.genre_war THEN 'War' END,
            CASE WHEN m.genre_western THEN 'Western' END
        ]::text[], 
        ', '
    ) as genres
FROM movies m
LEFT JOIN ratings r ON m.movie_id = r.movie_id
GROUP BY m.movie_id, m.title, m.genre_action, m.genre_adventure, m.genre_animation, 
         m.genre_children, m.genre_comedy, m.genre_crime, m.genre_documentary, 
         m.genre_drama, m.genre_fantasy, m.genre_film_noir, m.genre_horror, 
         m.genre_musical, m.genre_mystery, m.genre_romance, m.genre_sci_fi, 
         m.genre_thriller, m.genre_war, m.genre_western;

-- View for user statistics
CREATE VIEW user_stats AS
SELECT 
    u.user_id,
    u.age,
    u.gender,
    u.occupation,
    COUNT(r.rating) as num_ratings,
    AVG(r.rating::numeric) as avg_rating,
    STDDEV(r.rating::numeric) as rating_stddev,
    MIN(r.rating) as min_rating,
    MAX(r.rating) as max_rating
FROM users u
LEFT JOIN ratings r ON u.user_id = r.user_id
GROUP BY u.user_id, u.age, u.gender, u.occupation;

-- View for high-quality ratings (4 and 5 stars)
CREATE VIEW high_ratings AS
SELECT 
    r.user_id,
    r.movie_id,
    r.rating,
    r.timestamp,
    u.age,
    u.gender,
    u.occupation,
    m.title,
    m.release_date
FROM ratings r
JOIN users u ON r.user_id = u.user_id
JOIN movies m ON r.movie_id = m.movie_id
WHERE r.rating >= 4;

-- =====================================================
-- FUNCTIONS FOR DEMO QUERIES
-- =====================================================

-- Function to get similar movies using vector similarity
CREATE OR REPLACE FUNCTION get_similar_movies(
    target_movie_id INTEGER,
    similarity_threshold FLOAT DEFAULT 0.7,
    limit_count INTEGER DEFAULT 10
)
RETURNS TABLE(
    movie_id INTEGER,
    title VARCHAR(255),
    similarity_score NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        m2.movie_id,
        m2.title,
        ROUND((1 - (m1.embedding <=> m2.embedding))::numeric, 4) as similarity_score
    FROM movies m1, movies m2
    WHERE m1.movie_id = target_movie_id
        AND m2.movie_id != target_movie_id
        AND m1.embedding IS NOT NULL 
        AND m2.embedding IS NOT NULL
        AND (1 - (m1.embedding <=> m2.embedding)) >= similarity_threshold
    ORDER BY m1.embedding <=> m2.embedding
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Function to get similar users using vector similarity
CREATE OR REPLACE FUNCTION get_similar_users(
    target_user_id INTEGER,
    similarity_threshold FLOAT DEFAULT 0.7,
    limit_count INTEGER DEFAULT 10
)
RETURNS TABLE(
    user_id INTEGER,
    age INTEGER,
    gender CHAR(1),
    occupation VARCHAR(50),
    similarity_score NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        u2.user_id,
        u2.age,
        u2.gender,
        u2.occupation,
        ROUND((1 - (u1.embedding <=> u2.embedding))::numeric, 4) as similarity_score
    FROM users u1, users u2
    WHERE u1.user_id = target_user_id
        AND u2.user_id != target_user_id
        AND u1.embedding IS NOT NULL 
        AND u2.embedding IS NOT NULL
        AND (1 - (u1.embedding <=> u2.embedding)) >= similarity_threshold
    ORDER BY u1.embedding <=> u2.embedding
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- CONFIGURATION SETTINGS
-- =====================================================

-- Vector search configuration (adjust based on your needs)
-- These will be set when vector indexes are created

-- SET hnsw.ef_search = 40;
-- SET ivfflat.probes = 10;

-- Memory settings for better performance
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET work_mem = '32MB';

-- Parallel query settings
ALTER SYSTEM SET max_parallel_workers_per_gather = 2;
ALTER SYSTEM SET max_parallel_workers = 4;

-- =====================================================
-- SAMPLE DATA VERIFICATION QUERIES
-- =====================================================

-- These queries can be run after data loading to verify the setup

-- Check table sizes
-- SELECT 'users' as table_name, COUNT(*) as record_count FROM users
-- UNION ALL
-- SELECT 'movies' as table_name, COUNT(*) as record_count FROM movies
-- UNION ALL
-- SELECT 'ratings' as table_name, COUNT(*) as record_count FROM ratings;

-- Check embedding coverage
-- SELECT 
--     'users' as table_name,
--     COUNT(*) as total_records,
--     COUNT(embedding) as records_with_embeddings,
--     ROUND(COUNT(embedding)::numeric / COUNT(*) * 100, 2) as embedding_coverage_pct
-- FROM users
-- UNION ALL
-- SELECT 
--     'movies' as table_name,
--     COUNT(*) as total_records,
--     COUNT(embedding) as records_with_embeddings,
--     ROUND(COUNT(embedding)::numeric / COUNT(*) * 100, 2) as embedding_coverage_pct
-- FROM movies;

-- Sample data from views
-- SELECT * FROM movie_stats ORDER BY num_ratings DESC LIMIT 10;
-- SELECT * FROM user_stats ORDER BY num_ratings DESC LIMIT 10;

-- =====================================================
-- CLEANUP COMMANDS (USE WITH CAUTION)
-- =====================================================

-- Uncomment these only if you need to reset the database

-- Drop all tables and start over
-- DROP TABLE IF EXISTS ratings CASCADE;
-- DROP TABLE IF EXISTS movies CASCADE;
-- DROP TABLE IF EXISTS users CASCADE;

-- Drop views
-- DROP VIEW IF EXISTS movie_stats CASCADE;
-- DROP VIEW IF EXISTS user_stats CASCADE;
-- DROP VIEW IF EXISTS high_ratings CASCADE;

-- Drop functions
-- DROP FUNCTION IF EXISTS get_similar_movies(INTEGER, FLOAT, INTEGER);
-- DROP FUNCTION IF EXISTS get_similar_users(INTEGER, FLOAT, INTEGER);

-- =====================================================
-- COMPLETION MESSAGE
-- =====================================================

-- Display completion message
DO $$
BEGIN
    RAISE NOTICE 'Database schema creation completed successfully!';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '1. Load MovieLens data using load_movielens_data.py';
    RAISE NOTICE '2. Generate embeddings using generate_embeddings.py';
    RAISE NOTICE '3. Create vector indexes (uncomment the index creation commands above)';
    RAISE NOTICE '4. Set up Apache AGE graph using setup_age_graph.py';
    RAISE NOTICE '5. Run demo queries from demo_queries.sql';
END $$;

