-- =====================================================
-- FIXED APACHE AGE QUERIES
-- Workarounds for ORDER BY and aggregation issues
-- =====================================================

-- Load AGE extension
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- =====================================================
-- WORKING AGE QUERIES (FIXED VERSIONS)
-- =====================================================

-- Query 8 (FIXED): Collaborative filtering using graph traversal
-- Find movies recommended for user 1 based on similar users' preferences
-- Solution: Remove ORDER BY from Cypher query and handle sorting in outer query
WITH recommendations AS (
    SELECT * FROM ag_catalog.cypher('movielens', $$
        MATCH (target:User {user_id: 1})-[r1:RATED]->(m1:Movie)
        WHERE r1.rating >= 4
        MATCH (other:User)-[r2:RATED]->(m1)
        WHERE other.user_id <> 1 AND r2.rating >= 4
        WITH other, count(m1) as common_likes
        WHERE common_likes >= 3
        MATCH (other)-[r3:RATED]->(rec:Movie)
        WHERE r3.rating >= 4 
            AND NOT EXISTS((target)-[:RATED]->(rec))
        RETURN rec.title, count(*) as recommendation_strength, avg(r3.rating) as avg_rating
    $$) as (movie_title agtype, recommendation_strength agtype, avg_rating agtype)
)
SELECT 
    movie_title::text,
    recommendation_strength::int,
    avg_rating::numeric
FROM recommendations
ORDER BY recommendation_strength::int DESC, avg_rating::numeric DESC
LIMIT 10;

-- Query 8 (ALTERNATIVE): Simplified version without aggregation in Cypher
-- This approach avoids complex aggregations that cause issues
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (target:User {user_id: 1})-[r1:RATED]->(m1:Movie)
    WHERE r1.rating >= 4
    MATCH (other:User)-[r2:RATED]->(m1)
    WHERE other.user_id <> 1 AND r2.rating >= 4
    MATCH (other)-[r3:RATED]->(rec:Movie)
    WHERE r3.rating >= 4 
        AND NOT EXISTS((target)-[:RATED]->(rec))
    RETURN DISTINCT rec.title, rec.movie_id
    LIMIT 20
$$) as (movie_title agtype, movie_id agtype);

-- Query 10 (FIXED): Community detection
-- Remove ORDER BY from Cypher and handle in outer query
WITH communities AS (
    SELECT * FROM ag_catalog.cypher('movielens', $$
        MATCH (u1:User)-[r1:RATED]->(m:Movie)<-[r2:RATED]-(u2:User)
        WHERE u1.user_id < u2.user_id 
            AND r1.rating >= 4 
            AND r2.rating >= 4
        WITH u1, u2, count(m) as shared_likes
        WHERE shared_likes >= 5
        RETURN u1.user_id, u2.user_id, shared_likes
    $$) as (user1_id agtype, user2_id agtype, shared_likes agtype)
)
SELECT 
    user1_id::int,
    user2_id::int,
    shared_likes::int
FROM communities
ORDER BY shared_likes::int DESC
LIMIT 20;

-- Query 11 (FIXED): Movie popularity analysis
-- Remove ORDER BY from Cypher and handle in outer query
WITH popularity AS (
    SELECT * FROM ag_catalog.cypher('movielens', $$
        MATCH (u:User)-[r:RATED]->(m:Movie)
        WHERE r.rating >= 4
        RETURN m.movie_id, m.title, count(r) as high_rating_count, avg(r.rating) as avg_rating
    $$) as (movie_id agtype, movie_title agtype, high_rating_count agtype, avg_rating agtype)
)
SELECT 
    movie_id::int,
    movie_title::text,
    high_rating_count::int,
    avg_rating::numeric
FROM popularity
ORDER BY high_rating_count::int DESC
LIMIT 15;

