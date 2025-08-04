-- =====================================================
-- DiskANN and Apache AGE Demo Queries
-- MovieLens Dataset Demonstration
-- =====================================================
--
-- IMPORTANT NOTES:
-- 1. For DiskANN queries: Run directly in psql
-- 2. For AGE queries: First run the AGE setup commands in the "APACHE AGE GRAPH QUERIES" section
-- 3. Make sure you've run setup_age_graph.py before testing AGE queries
-- =====================================================

-- =====================================================
-- SETUP AND VERIFICATION QUERIES
-- =====================================================

-- Verify extensions are installed
SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector', 'age');

-- Check data counts
SELECT 'users' as table_name, COUNT(*) as record_count FROM users
UNION ALL
SELECT 'movies' as table_name, COUNT(*) as record_count FROM movies
UNION ALL
SELECT 'ratings' as table_name, COUNT(*) as record_count FROM ratings;

-- Verify embeddings are present
SELECT 
    'users' as table_name,
    COUNT(*) as total_records,
    COUNT(embedding) as records_with_embeddings,
    ROUND(COUNT(embedding)::numeric / COUNT(*) * 100, 2) as embedding_coverage_pct
FROM users
UNION ALL
SELECT 
    'movies' as table_name,
    COUNT(*) as total_records,
    COUNT(embedding) as records_with_embeddings,
    ROUND(COUNT(embedding)::numeric / COUNT(*) * 100, 2) as embedding_coverage_pct
FROM movies;

-- =====================================================
-- DISKANN VECTOR SIMILARITY QUERIES
-- =====================================================

-- Query 1: Find movies similar to "Toy Story" (movie_id = 1)
-- This demonstrates content-based similarity using DiskANN
SELECT 
    m2.movie_id,
    m2.title,
    ROUND((1 - (m1.embedding <=> m2.embedding))::numeric, 4) as similarity_score
FROM movies m1, movies m2
WHERE m1.movie_id = 1 
    AND m2.movie_id != 1
    AND m1.embedding IS NOT NULL 
    AND m2.embedding IS NOT NULL
ORDER BY m1.embedding <=> m2.embedding
LIMIT 10;

-- Query 2: Find users similar to user 1 (collaborative filtering potential)
-- This demonstrates user similarity for recommendation systems
SELECT 
    u2.user_id,
    u2.age,
    u2.gender,
    u2.occupation,
    ROUND((1 - (u1.embedding <=> u2.embedding))::numeric, 4) as similarity_score
FROM users u1, users u2
WHERE u1.user_id = 1 
    AND u2.user_id != 1
    AND u1.embedding IS NOT NULL 
    AND u2.embedding IS NOT NULL
ORDER BY u1.embedding <=> u2.embedding
LIMIT 10;

-- Query 3: Movie recommendation based on user similarity
-- Find movies liked by users similar to user 1
WITH similar_users AS (
    SELECT 
        u2.user_id,
        1 - (u1.embedding <=> u2.embedding) as similarity_score
    FROM users u1, users u2
    WHERE u1.user_id = 1 
        AND u2.user_id != 1
        AND u1.embedding IS NOT NULL 
        AND u2.embedding IS NOT NULL
    ORDER BY u1.embedding <=> u2.embedding
    LIMIT 20
),
user_1_movies AS (
    SELECT movie_id FROM ratings WHERE user_id = 1
)
SELECT 
    m.movie_id,
    m.title,
    AVG(r.rating) as avg_rating_from_similar_users,
    COUNT(r.rating) as num_similar_users_rated,
    ROUND(AVG(su.similarity_score)::numeric, 4) as avg_similarity_of_raters
FROM similar_users su
JOIN ratings r ON su.user_id = r.user_id
JOIN movies m ON r.movie_id = m.movie_id
WHERE r.rating >= 4  -- Only consider highly rated movies
    AND m.movie_id NOT IN (SELECT movie_id FROM user_1_movies)  -- Exclude movies user 1 has already seen
GROUP BY m.movie_id, m.title
HAVING COUNT(r.rating) >= 2  -- At least 2 similar users rated it highly
ORDER BY avg_rating_from_similar_users DESC, num_similar_users_rated DESC
LIMIT 10;

-- Query 4: Genre-based movie similarity
-- Find action movies similar to a specific action movie
SELECT 
    m2.movie_id,
    m2.title,
    ROUND((1 - (m1.embedding <=> m2.embedding))::numeric, 4) as similarity_score
FROM movies m1, movies m2
WHERE m1.movie_id = 1  -- Toy Story
    AND m2.movie_id != 1
    AND m2.genre_action = true  -- Only action movies
    AND m1.embedding IS NOT NULL 
    AND m2.embedding IS NOT NULL
ORDER BY m1.embedding <=> m2.embedding
LIMIT 10;

