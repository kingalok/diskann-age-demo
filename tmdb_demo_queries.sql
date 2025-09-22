-- =====================================================
-- TMDB Demo Queries for DiskANN and Apache AGE
-- Comprehensive demonstration of vector similarity search and graph analytics
-- =====================================================

-- Set search path to include AGE catalog
SET search_path = ag_catalog, "$user", public;

-- =====================================================
-- DISKANN VECTOR SIMILARITY QUERIES
-- =====================================================

-- Query 1: Content-based movie recommendations using vector similarity
-- Find movies similar to "Toy Story" based on plot and genre embeddings
WITH target_movie AS (
    SELECT embedding 
    FROM movies 
    WHERE title ILIKE '%Toy Story%' 
    LIMIT 1
)
SELECT 
    m.title,
    m.vote_average,
    m.release_date,
    array_to_string(
        ARRAY(
            SELECT jsonb_array_elements_text(
                CASE 
                    WHEN jsonb_typeof(m.genres) = 'array' 
                    THEN (SELECT jsonb_agg(genre->>'name') FROM jsonb_array_elements(m.genres) AS genre)
                    ELSE '[]'::jsonb
                END
            )
        ), ', '
    ) as genres,
    (m.embedding <=> t.embedding) as similarity_distance
FROM movies m, target_movie t
WHERE m.embedding IS NOT NULL 
    AND t.embedding IS NOT NULL
    AND m.title NOT ILIKE '%Toy Story%'
ORDER BY m.embedding <=> t.embedding
LIMIT 10;

-- Query 2: User-based collaborative filtering using vector similarity
-- Find users similar to user ID 1 and recommend movies they liked
WITH target_user AS (
    SELECT embedding 
    FROM users 
    WHERE user_id = 1
    LIMIT 1
),
similar_users AS (
    SELECT 
        u.user_id,
        (u.embedding <=> t.embedding) as similarity_distance
    FROM users u, target_user t
    WHERE u.embedding IS NOT NULL 
        AND t.embedding IS NOT NULL
        AND u.user_id != 1
    ORDER BY u.embedding <=> t.embedding
    LIMIT 20
)
SELECT 
    m.title,
    m.vote_average,
    AVG(r.rating) as avg_rating_from_similar_users,
    COUNT(r.rating) as rating_count
FROM similar_users su
JOIN ratings r ON su.user_id = r.user_id
JOIN movies m ON r.movie_id = m.movie_id
WHERE r.rating >= 4.0
    AND m.movie_id NOT IN (
        SELECT movie_id FROM ratings WHERE user_id = 1
    )
GROUP BY m.movie_id, m.title, m.vote_average
HAVING COUNT(r.rating) >= 3
ORDER BY avg_rating_from_similar_users DESC, rating_count DESC
LIMIT 10;

-- Query 3: Hybrid content and collaborative filtering
-- Combine movie content similarity with user preference patterns
WITH content_similar AS (
    SELECT 
        m.movie_id,
        m.title,
        m.vote_average,
        (m.embedding <=> (SELECT embedding FROM movies WHERE title ILIKE '%Matrix%' LIMIT 1)) as content_distance
    FROM movies m
    WHERE m.embedding IS NOT NULL
        AND m.title NOT ILIKE '%Matrix%'
    ORDER BY content_distance
    LIMIT 50
),
user_preferences AS (
    SELECT 
        r.movie_id,
        AVG(r.rating) as avg_user_rating,
        COUNT(r.rating) as rating_count
    FROM ratings r
    WHERE r.rating >= 4.0
    GROUP BY r.movie_id
    HAVING COUNT(r.rating) >= 10
)
SELECT 
    cs.title,
    cs.vote_average,
    up.avg_user_rating,
    up.rating_count,
    cs.content_distance,
    (cs.content_distance * 0.6 + (5.0 - up.avg_user_rating) * 0.4) as hybrid_score
FROM content_similar cs
JOIN user_preferences up ON cs.movie_id = up.movie_id
ORDER BY hybrid_score ASC
LIMIT 15;

