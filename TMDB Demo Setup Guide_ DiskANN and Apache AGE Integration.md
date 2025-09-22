# TMDB Demo Setup Guide: DiskANN and Apache AGE Integration

**Version**: 1.0  
**Last Updated**: December 2024

## Overview

This guide provides step-by-step instructions for setting up the TMDB Movies Dataset demonstration of DiskANN vector similarity search and Apache AGE graph analytics in PostgreSQL Flexible Server. The setup process involves database preparation, data loading, embedding generation, and graph construction.

## Prerequisites

### System Requirements

**Minimum Requirements:**
- 16GB RAM
- 100GB available storage
- Multi-core processor (4+ cores recommended)
- PostgreSQL 14 or later
- Python 3.8 or later

**Recommended Requirements:**
- 32GB RAM
- SSD storage
- 8+ core processor
- GPU with 8GB+ VRAM (for faster embedding generation)

### Software Dependencies

**PostgreSQL Extensions:**
- `vector` extension (for HNSW indexing)
- `age` extension (for graph analytics)

**Python Libraries:**
```bash
pip install psycopg2-binary pandas numpy transformers torch
```

**Note**: Avoid installing `sentence-transformers` or `scikit-learn` if you encounter `joblib` security issues. Use the provided secure embedding generation script instead.

## Step 1: Database Setup

### 1.1 Create Database

```sql
-- Connect to PostgreSQL as superuser
CREATE DATABASE tmdb_demo;
\c tmdb_demo;
```

### 1.2 Install Extensions

```sql
-- Install required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS age;

-- Load AGE into the session
LOAD 'age';

-- Set search path
SET search_path = ag_catalog, "$user", public;
```

### 1.3 Create Database Schema

Run the provided schema creation script:

```bash
psql -h <your_host> -d tmdb_demo -U <your_user> -f create_tmdb_schema.sql
```

This script creates:
- Core tables (movies, persons, users, etc.)
- Relationship tables (movie_cast, movie_crew, ratings, etc.)
- HNSW indexes for vector similarity search
- Apache AGE graph setup

## Step 2: Data Acquisition

### 2.1 Download TMDB Dataset

1. Visit the Kaggle dataset page: https://www.kaggle.com/datasets/rounakbanik/the-movies-dataset
2. Download the dataset (requires Kaggle account)
3. Extract the ZIP file to your working directory

**Required Files:**
- `movies_metadata.csv`
- `credits.csv`
- `keywords.csv`
- `ratings.csv` (optional, for user ratings)

### 2.2 Verify Data Files

Ensure the following files are in your working directory:
```bash
ls -la *.csv
# Should show:
# movies_metadata.csv
# credits.csv
# keywords.csv
# ratings.csv (if using ratings data)
```

## Step 3: Data Loading

### 3.1 Load Core Data

Run the data loading script:

```bash
python load_tmdb_data.py "host=<your_host> dbname=tmdb_demo user=<your_user> password=<your_password>"
```

**Optional Parameters:**
- `--sample-size N`: Load only N movies (for testing)
- `--batch-size N`: Set batch size for processing (default: 1000)

**Example with sampling:**
```bash
python load_tmdb_data.py "host=localhost dbname=tmdb_demo user=postgres password=mypassword" --sample-size 5000
```

### 3.2 Verify Data Loading

Check that data was loaded correctly:

```sql
-- Check record counts
SELECT 'movies' as table_name, COUNT(*) as record_count FROM movies
UNION ALL
SELECT 'persons' as table_name, COUNT(*) as record_count FROM persons
UNION ALL
SELECT 'movie_cast' as table_name, COUNT(*) as record_count FROM movie_cast
UNION ALL
SELECT 'movie_crew' as table_name, COUNT(*) as record_count FROM movie_crew;
```

Expected results for full dataset:
- movies: ~45,000 records
- persons: ~200,000+ records
- movie_cast: ~400,000+ records
- movie_crew: ~300,000+ records

## Step 4: Embedding Generation

### 4.1 Generate Movie and User Embeddings

Run the embedding generation script:

```bash
python generate_tmdb_embeddings.py "host=<your_host> dbname=tmdb_demo user=<your_user> password=<your_password>"
```

**Optional Parameters:**
- `--batch-size N`: Set batch size (default: 100)
- `--model-name MODEL`: Specify transformer model (default: all-MiniLM-L6-v2)

**Example:**
```bash
python generate_tmdb_embeddings.py "host=localhost dbname=tmdb_demo user=postgres password=mypassword" --batch-size 50
```

### 4.2 Monitor Progress