-- Query 5: Performance test for vector similarity search
-- Measure query performance with EXPLAIN ANALYZE
EXPLAIN (ANALYZE, BUFFERS) 
SELECT movie_id, title
FROM movies
WHERE embedding IS NOT NULL
ORDER BY embedding <=> (SELECT embedding FROM movies WHERE movie_id = 1)
LIMIT 10;

-- =====================================================
-- APACHE AGE GRAPH QUERIES
-- =====================================================

-- IMPORTANT: Run these commands before executing any AGE queries
-- For Azure PostgreSQL Flexible Server, extensions are pre-loaded
-- Just set the search path
SET search_path = ag_catalog, "$user", public;

-- Verify AGE extension is loaded
SELECT extname, extversion FROM pg_extension WHERE extname = 'age';

-- Verify graph exists (run this after graph setup)
SELECT * FROM ag_catalog.ag_graph;

-- Query 6: Basic user-movie relationships
-- Show movies rated by user 1
-- For Azure PostgreSQL, just set search path
SET search_path = ag_catalog, "$user", public;

SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (u:User {user_id: 1})-[r:RATED]->(m:Movie)
    RETURN m.title, r.rating
    ORDER BY r.rating DESC
$$) as (movie_title agtype, rating agtype);

-- Query 7: Find users who rated a specific movie highly
-- Users who gave "Toy Story" (movie_id: 1) a rating of 4 or 5
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (u:User)-[r:RATED]->(m:Movie {movie_id: 1})
    WHERE r.rating >= 4
    RETURN u.user_id, u.age, u.gender, r.rating
    ORDER BY r.rating DESC
$$) as (user_id agtype, age agtype, gender agtype, rating agtype);

-- Query 8: Collaborative filtering using graph traversal
-- Find movies recommended for user 1 based on similar users' preferences
-- Simplified version for Apache AGE compatibility
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (u1:User {user_id: 1})-[r1:RATED]->(m1:Movie)
    WHERE r1.rating >= 4
    MATCH (u2:User)-[r2:RATED]->(m1)
    WHERE u2.user_id <> 1 AND r2.rating >= 4
    WITH u2, count(m1) as common_likes
    WHERE common_likes >= 3
    MATCH (u2)-[r3:RATED]->(rec:Movie)
    WHERE r3.rating >= 4
    RETURN rec.title, count(*) as recommendation_strength, avg(r3.rating) as avg_rating
    ORDER BY recommendation_strength DESC, avg_rating DESC
    LIMIT 10
$$) as (movie_title agtype, recommendation_strength agtype, avg_rating agtype);

-- Query 9: Find shortest path between two movies through users
-- Discover connection patterns between movies
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH p = shortestPath((m1:Movie {movie_id: 1})-[*..4]-(m2:Movie {movie_id: 50}))
    RETURN p
    LIMIT 1
$$) as (path agtype);

-- Query 10: Community detection - find groups of users with similar tastes
-- Users who consistently rate the same movies highly
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (u1:User)-[r1:RATED]->(m:Movie)<-[r2:RATED]-(u2:User)
    WHERE u1.user_id < u2.user_id 
        AND r1.rating >= 4 
        AND r2.rating >= 4
    WITH u1, u2, count(m) as shared_likes
    WHERE shared_likes >= 5
    RETURN u1.user_id, u2.user_id, shared_likes
    ORDER BY shared_likes DESC
    LIMIT 20
$$) as (user1_id agtype, user2_id agtype, shared_likes agtype);

-- Query 11: Movie popularity analysis
-- Find most popular movies based on high ratings
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (u:User)-[r:RATED]->(m:Movie)
    WHERE r.rating >= 4
    RETURN m.movie_id, m.title, count(r) as high_rating_count, avg(r.rating) as avg_rating
    ORDER BY high_rating_count DESC
    LIMIT 15
$$) as (movie_id agtype, movie_title agtype, high_rating_count agtype, avg_rating agtype);

-- Query 12: User influence analysis
-- Find users whose ratings correlate with many other users
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (influencer:User)-[r1:RATED]->(m:Movie)<-[r2:RATED]-(follower:User)
    WHERE influencer.user_id <> follower.user_id
        AND abs(r1.rating - r2.rating) <= 1
    WITH influencer, count(DISTINCT follower) as influenced_users
    WHERE influenced_users >= 10
    RETURN influencer.user_id, influencer.age, influencer.gender, influenced_users
    ORDER BY influenced_users DESC
    LIMIT 10
$$) as (user_id agtype, age agtype, gender agtype, influenced_users agtype);

-- =====================================================
-- HYBRID QUERIES (COMBINING DISKANN AND AGE)
-- =====================================================

