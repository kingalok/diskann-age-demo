# DiskANN and Apache AGE Demo Package

A comprehensive demonstration of DiskANN vector similarity search and Apache AGE graph analytics using PostgreSQL Flexible Server with the MovieLens dataset.

## Overview

This demo package showcases the powerful combination of:
- **DiskANN**: High-performance vector similarity search for recommendation systems
- **Apache AGE**: Graph database functionality for relationship analysis
- **PostgreSQL Flexible Server**: Unified platform supporting both technologies
- **MovieLens Dataset**: Real-world movie rating data for practical demonstrations

## What's Included

### Documentation
- `README.md` - This comprehensive guide
- `setup_guide.md` - Detailed step-by-step setup instructions
- `demo_plan.md` - Database design and demo scenarios overview
- `architecture_design.md` - Technical architecture documentation

### Database Scripts
- `create_database_schema.sql` - Complete database schema with tables, indexes, and views
- `demo_queries.sql` - Comprehensive collection of demo queries for both DiskANN and AGE

### Python Scripts
- `load_movielens_data.py` - Data ingestion script for MovieLens dataset
- `generate_embeddings.py` - Vector embedding generation for users and movies
- `setup_age_graph.py` - Apache AGE graph setup and population script

## Quick Start

### Prerequisites
- PostgreSQL Flexible Server 15+ with superuser access
- Python 3.8+ with pip
- 8GB+ RAM (16GB recommended)
- 10GB+ available disk space

### Installation Steps

1. **Download MovieLens Dataset**
   ```bash
   wget https://files.grouplens.org/datasets/movielens/ml-100k.zip
   unzip ml-100k.zip
   ```

2. **Create Database and Schema**
   ```sql
   psql -f create_database_schema.sql
   ```

3. **Install Python Dependencies**
   ```bash
   pip install psycopg2-binary pandas numpy scikit-learn sentence-transformers torch
   ```

4. **Load Data**
   ```bash
   python load_movielens_data.py "host=your-server dbname=movielens_demo user=your-username"
   ```

5. **Generate Embeddings**
   ```bash
   python generate_embeddings.py "host=your-server dbname=movielens_demo user=your-username"
   ```

6. **Setup AGE Graph**
   ```bash
   python setup_age_graph.py "host=your-server dbname=movielens_demo user=your-username"
   ```

7. **Run Demo Queries**
   ```sql
   psql -f demo_queries.sql
   ```

## Demo Scenarios

### DiskANN Vector Similarity
- **Movie Recommendations**: Find movies similar to user preferences
- **User Similarity**: Identify users with similar tastes for collaborative filtering
- **Content-Based Filtering**: Discover movies with similar characteristics
- **Performance Testing**: Benchmark vector search performance

### Apache AGE Graph Analytics
- **Relationship Analysis**: Explore user-movie interaction patterns
- **Community Detection**: Find groups of users with similar preferences
- **Collaborative Filtering**: Graph-based recommendation algorithms
- **Path Finding**: Discover connections between movies through users

### Hybrid Approaches
- **Enhanced Recommendations**: Combine vector similarity with graph analytics
- **Multi-Modal Analysis**: Leverage both content and collaborative signals
- **Performance Comparison**: Compare different recommendation approaches

## Key Features Demonstrated

### DiskANN Capabilities
- ✅ High-performance vector similarity search
- ✅ Scalable approximate nearest neighbor (ANN) algorithms
- ✅ Memory-efficient disk-based indexing
- ✅ Support for various distance metrics (cosine, L2)
- ✅ Integration with PostgreSQL's vector extension

### Apache AGE Capabilities
- ✅ Property graph model with nodes and relationships
- ✅ Cypher query language support
- ✅ Graph analytics and traversal algorithms
- ✅ Community detection and influence analysis
- ✅ Seamless integration with PostgreSQL

### Integration Benefits
- ✅ Unified data platform combining relational, vector, and graph data
- ✅ Cross-technology queries leveraging multiple paradigms
- ✅ Consistent ACID transactions across all data types
- ✅ Simplified architecture reducing operational complexity

## Sample Queries

### Find Similar Movies (DiskANN)
```sql
SELECT movie_id, title, similarity_score
FROM get_similar_movies(1, 0.7, 10);
```

### Collaborative Filtering (Apache AGE)
```sql
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (u1:User {user_id: 1})-[r1:RATED]->(m:Movie)<-[r2:RATED]-(u2:User)
    WHERE r1.rating >= 4 AND r2.rating >= 4
    MATCH (u2)-[r3:RATED]->(rec:Movie)
    WHERE r3.rating >= 4 AND NOT EXISTS((u1)-[:RATED]->(rec))
    RETURN rec.title, count(*) as strength
    ORDER BY strength DESC LIMIT 10
$$) as (movie_title agtype, strength agtype);
```