-- Query 4: Genre-based movie clustering using embeddings
-- Find movies that are similar within specific genres
SELECT 
    genre_name,
    title,
    vote_average,
    similarity_rank
FROM (
    SELECT 
        g.genre_name,
        m.title,
        m.vote_average,
        ROW_NUMBER() OVER (
            PARTITION BY g.genre_name 
            ORDER BY m.embedding <=> g.genre_centroid
        ) as similarity_rank
    FROM (
        SELECT 
            genre_name,
            AVG(m.embedding) as genre_centroid
        FROM (
            SELECT 
                jsonb_array_elements(m.genres)->>'name' as genre_name,
                m.embedding
            FROM movies m
            WHERE m.genres IS NOT NULL 
                AND m.embedding IS NOT NULL
                AND jsonb_typeof(m.genres) = 'array'
        ) genre_movies
        JOIN movies m ON TRUE
        WHERE m.embedding IS NOT NULL
        GROUP BY genre_name
        HAVING COUNT(*) >= 20
    ) g
    CROSS JOIN movies m
    WHERE m.embedding IS NOT NULL
        AND m.genres ? g.genre_name
) ranked_movies
WHERE similarity_rank <= 5
ORDER BY genre_name, similarity_rank;

-- =====================================================
-- APACHE AGE GRAPH ANALYTICS QUERIES
-- =====================================================

-- Query 5: Find movies that actors from "The Matrix" have appeared in together
-- Collaborative network analysis through cast connections
SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
    MATCH (matrix:Movie)
    WHERE matrix.title CONTAINS 'Matrix'
    MATCH (matrix)<-[:ACTED_IN]-(actor:Person)
    MATCH (actor)-[:ACTED_IN]->(other_movie:Movie)
    WHERE other_movie.movie_id <> matrix.movie_id
    WITH other_movie, collect(DISTINCT actor.name) as shared_actors
    WHERE size(shared_actors) >= 2
    RETURN other_movie.title, shared_actors, size(shared_actors) as actor_count
    ORDER BY actor_count DESC
    LIMIT 10
$$) as (movie_title agtype, shared_actors agtype, actor_count agtype);

-- Query 6: Director collaboration network
-- Find directors who have worked with the same actors multiple times
SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
    MATCH (d1:Person)-[:DIRECTED]->(m1:Movie)<-[:ACTED_IN]-(actor:Person)
    MATCH (d2:Person)-[:DIRECTED]->(m2:Movie)<-[:ACTED_IN]-(actor)
    WHERE d1.person_id <> d2.person_id AND m1.movie_id <> m2.movie_id
    WITH d1, d2, count(DISTINCT actor) as shared_actors_count
    WHERE shared_actors_count >= 3
    RETURN d1.name as director1, d2.name as director2, shared_actors_count
    ORDER BY shared_actors_count DESC
    LIMIT 15
$$) as (director1 agtype, director2 agtype, shared_actors_count agtype);

-- Query 7: Movie recommendation through user similarity graph
-- Find movies liked by users with similar taste patterns
SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
    MATCH (target_user:User {user_id: 1})-[r1:RATED]->(liked_movie:Movie)
    WHERE r1.rating >= 4.0
    MATCH (other_user:User)-[r2:RATED]->(liked_movie)
    WHERE other_user.user_id <> 1 AND r2.rating >= 4.0
    WITH other_user, count(liked_movie) as common_likes
    WHERE common_likes >= 3
    MATCH (other_user)-[r3:RATED]->(recommended:Movie)
    WHERE r3.rating >= 4.0
    AND NOT EXISTS((target_user)-[:RATED]->(recommended))
    RETURN recommended.title, count(*) as recommendation_strength, avg(r3.rating) as avg_rating
    ORDER BY recommendation_strength DESC, avg_rating DESC
    LIMIT 10
$$) as (movie_title agtype, recommendation_strength agtype, avg_rating agtype);