-- Query 13: Enhanced recommendation using both vector similarity and graph analysis
-- Step 1: Find similar users using DiskANN
-- Step 2: Use AGE to analyze their rating patterns
WITH similar_users_vector AS (
    SELECT 
        u2.user_id,
        1 - (u1.embedding <=> u2.embedding) as similarity_score
    FROM users u1, users u2
    WHERE u1.user_id = 1 
        AND u2.user_id != 1
        AND u1.embedding IS NOT NULL 
        AND u2.embedding IS NOT NULL
    ORDER BY u1.embedding <=> u2.embedding
    LIMIT 10
)
SELECT 
    m.movie_id,
    m.title,
    COUNT(r.rating) as num_similar_users_liked,
    AVG(r.rating) as avg_rating,
    AVG(suv.similarity_score) as avg_user_similarity
FROM similar_users_vector suv
JOIN ratings r ON suv.user_id = r.user_id
JOIN movies m ON r.movie_id = m.movie_id
WHERE r.rating >= 4
    AND m.movie_id NOT IN (SELECT movie_id FROM ratings WHERE user_id = 1)
GROUP BY m.movie_id, m.title
HAVING COUNT(r.rating) >= 2
ORDER BY avg_rating DESC, num_similar_users_liked DESC
LIMIT 10;

-- =====================================================
-- PERFORMANCE ANALYSIS QUERIES
-- =====================================================

-- Query 14: Compare vector similarity search performance
-- Test different distance metrics
EXPLAIN (ANALYZE, BUFFERS)
SELECT movie_id, title, embedding <-> (SELECT embedding FROM movies WHERE movie_id = 1) as l2_distance
FROM movies 
WHERE embedding IS NOT NULL
ORDER BY embedding <-> (SELECT embedding FROM movies WHERE movie_id = 1)
LIMIT 10;

EXPLAIN (ANALYZE, BUFFERS)
SELECT movie_id, title, embedding <=> (SELECT embedding FROM movies WHERE movie_id = 1) as cosine_distance
FROM movies 
WHERE embedding IS NOT NULL
ORDER BY embedding <=> (SELECT embedding FROM movies WHERE movie_id = 1)
LIMIT 10;

-- Query 15: Graph query performance analysis
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (u:User {user_id: 1})-[r:RATED]->(m:Movie)
    RETURN count(*)
$$) as (count agtype);

-- =====================================================
-- DATA EXPLORATION QUERIES
-- =====================================================

-- Query 16: Embedding statistics
SELECT 
    'movies' as entity_type,
    COUNT(*) as total_count,
    COUNT(embedding) as with_embedding,
    AVG(array_length(embedding, 1)) as avg_dimension,
    MIN(array_length(embedding, 1)) as min_dimension,
    MAX(array_length(embedding, 1)) as max_dimension
FROM movies
WHERE embedding IS NOT NULL
UNION ALL
SELECT 
    'users' as entity_type,
    COUNT(*) as total_count,
    COUNT(embedding) as with_embedding,
    AVG(array_length(embedding, 1)) as avg_dimension,
    MIN(array_length(embedding, 1)) as min_dimension,
    MAX(array_length(embedding, 1)) as max_dimension
FROM users
WHERE embedding IS NOT NULL;

-- Query 17: Rating distribution analysis
SELECT 
    rating,
    COUNT(*) as count,
    ROUND(COUNT(*)::numeric / (SELECT COUNT(*) FROM ratings) * 100, 2) as percentage
FROM ratings
GROUP BY rating
ORDER BY rating;

-- Query 18: Genre popularity analysis
SELECT 
    'Action' as genre, COUNT(*) as movie_count FROM movies WHERE genre_action = true
UNION ALL
SELECT 'Comedy' as genre, COUNT(*) as movie_count FROM movies WHERE genre_comedy = true
UNION ALL
SELECT 'Drama' as genre, COUNT(*) as movie_count FROM movies WHERE genre_drama = true
UNION ALL
SELECT 'Romance' as genre, COUNT(*) as movie_count FROM movies WHERE genre_romance = true
UNION ALL
SELECT 'Thriller' as genre, COUNT(*) as movie_count FROM movies WHERE genre_thriller = true
ORDER BY movie_count DESC;

-- =====================================================
-- CLEANUP QUERIES (USE WITH CAUTION)
-- =====================================================

-- Uncomment these queries only if you need to reset the demo

-- Drop graph (WARNING: This will delete all graph data)
-- SELECT ag_catalog.drop_graph('movielens', true);

-- Clear embeddings (WARNING: This will delete all embeddings)
-- UPDATE movies SET embedding = NULL;
-- UPDATE users SET embedding = NULL;

-- Drop indexes (WARNING: This will remove performance optimizations)
-- DROP INDEX IF EXISTS idx_movies_embedding_hnsw;
-- DROP INDEX IF EXISTS idx_users_embedding_hnsw;