-- Query 12 (FIXED): User influence analysis
-- Remove ORDER BY from Cypher and handle in outer query
WITH influence AS (
    SELECT * FROM ag_catalog.cypher('movielens', $$
        MATCH (influencer:User)-[r1:RATED]->(m:Movie)<-[r2:RATED]-(follower:User)
        WHERE influencer.user_id <> follower.user_id
            AND abs(r1.rating - r2.rating) <= 1
        WITH influencer, count(DISTINCT follower) as influenced_users
        WHERE influenced_users >= 10
        RETURN influencer.user_id, influencer.age, influencer.gender, influenced_users
    $$) as (user_id agtype, age agtype, gender agtype, influenced_users agtype)
)
SELECT 
    user_id::int,
    age::int,
    gender::text,
    influenced_users::int
FROM influence
ORDER BY influenced_users::int DESC
LIMIT 10;

-- =====================================================
-- ALTERNATIVE APPROACHES FOR COMPLEX QUERIES
-- =====================================================

-- Alternative Query 8: Using SQL for aggregation instead of Cypher
-- This approach uses AGE for graph traversal and SQL for aggregation
WITH user_similarities AS (
    SELECT * FROM ag_catalog.cypher('movielens', $$
        MATCH (target:User {user_id: 1})-[r1:RATED]->(m1:Movie)
        WHERE r1.rating >= 4
        MATCH (other:User)-[r2:RATED]->(m1)
        WHERE other.user_id <> 1 AND r2.rating >= 4
        RETURN DISTINCT other.user_id
    $$) as (similar_user_id agtype)
),
similar_user_ratings AS (
    SELECT * FROM ag_catalog.cypher('movielens', $$
        MATCH (u:User)-[r:RATED]->(m:Movie)
        WHERE r.rating >= 4
        RETURN u.user_id, m.movie_id, m.title, r.rating
    $$) as (user_id agtype, movie_id agtype, movie_title agtype, rating agtype)
),
user_1_movies AS (
    SELECT * FROM ag_catalog.cypher('movielens', $$
        MATCH (u:User {user_id: 1})-[r:RATED]->(m:Movie)
        RETURN m.movie_id
    $$) as (movie_id agtype)
)
SELECT 
    sur.movie_title::text,
    COUNT(*) as recommendation_strength,
    AVG(sur.rating::numeric) as avg_rating
FROM user_similarities us
JOIN similar_user_ratings sur ON us.similar_user_id::int = sur.user_id::int
WHERE sur.movie_id::int NOT IN (SELECT movie_id::int FROM user_1_movies)
GROUP BY sur.movie_title::text
HAVING COUNT(*) >= 2
ORDER BY recommendation_strength DESC, avg_rating DESC
LIMIT 10;

-- =====================================================
-- SIMPLE WORKING AGE QUERIES
-- =====================================================

-- Simple Query: Basic user-movie relationships (WORKS)
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (u:User {user_id: 1})-[r:RATED]->(m:Movie)
    RETURN m.title, r.rating
$$) as (movie_title agtype, rating agtype)
LIMIT 10;

-- Simple Query: Find users who rated a specific movie highly (WORKS)
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (u:User)-[r:RATED]->(m:Movie {movie_id: 1})
    WHERE r.rating >= 4
    RETURN u.user_id, u.age, u.gender, r.rating
$$) as (user_id agtype, age agtype, gender agtype, rating agtype)
LIMIT 10;

-- Simple Query: Count relationships (WORKS)
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (u:User)-[r:RATED]->(m:Movie)
    RETURN count(r) as total_ratings
$$) as (total_ratings agtype);

-- Simple Query: Find movies with high average ratings (WORKS)
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (u:User)-[r:RATED]->(m:Movie)
    WHERE r.rating >= 4
    RETURN m.title, count(r) as high_ratings
$$) as (movie_title agtype, high_ratings agtype)
LIMIT 15;

-- =====================================================
-- HYBRID SQL + AGE APPROACH
-- =====================================================