-- Query 8: Genre influence network
-- Analyze how genres connect through shared movies and actors
SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
    MATCH (g1:Genre)<-[:HAS_GENRE]-(m:Movie)-[:HAS_GENRE]->(g2:Genre)
    WHERE g1.name <> g2.name
    WITH g1, g2, count(m) as shared_movies
    WHERE shared_movies >= 10
    RETURN g1.name as genre1, g2.name as genre2, shared_movies
    ORDER BY shared_movies DESC
    LIMIT 20
$$) as (genre1 agtype, genre2 agtype, shared_movies agtype);

-- Query 9: Actor career path analysis
-- Find actors who have worked across different genres and their evolution
SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
    MATCH (actor:Person)-[:ACTED_IN]->(movie:Movie)-[:HAS_GENRE]->(genre:Genre)
    WHERE actor.known_for_department = 'Acting'
    WITH actor, genre, count(movie) as movies_in_genre
    WHERE movies_in_genre >= 2
    WITH actor, collect({genre: genre.name, count: movies_in_genre}) as genre_distribution
    WHERE size(genre_distribution) >= 3
    RETURN actor.name, genre_distribution, size(genre_distribution) as genre_diversity
    ORDER BY genre_diversity DESC
    LIMIT 15
$$) as (actor_name agtype, genre_distribution agtype, genre_diversity agtype);

-- Query 10: Movie influence through cast connections
-- Find movies that are connected through shared cast members
SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
    MATCH (m1:Movie)<-[:ACTED_IN]-(actor:Person)-[:ACTED_IN]->(m2:Movie)
    WHERE m1.movie_id <> m2.movie_id
    WITH m1, m2, count(actor) as shared_cast_count
    WHERE shared_cast_count >= 3
    RETURN m1.title as movie1, m2.title as movie2, shared_cast_count
    ORDER BY shared_cast_count DESC
    LIMIT 20
$$) as (movie1 agtype, movie2 agtype, shared_cast_count agtype);

-- =====================================================
-- HYBRID DISKANN + AGE QUERIES
-- =====================================================

-- Query 11: Enhanced recommendation combining vector similarity and graph traversal
-- Use DiskANN to find similar movies, then AGE to explore cast connections
WITH vector_similar_movies AS (
    SELECT 
        m.movie_id,
        m.title,
        (m.embedding <=> (SELECT embedding FROM movies WHERE title ILIKE '%Inception%' LIMIT 1)) as similarity_distance
    FROM movies m
    WHERE m.embedding IS NOT NULL
        AND m.title NOT ILIKE '%Inception%'
    ORDER BY similarity_distance
    LIMIT 20
)
SELECT 
    graph_result.movie_title::text as recommended_movie,
    graph_result.shared_actors_count::int as shared_actors,
    vsm.similarity_distance,
    (vsm.similarity_distance * 0.7 + (10.0 - graph_result.shared_actors_count::int) * 0.3) as hybrid_score
FROM vector_similar_movies vsm
CROSS JOIN LATERAL (
    SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
        MATCH (target:Movie {movie_id: $movie_id})
        MATCH (target)<-[:ACTED_IN]-(actor:Person)-[:ACTED_IN]->(recommended:Movie)
        WHERE recommended.movie_id <> $movie_id
        WITH recommended, count(DISTINCT actor) as shared_actors_count
        WHERE shared_actors_count >= 1
        RETURN recommended.title, shared_actors_count
        ORDER BY shared_actors_count DESC
        LIMIT 1
    $$, json_build_object('movie_id', vsm.movie_id)) as (movie_title agtype, shared_actors_count agtype)
) graph_result
ORDER BY hybrid_score ASC
LIMIT 10;

-- Query 12: User preference analysis with graph context
-- Combine user embedding similarity with their rating graph patterns
WITH similar_users AS (
    SELECT 
        u.user_id,
        (u.embedding <=> (SELECT embedding FROM users WHERE user_id = 1 LIMIT 1)) as user_similarity
    FROM users u
    WHERE u.embedding IS NOT NULL 
        AND u.user_id != 1
    ORDER BY user_similarity
    LIMIT 10
)
SELECT 
    su.user_id,
    su.user_similarity,
    graph_result.avg_rating::numeric as avg_rating,
    graph_result.genre_diversity::int as genre_diversity,
    graph_result.total_ratings::int as total_ratings
