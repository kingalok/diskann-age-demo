-- =====================================================
-- Database Schema for The Movies Dataset (TMDB)
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
    imdb_id VARCHAR(20) UNIQUE,
    title VARCHAR(500) NOT NULL,
    original_title VARCHAR(500),
    overview TEXT,
    tagline TEXT,
    release_date DATE,
    budget BIGINT,
    revenue BIGINT,
    runtime INTEGER,
    vote_average NUMERIC(3,1),
    vote_count INTEGER,
    homepage VARCHAR(500),
    status VARCHAR(50),
    original_language VARCHAR(10),
    genres JSONB,
    production_companies JSONB,
    production_countries JSONB,
    spoken_languages JSONB,
    embedding VECTOR(768),
    tsv_overview TSVECTOR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Users table (simplified as dataset doesn't provide demographics)
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

-- Persons table (actors, directors, crew)
CREATE TABLE IF NOT EXISTS persons (
    person_id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    gender INTEGER,
    profile_path VARCHAR(255),
    known_for_department VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Movie cast junction table
CREATE TABLE IF NOT EXISTS movie_cast (
    movie_id INTEGER REFERENCES movies(movie_id),
    person_id INTEGER REFERENCES persons(person_id),
    character VARCHAR(500),
    credit_id VARCHAR(50),
    cast_id INTEGER,
    order_in_credits INTEGER,
    PRIMARY KEY (movie_id, person_id, credit_id)
);

-- Movie crew junction table
CREATE TABLE IF NOT EXISTS movie_crew (
    movie_id INTEGER REFERENCES movies(movie_id),
    person_id INTEGER REFERENCES persons(person_id),
    department VARCHAR(100),
    job VARCHAR(100),
    credit_id VARCHAR(50),
    PRIMARY KEY (movie_id, person_id, credit_id)
);

-- Keywords table
CREATE TABLE IF NOT EXISTS keywords (
    keyword_id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Movie keywords junction table
CREATE TABLE IF NOT EXISTS movie_keywords (
    movie_id INTEGER REFERENCES movies(movie_id),
    keyword_id INTEGER REFERENCES keywords(keyword_id),
    PRIMARY KEY (movie_id, keyword_id)
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

-- JSONB indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_movies_genres_gin 
ON movies USING GIN (genres);

CREATE INDEX IF NOT EXISTS idx_movies_production_companies_gin 
ON movies USING GIN (production_companies);

CREATE INDEX IF NOT EXISTS idx_movies_production_countries_gin 
ON movies USING GIN (production_countries);

-- Text search indexes
CREATE INDEX IF NOT EXISTS idx_movies_tsv_overview 
ON movies USING GIN (tsv_overview);

CREATE INDEX IF NOT EXISTS idx_movies_title_gin 
ON movies USING GIN (to_tsvector('english', title));

-- Standard indexes for common queries
CREATE INDEX IF NOT EXISTS idx_movies_release_date ON movies(release_date);
CREATE INDEX IF NOT EXISTS idx_movies_vote_average ON movies(vote_average);
CREATE INDEX IF NOT EXISTS idx_movies_vote_count ON movies(vote_count);
CREATE INDEX IF NOT EXISTS idx_movies_budget ON movies(budget);
CREATE INDEX IF NOT EXISTS idx_movies_revenue ON movies(revenue);
CREATE INDEX IF NOT EXISTS idx_movies_runtime ON movies(runtime);

CREATE INDEX IF NOT EXISTS idx_ratings_user_id ON ratings(user_id);
CREATE INDEX IF NOT EXISTS idx_ratings_movie_id ON ratings(movie_id);
CREATE INDEX IF NOT EXISTS idx_ratings_rating ON ratings(rating);
CREATE INDEX IF NOT EXISTS idx_ratings_timestamp ON ratings(timestamp);

CREATE INDEX IF NOT EXISTS idx_persons_name ON persons(name);
CREATE INDEX IF NOT EXISTS idx_persons_known_for_department ON persons(known_for_department);

CREATE INDEX IF NOT EXISTS idx_movie_cast_movie_id ON movie_cast(movie_id);
CREATE INDEX IF NOT EXISTS idx_movie_cast_person_id ON movie_cast(person_id);
CREATE INDEX IF NOT EXISTS idx_movie_cast_order ON movie_cast(order_in_credits);

CREATE INDEX IF NOT EXISTS idx_movie_crew_movie_id ON movie_crew(movie_id);
CREATE INDEX IF NOT EXISTS idx_movie_crew_person_id ON movie_crew(person_id);
CREATE INDEX IF NOT EXISTS idx_movie_crew_department ON movie_crew(department);
CREATE INDEX IF NOT EXISTS idx_movie_crew_job ON movie_crew(job);

CREATE INDEX IF NOT EXISTS idx_keywords_name ON keywords(name);

-- =====================================================
-- VIEWS FOR COMMON QUERIES
-- =====================================================

-- View for movies with their primary genre
CREATE OR REPLACE VIEW movies_with_primary_genre AS
SELECT 
    m.movie_id,
    m.title,
    m.overview,
    m.release_date,
    m.vote_average,
    m.vote_count,
    m.budget,
    m.revenue,
    m.runtime,
    CASE 
        WHEN m.genres IS NOT NULL AND jsonb_array_length(m.genres) > 0 
        THEN (m.genres->0->>'name')::VARCHAR(50)
        ELSE 'Unknown'
    END as primary_genre
FROM movies m;

-- View for directors
CREATE OR REPLACE VIEW movie_directors AS
SELECT 
    mc.movie_id,
    p.person_id,
    p.name as director_name
FROM movie_crew mc
JOIN persons p ON mc.person_id = p.person_id
WHERE mc.job = 'Director';

-- View for main cast (top 5 actors by order)
CREATE OR REPLACE VIEW movie_main_cast AS
SELECT 
    mcast.movie_id,
    p.person_id,
    p.name as actor_name,
    mcast.character,
    mcast.order_in_credits
FROM movie_cast mcast
JOIN persons p ON mcast.person_id = p.person_id
WHERE mcast.order_in_credits <= 5
ORDER BY mcast.movie_id, mcast.order_in_credits;

-- View for movie statistics
CREATE OR REPLACE VIEW movie_stats AS
SELECT 
    m.movie_id,
    m.title,
    m.vote_average,
    m.vote_count,
    COUNT(r.rating) as rating_count,
    AVG(r.rating) as avg_user_rating,
    STDDEV(r.rating) as rating_stddev,
    COUNT(DISTINCT mc.person_id) as cast_count,
    COUNT(DISTINCT mcr.person_id) as crew_count
FROM movies m
LEFT JOIN ratings r ON m.movie_id = r.movie_id
LEFT JOIN movie_cast mc ON m.movie_id = mc.movie_id
LEFT JOIN movie_crew mcr ON m.movie_id = mcr.movie_id
GROUP BY m.movie_id, m.title, m.vote_average, m.vote_count;

-- =====================================================
-- FUNCTIONS FOR DATA PROCESSING
-- =====================================================

-- Function to update text search vectors
CREATE OR REPLACE FUNCTION update_movie_tsv() RETURNS TRIGGER AS $$
BEGIN
    NEW.tsv_overview := to_tsvector('english', COALESCE(NEW.overview, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically update text search vectors
DROP TRIGGER IF EXISTS trigger_update_movie_tsv ON movies;
CREATE TRIGGER trigger_update_movie_tsv
    BEFORE INSERT OR UPDATE ON movies
    FOR EACH ROW EXECUTE FUNCTION update_movie_tsv();

-- Function to extract genres from JSONB
CREATE OR REPLACE FUNCTION extract_genre_names(genres_json JSONB)
RETURNS TEXT[] AS $$
BEGIN
    IF genres_json IS NULL THEN
        RETURN ARRAY[]::TEXT[];
    END IF;
    
    RETURN ARRAY(
        SELECT jsonb_array_elements(genres_json)->>'name'
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to calculate movie popularity score
CREATE OR REPLACE FUNCTION calculate_popularity_score(
    vote_average NUMERIC,
    vote_count INTEGER,
    revenue BIGINT DEFAULT NULL
)
RETURNS NUMERIC AS $$
BEGIN
    -- Weighted score combining vote average, vote count, and revenue
    RETURN (
        COALESCE(vote_average, 0) * 0.4 +
        (LOG(GREATEST(vote_count, 1)) / LOG(10)) * 0.4 +
        CASE 
            WHEN revenue IS NOT NULL AND revenue > 0 
            THEN (LOG(revenue) / LOG(10)) * 0.2
            ELSE 0
        END
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- =====================================================
-- APACHE AGE GRAPH SETUP
-- =====================================================

-- Create the graph (will be populated by separate script)
SELECT ag_catalog.create_graph('tmdb_movies');

-- =====================================================
-- SAMPLE DATA VALIDATION QUERIES
-- =====================================================

-- Query to check table sizes after data load
CREATE OR REPLACE VIEW data_load_summary AS
SELECT 
    'movies' as table_name, COUNT(*) as record_count FROM movies
UNION ALL
SELECT 'users' as table_name, COUNT(*) as record_count FROM users
UNION ALL
SELECT 'ratings' as table_name, COUNT(*) as record_count FROM ratings
UNION ALL
SELECT 'persons' as table_name, COUNT(*) as record_count FROM persons
UNION ALL
SELECT 'movie_cast' as table_name, COUNT(*) as record_count FROM movie_cast
UNION ALL
SELECT 'movie_crew' as table_name, COUNT(*) as record_count FROM movie_crew
UNION ALL
SELECT 'keywords' as table_name, COUNT(*) as record_count FROM keywords
UNION ALL
SELECT 'movie_keywords' as table_name, COUNT(*) as record_count FROM movie_keywords;

-- Query to check embedding coverage
CREATE OR REPLACE VIEW embedding_coverage AS
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
CREATE OR REPLACE FUNCTION reset_all_data()
RETURNS VOID AS $$
BEGIN
    -- Drop graph if exists
    BEGIN
        PERFORM ag_catalog.drop_graph('tmdb_movies', true);
    EXCEPTION
        WHEN OTHERS THEN
            -- Graph doesn't exist, continue
            NULL;
    END;
    
    -- Clear all tables
    TRUNCATE TABLE movie_keywords CASCADE;
    TRUNCATE TABLE movie_crew CASCADE;
    TRUNCATE TABLE movie_cast CASCADE;
    TRUNCATE TABLE ratings CASCADE;
    TRUNCATE TABLE keywords CASCADE;
    TRUNCATE TABLE persons CASCADE;
    TRUNCATE TABLE movies CASCADE;
    TRUNCATE TABLE users CASCADE;
    
    -- Recreate graph
    PERFORM ag_catalog.create_graph('tmdb_movies');
    
    RAISE NOTICE 'All data has been reset. Tables are empty and graph is recreated.';
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- COMMENTS AND DOCUMENTATION
-- =====================================================

COMMENT ON TABLE movies IS 'Core movie metadata from TMDB dataset';
COMMENT ON TABLE users IS 'User information (simplified from ratings data)';
COMMENT ON TABLE ratings IS 'User ratings for movies';
COMMENT ON TABLE persons IS 'Actors, directors, and crew members';
COMMENT ON TABLE movie_cast IS 'Junction table linking movies to cast members';
COMMENT ON TABLE movie_crew IS 'Junction table linking movies to crew members';
COMMENT ON TABLE keywords IS 'Plot keywords for movies';
COMMENT ON TABLE movie_keywords IS 'Junction table linking movies to keywords';

COMMENT ON COLUMN movies.embedding IS '768-dimensional vector embedding for similarity search';
COMMENT ON COLUMN movies.genres IS 'JSONB array of genre objects with id and name';
COMMENT ON COLUMN movies.tsv_overview IS 'Text search vector for movie overview';
COMMENT ON COLUMN users.embedding IS '768-dimensional vector embedding derived from rating patterns';

-- =====================================================
-- COMPLETION MESSAGE
-- =====================================================

DO $$
BEGIN
    RAISE NOTICE 'TMDB Movies database schema created successfully!';
    RAISE NOTICE 'Tables created: movies, users, ratings, persons, movie_cast, movie_crew, keywords, movie_keywords';
    RAISE NOTICE 'Indexes created for vector similarity, JSONB queries, and text search';
    RAISE NOTICE 'Views created for common query patterns';
    RAISE NOTICE 'Apache AGE graph "tmdb_movies" created';
    RAISE NOTICE 'Ready for data loading!';
END $$;