-- Hybrid Query: Use AGE for graph traversal, SQL for complex operations
-- Step 1: Get similar users using AGE
CREATE TEMPORARY TABLE temp_similar_users AS
SELECT user_id::int as similar_user_id
FROM (
    SELECT * FROM ag_catalog.cypher('movielens', $$
        MATCH (target:User {user_id: 1})-[r1:RATED]->(m1:Movie)
        WHERE r1.rating >= 4
        MATCH (other:User)-[r2:RATED]->(m1)
        WHERE other.user_id <> 1 AND r2.rating >= 4
        WITH other, count(m1) as common_likes
        WHERE common_likes >= 3
        RETURN DISTINCT other.user_id
    $$) as (user_id agtype)
) subq;

-- Step 2: Use SQL for recommendation logic
SELECT 
    m.title,
    COUNT(r.rating) as recommendation_strength,
    AVG(r.rating) as avg_rating
FROM temp_similar_users tsu
JOIN ratings r ON tsu.similar_user_id = r.user_id
JOIN movies m ON r.movie_id = m.movie_id
WHERE r.rating >= 4
    AND m.movie_id NOT IN (SELECT movie_id FROM ratings WHERE user_id = 1)
GROUP BY m.movie_id, m.title
HAVING COUNT(r.rating) >= 2
ORDER BY recommendation_strength DESC, avg_rating DESC
LIMIT 10;

-- Clean up
DROP TABLE temp_similar_users;

-- =====================================================
-- DEBUGGING QUERIES
-- =====================================================

-- Debug: Check if graph exists and has data
SELECT * FROM ag_catalog.ag_graph;

-- Debug: Count nodes and relationships
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (n) RETURN labels(n) as node_type, count(n) as count
$$) as (node_type agtype, count agtype);

SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH ()-[r]->() RETURN type(r) as relationship_type, count(r) as count
$$) as (relationship_type agtype, count agtype);

-- Debug: Sample data
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (u:User) RETURN u LIMIT 3
$$) as (user_node agtype);

SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (m:Movie) RETURN m LIMIT 3
$$) as (movie_node agtype);

-- =====================================================
-- PERFORMANCE TIPS
-- =====================================================

-- Tip 1: Use LIMIT in Cypher queries to avoid large result sets
-- Tip 2: Avoid complex ORDER BY within Cypher, use outer SQL instead
-- Tip 3: Use explicit type casting (::int, ::text, ::numeric) when needed
-- Tip 4: Break complex queries into simpler parts using CTEs or temp tables
-- Tip 5: Use DISTINCT to avoid duplicate results in graph traversals

-- =====================================================
-- WORKING QUERY TEMPLATES
-- =====================================================

-- Template 1: Simple pattern matching (ALWAYS WORKS)
/*
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (node1)-[relationship]->(node2)
    WHERE condition
    RETURN node1.property, node2.property, relationship.property
$$) as (col1 agtype, col2 agtype, col3 agtype);
*/

-- Template 2: Aggregation with outer SQL sorting (RECOMMENDED)
/*
WITH results AS (
    SELECT * FROM ag_catalog.cypher('movielens', $$
        MATCH pattern
        RETURN property1, count(*) as count_val, avg(property2) as avg_val
    $$) as (prop1 agtype, count_val agtype, avg_val agtype)
)
SELECT 
    prop1::text,
    count_val::int,
    avg_val::numeric
FROM results
ORDER BY count_val::int DESC;
*/

-- Template 3: Hybrid approach (MOST FLEXIBLE)
/*
-- Step 1: Use AGE for graph traversal
CREATE TEMP TABLE temp_results AS
SELECT column::appropriate_type
FROM (
    SELECT * FROM ag_catalog.cypher('movielens', $$
        MATCH pattern
        RETURN simple_properties
    $$) as (column agtype)
) subq;

-- Step 2: Use SQL for complex operations
SELECT ...
FROM temp_results tr
JOIN regular_tables rt ON ...
WHERE ...
GROUP BY ...
ORDER BY ...;

-- Step 3: Clean up
DROP TABLE temp_results;
*/