FROM similar_users su
CROSS JOIN LATERAL (
    SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
        MATCH (u:User {user_id: $user_id})-[r:RATED]->(m:Movie)-[:HAS_GENRE]->(g:Genre)
        WITH u, avg(r.rating) as avg_rating, count(DISTINCT g) as genre_diversity, count(r) as total_ratings
        RETURN avg_rating, genre_diversity, total_ratings
    $$, json_build_object('user_id', su.user_id)) as (avg_rating agtype, genre_diversity agtype, total_ratings agtype)
) graph_result
ORDER BY user_similarity, graph_result.avg_rating::numeric DESC;

-- Query 13: Content-based filtering enhanced with cast network analysis
-- Find movies similar in content and cast network structure
WITH content_candidates AS (
    SELECT 
        m.movie_id,
        m.title,
        m.vote_average,
        (m.embedding <=> (SELECT embedding FROM movies WHERE title ILIKE '%Godfather%' LIMIT 1)) as content_similarity
    FROM movies m
    WHERE m.embedding IS NOT NULL
        AND m.title NOT ILIKE '%Godfather%'
    ORDER BY content_similarity
    LIMIT 30
)
SELECT 
    cc.title,
    cc.vote_average,
    cc.content_similarity,
    graph_result.cast_network_score::numeric as cast_network_score,
    (cc.content_similarity * 0.6 + graph_result.cast_network_score::numeric * 0.4) as final_score
FROM content_candidates cc
CROSS JOIN LATERAL (
    SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
        MATCH (m:Movie {movie_id: $movie_id})<-[:ACTED_IN]-(actor:Person)
        WITH m, count(actor) as cast_size
        MATCH (m)<-[:ACTED_IN]-(actor:Person)-[:ACTED_IN]->(other:Movie)
        WHERE other.movie_id <> m.movie_id
        WITH m, cast_size, count(DISTINCT other) as connected_movies
        RETURN (connected_movies * 1.0 / cast_size) as cast_network_score
    $$, json_build_object('movie_id', cc.movie_id)) as (cast_network_score agtype)
) graph_result
WHERE graph_result.cast_network_score::numeric > 0
ORDER BY final_score ASC
LIMIT 15;

-- =====================================================
-- PERFORMANCE AND ANALYTICS QUERIES
-- =====================================================

-- Query 14: Vector index performance analysis
-- Analyze the effectiveness of HNSW indexes
EXPLAIN (ANALYZE, BUFFERS) 
SELECT 
    m.title,
    (m.embedding <=> (SELECT embedding FROM movies WHERE movie_id = 862 LIMIT 1)) as distance
FROM movies m
WHERE m.embedding IS NOT NULL
ORDER BY distance
LIMIT 10;

-- Query 15: Graph traversal performance analysis
-- Analyze Apache AGE query performance
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
    MATCH (u:User {user_id: 1})-[:RATED]->(m:Movie)<-[:ACTED_IN]-(a:Person)
    RETURN count(DISTINCT a) as actors_in_rated_movies
$$) as (actor_count agtype);

-- Query 16: Data quality and coverage analysis
-- Analyze embedding coverage and data completeness
SELECT 
    'Movies' as entity_type,
    COUNT(*) as total_records,
    COUNT(embedding) as records_with_embeddings,
    ROUND(COUNT(embedding)::numeric / COUNT(*) * 100, 2) as embedding_coverage_pct,
    AVG(array_length(embedding, 1)) as avg_embedding_dimension
FROM movies
UNION ALL
SELECT 
    'Users' as entity_type,
    COUNT(*) as total_records,
    COUNT(embedding) as records_with_embeddings,
    ROUND(COUNT(embedding)::numeric / COUNT(*) * 100, 2) as embedding_coverage_pct,
    AVG(array_length(embedding, 1)) as avg_embedding_dimension