The script provides progress updates:
```
2024-12-XX XX:XX:XX - INFO - Loading model: all-MiniLM-L6-v2
2024-12-XX XX:XX:XX - INFO - Model loaded successfully on device: cpu
2024-12-XX XX:XX:XX - INFO - Generating movie embeddings...
2024-12-XX XX:XX:XX - INFO - Found 45000 movies without embeddings
2024-12-XX XX:XX:XX - INFO - Processed 1000/45000 movies
...
```

### 4.3 Verify Embeddings

Check embedding generation results:

```sql
-- Check embedding coverage
SELECT 
    'Movies' as entity_type,
    COUNT(*) as total_records,
    COUNT(embedding) as records_with_embeddings,
    ROUND(COUNT(embedding)::numeric / COUNT(*) * 100, 2) as coverage_pct
FROM movies
UNION ALL
SELECT 
    'Users' as entity_type,
    COUNT(*) as total_records,
    COUNT(embedding) as records_with_embeddings,
    ROUND(COUNT(embedding)::numeric / COUNT(*) * 100, 2) as coverage_pct
FROM users;
```

Expected coverage: >95% for both movies and users.

## Step 5: Graph Construction

### 5.1 Set Up Apache AGE Graph

Run the graph setup script:

```bash
python setup_tmdb_age_graph.py "host=<your_host> dbname=tmdb_demo user=<your_user> password=<your_password>"
```

**Optional Parameters:**
- `--batch-size N`: Set batch size (default: 1000)
- `--sample-size N`: Limit number of movies (for testing)

### 5.2 Monitor Graph Construction

The script creates nodes and relationships in stages:
```
2024-12-XX XX:XX:XX - INFO - Setting up Apache AGE environment...
2024-12-XX XX:XX:XX - INFO - Creating Movie nodes...
2024-12-XX XX:XX:XX - INFO - Found 45000 movies to create as nodes
2024-12-XX XX:XX:XX - INFO - Created 1000/45000 Movie nodes
...
2024-12-XX XX:XX:XX - INFO - Creating RATED relationships...
2024-12-XX XX:XX:XX - INFO - Found 26000000 ratings to create as relationships
...
```

### 5.3 Verify Graph Creation

Check graph structure:

```sql
-- Count nodes by type
SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
    MATCH (n)
    WITH labels(n)[0] as node_type, count(n) as node_count
    RETURN node_type, node_count
    ORDER BY node_count DESC
$$) as (node_type agtype, node_count agtype);

-- Count relationships by type
SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
    MATCH ()-[r]->()
    WITH type(r) as rel_type, count(r) as rel_count
    RETURN rel_type, rel_count
    ORDER BY rel_count DESC
$$) as (rel_type agtype, rel_count agtype);
```

## Step 6: Testing and Validation

### 6.1 Test Vector Similarity Search

Run a simple similarity query:

```sql
-- Find movies similar to "Toy Story"
WITH target_movie AS (
    SELECT embedding 
    FROM movies 
    WHERE title ILIKE '%Toy Story%' 
    LIMIT 1
)
SELECT 
    m.title,
    m.vote_average,
    (m.embedding <=> t.embedding) as similarity_distance
FROM movies m, target_movie t
WHERE m.embedding IS NOT NULL 
    AND t.embedding IS NOT NULL
    AND m.title NOT ILIKE '%Toy Story%'
ORDER BY m.embedding <=> t.embedding
LIMIT 10;
```

### 6.2 Test Graph Analytics

Run a simple graph query:

```sql
-- Find actors who worked together in multiple movies
SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
    MATCH (a1:Person)-[:ACTED_IN]->(m1:Movie)<-[:ACTED_IN]-(a2:Person)
    WHERE a1.person_id < a2.person_id
    WITH a1, a2, count(m1) as movies_together
    WHERE movies_together >= 3
    RETURN a1.name, a2.name, movies_together
    ORDER BY movies_together DESC
    LIMIT 10
$$) as (actor1 agtype, actor2 agtype, movies_together agtype);
```

### 6.3 Test Hybrid Queries

Run a hybrid vector-graph query:

```sql
-- Enhanced recommendations combining similarity and graph data
WITH vector_similar_movies AS (
    SELECT 
        m.movie_id,
        m.title,
        (m.embedding <=> (SELECT embedding FROM movies WHERE title ILIKE '%Matrix%' LIMIT 1)) as similarity_distance
    FROM movies m
    WHERE m.embedding IS NOT NULL
        AND m.title NOT ILIKE '%Matrix%'
    ORDER BY similarity_distance
    LIMIT 20
)
SELECT 
    vsm.title,
    vsm.similarity_distance,
    graph_result.shared_actors_count::int as shared_actors
FROM vector_similar_movies vsm
CROSS JOIN LATERAL (
    SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
        MATCH (target:Movie)
        WHERE target.title CONTAINS 'Matrix'
        MATCH (target)<-[:ACTED_IN]-(actor:Person)-[:ACTED_IN]->(candidate:Movie {movie_id: $movie_id})
        RETURN count(DISTINCT actor) as shared_actors_count
    $$, json_build_object('movie_id', vsm.movie_id)) as (shared_actors_count agtype)
) graph_result
ORDER BY vsm.similarity_distance
LIMIT 10;
```

## Step 7: Performance Optimization

### 7.1 Create Additional Indexes

For better query performance, create additional indexes:

```sql
-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_movies_vote_average ON movies(vote_average);
CREATE INDEX IF NOT EXISTS idx_movies_release_date ON movies(release_date);
CREATE INDEX IF NOT EXISTS idx_ratings_user_movie ON ratings(user_id, movie_id);
CREATE INDEX IF NOT EXISTS idx_ratings_rating ON ratings(rating);

-- GIN indexes for JSON columns
CREATE INDEX IF NOT EXISTS idx_movies_genres_gin ON movies USING gin(genres);
```

### 7.2 Optimize PostgreSQL Configuration

Add to `postgresql.conf`:

```ini
# Memory settings
shared_buffers = 4GB                    # 25% of RAM
work_mem = 256MB                        # For sorting and hashing
maintenance_work_mem = 1GB              # For index creation

# Vector extension settings
vector.hnsw_ef_search = 40              # Search accuracy vs speed

# AGE settings
age.graph_path = '/path/to/graph/data'  # Optional: custom graph storage
```

Restart PostgreSQL after configuration changes.

### 7.3 Monitor Performance

Use the provided performance queries:

```sql
-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE idx_scan > 0
ORDER BY idx_scan DESC;

-- Check query performance
EXPLAIN (ANALYZE, BUFFERS) 
SELECT m.title, (m.embedding <=> (SELECT embedding FROM movies WHERE movie_id = 862)) as distance
FROM movies m
WHERE m.embedding IS NOT NULL
ORDER BY distance
LIMIT 10;
```

## Troubleshooting

### Common Issues

**1. Extension Installation Errors**
```
ERROR: extension "vector" is not available
```
**Solution**: Install the pgvector extension:
```bash
# Ubuntu/Debian
sudo apt install postgresql-14-pgvector

# Or compile from source
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

**2. Memory Issues During Embedding Generation**
```
RuntimeError: CUDA out of memory
```
**Solution**: Reduce batch size or use CPU-only processing:
```bash
python generate_tmdb_embeddings.py "connection_string" --batch-size 10
```

**3. Graph Query Errors**
```
ERROR: graph "tmdb_movies" does not exist
```
**Solution**: Ensure AGE extension is loaded and graph is created:
```sql
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
SELECT ag_catalog.create_graph('tmdb_movies');
```

**4. Slow Query Performance**
**Solution**: Check index usage and optimize queries:
```sql
-- Check if HNSW index is being used
EXPLAIN (ANALYZE, BUFFERS) 
SELECT * FROM movies ORDER BY embedding <=> '[0,0,0,...]' LIMIT 10;
```

### Performance Tuning

**For Large Datasets:**
- Increase `work_mem` and `shared_buffers`
- Use SSD storage for better I/O performance
- Consider partitioning large tables
- Use connection pooling for high-concurrency applications

**For Better Accuracy:**
- Increase HNSW `ef_construction` parameter during index creation
- Increase `ef_search` parameter for queries
- Use higher-dimensional embeddings (trade-off with performance)

## Next Steps

After successful setup:

1. **Explore Demo Queries**: Run the queries in `tmdb_demo_queries.sql`
2. **Customize for Your Use Case**: Adapt the schema and queries for your specific requirements
3. **Scale Up**: Consider distributed deployment for larger datasets
4. **Monitor and Optimize**: Use PostgreSQL monitoring tools to optimize performance

## Support and Resources

- **PostgreSQL Documentation**: https://www.postgresql.org/docs/
- **Apache AGE Documentation**: https://age.apache.org/
- **pgvector Documentation**: https://github.com/pgvector/pgvector
- **TMDB Dataset**: https://www.kaggle.com/datasets/rounakbanik/the-movies-dataset

For additional support, refer to the comprehensive documentation in `tmdb_demo_documentation.md`.