### Hybrid Recommendation
```sql
WITH similar_users AS (
    SELECT user_id FROM get_similar_users(1, 0.8, 20)
)
SELECT m.title, AVG(r.rating) as avg_rating
FROM similar_users su
JOIN ratings r ON su.user_id = r.user_id
JOIN movies m ON r.movie_id = m.movie_id
WHERE r.rating >= 4
GROUP BY m.movie_id, m.title
ORDER BY avg_rating DESC LIMIT 10;
```

## Performance Optimization

### Vector Index Tuning
```sql
-- HNSW parameters for DiskANN
CREATE INDEX idx_movies_embedding_hnsw 
ON movies USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

SET hnsw.ef_search = 40;
```

### Graph Query Optimization
```sql
-- Create indexes for common graph patterns
SELECT * FROM ag_catalog.cypher('movielens', $$
    CREATE INDEX user_id_idx FOR (u:User) ON (u.user_id)
$$) as (result agtype);
```

## Troubleshooting

### Common Issues

**Extension Installation**
```sql
-- Verify extensions
SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector', 'age');
```

**Embedding Generation**
```sql
-- Check embedding coverage
SELECT COUNT(*), COUNT(embedding) FROM movies;
```

**Graph Setup**
```sql
-- Verify graph creation
SELECT * FROM ag_catalog.ag_graph;
```

### Performance Issues
- Increase `shared_buffers` and `effective_cache_size`
- Tune vector index parameters (`ef_search`, `probes`)
- Use `EXPLAIN ANALYZE` to identify bottlenecks
- Consider partitioning for larger datasets

## Dataset Information

### MovieLens 100K Dataset
- **Users**: 943 users with demographic information
- **Movies**: 1,682 movies with genre classifications
- **Ratings**: 100,000 ratings (1-5 scale)
- **Time Period**: 1995-1998
- **Source**: GroupLens Research (University of Minnesota)

### Data Characteristics
- Dense rating matrix (6.3% sparsity)
- Rich metadata for both users and movies
- Temporal rating patterns
- Multiple genre classifications per movie
- Balanced rating distribution

## Architecture Benefits

### Unified Platform
- Single database for all data types
- Consistent backup and recovery procedures
- Unified security and access control
- Simplified operational management

### Performance Advantages
- In-database processing reduces data movement
- Shared memory and caching across workloads
- Optimized query planning across paradigms
- Reduced network latency for complex queries

### Development Efficiency
- Single connection string for all operations
- Consistent transaction semantics
- Unified monitoring and logging
- Simplified application architecture

## Use Cases

### E-commerce
- Product recommendations using content similarity
- Customer segmentation through graph analysis
- Cross-selling optimization via relationship mining
- Personalization engines combining multiple signals

### Social Media
- Friend recommendations using graph connectivity
- Content recommendation via embedding similarity
- Influence analysis through graph centrality
- Community detection for targeted advertising

### Financial Services
- Fraud detection using graph patterns
- Risk assessment via similarity analysis
- Customer lifetime value prediction
- Regulatory compliance through relationship tracking

## Next Steps

### Scaling Considerations
- Horizontal partitioning for larger datasets
- Read replicas for query load distribution
- Connection pooling for high concurrency
- Caching strategies for frequent queries

### Advanced Features
- Real-time embedding updates
- Streaming graph analytics
- Multi-modal embeddings (text, images, audio)
- Federated learning for privacy-preserving recommendations

### Production Deployment
- High availability configuration
- Backup and disaster recovery planning
- Monitoring and alerting setup
- Security hardening and compliance

## Support and Resources

### Documentation
- [PostgreSQL Vector Extension](https://github.com/pgvector/pgvector)
- [Apache AGE Documentation](https://age.apache.org/)
- [MovieLens Dataset](https://grouplens.org/datasets/movielens/)
- [DiskANN Research](https://www.microsoft.com/en-us/research/project/project-akupara-approximate-nearest-neighbor-search-for-large-scale-semantic-search/)

### Community
- PostgreSQL Community Forums
- Apache AGE Mailing Lists
- Vector Database Communities
- Graph Database User Groups

---

**Created by**: Manus AI  
**Version**: 1.0  
**Last Updated**: January 2025

This demo package provides a comprehensive foundation for exploring the powerful combination of vector similarity search and graph analytics in PostgreSQL Flexible Server. The included scripts, documentation, and examples enable both technical evaluation and practical implementation of these advanced database capabilities.