FROM users;

-- Query 17: Graph connectivity analysis
-- Analyze the connectivity and structure of the graph
SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
    MATCH (n)
    WITH labels(n)[0] as node_type, count(n) as node_count
    RETURN node_type, node_count
    ORDER BY node_count DESC
$$) as (node_type agtype, node_count agtype);

-- Query 18: Complex multi-hop recommendation
-- Advanced recommendation using multiple relationship types
SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
    MATCH (target_user:User {user_id: 1})-[:RATED]->(liked:Movie)
    WHERE liked.vote_average >= 7.0
    MATCH (liked)<-[:ACTED_IN]-(actor:Person)-[:ACTED_IN]->(candidate:Movie)
    WHERE NOT EXISTS((target_user)-[:RATED]->(candidate))
    MATCH (candidate)<-[:DIRECTED]-(director:Person)
    WITH candidate, 
         count(DISTINCT actor) as shared_actors,
         collect(DISTINCT director.name) as directors,
         avg(liked.vote_average) as avg_liked_rating
    WHERE shared_actors >= 2
    RETURN candidate.title, 
           shared_actors, 
           directors, 
           candidate.vote_average,
           avg_liked_rating
    ORDER BY shared_actors DESC, candidate.vote_average DESC
    LIMIT 10
$$) as (movie_title agtype, shared_actors agtype, directors agtype, vote_average agtype, avg_liked_rating agtype);

-- =====================================================
-- UTILITY QUERIES FOR DEMO SETUP AND VALIDATION
-- =====================================================

-- Query 19: Validate data loading completeness
SELECT 
    table_name,
    record_count,
    CASE 
        WHEN table_name = 'movies' AND record_count >= 1000 THEN '✓'
        WHEN table_name = 'persons' AND record_count >= 5000 THEN '✓'
        WHEN table_name = 'ratings' AND record_count >= 10000 THEN '✓'
        WHEN table_name = 'movie_cast' AND record_count >= 10000 THEN '✓'
        WHEN table_name = 'movie_crew' AND record_count >= 5000 THEN '✓'
        ELSE '⚠'
    END as status
FROM (
    SELECT 'movies' as table_name, COUNT(*) as record_count FROM movies
    UNION ALL
    SELECT 'persons' as table_name, COUNT(*) as record_count FROM persons
    UNION ALL
    SELECT 'ratings' as table_name, COUNT(*) as record_count FROM ratings
    UNION ALL
    SELECT 'movie_cast' as table_name, COUNT(*) as record_count FROM movie_cast
    UNION ALL
    SELECT 'movie_crew' as table_name, COUNT(*) as record_count FROM movie_crew
    UNION ALL
    SELECT 'keywords' as table_name, COUNT(*) as record_count FROM keywords
    UNION ALL
    SELECT 'movie_keywords' as table_name, COUNT(*) as record_count FROM movie_keywords
) data_summary
ORDER BY record_count DESC;

-- Query 20: Sample data for demo presentation
-- Get interesting sample data to showcase in presentations
WITH sample_movies AS (
    SELECT 
        m.title,
        m.vote_average,
        m.budget,
        m.revenue,
        array_to_string(
            ARRAY(
                SELECT jsonb_array_elements_text(
                    CASE 
                        WHEN jsonb_typeof(m.genres) = 'array' 
                        THEN (SELECT jsonb_agg(genre->>'name') FROM jsonb_array_elements(m.genres) AS genre)
                        ELSE '[]'::jsonb
                    END
                )
            ), ', '
        ) as genres
    FROM movies m
    WHERE m.vote_average >= 8.0 
        AND m.vote_count >= 1000
        AND m.budget > 0
        AND m.revenue > 0
    ORDER BY m.vote_average DESC, m.vote_count DESC
    LIMIT 10
)
SELECT * FROM sample_movies;

