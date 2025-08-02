# Updated Setup Guide - Secure Installation

## Security Notice

This updated setup guide addresses the `joblib` security concern by using a secure set of Python dependencies that avoid the problematic `joblib==1.5.1` version.

## Secure Python Installation

### Step 1: Install Secure Dependencies

Use the provided `requirements_secure.txt` file to install only verified, secure packages:

```bash
pip install -r requirements_secure.txt
```

This will install:
- `psycopg2-binary==2.9.10` - PostgreSQL adapter
- `pandas==2.2.3` - Data manipulation
- `numpy==1.26.4` - Numerical computing
- `transformers==4.45.2` - Hugging Face transformers (for embeddings)
- `torch==2.4.1` - PyTorch (for neural networks)
- `requests==2.32.3` - HTTP library
- `tqdm==4.66.5` - Progress bars

### Step 2: Verify No Problematic Packages

Check that `joblib` is not installed:

```bash
pip list | grep joblib
```

This should return no results.

### Step 3: Use Secure Embedding Generation

Use the `generate_embeddings_secure.py` script instead of the original `generate_embeddings.py`:

```bash
python generate_embeddings_secure.py "host=your-server dbname=movielens_demo user=your-username"
```

## Key Differences in Secure Version

### Removed Dependencies
- ❌ `sentence-transformers` (depends on `joblib`)
- ❌ `scikit-learn` (depends on `joblib`)
- ❌ `joblib` (security concern)

### Secure Alternatives
- ✅ Direct use of `transformers` library for text embeddings
- ✅ Manual implementation of standardization (replacing `sklearn.preprocessing`)
- ✅ Custom normalization functions (replacing `sklearn` utilities)

### Embedding Generation Changes

The secure version:
1. Uses `transformers.AutoTokenizer` and `transformers.AutoModel` directly
2. Implements manual vector normalization
3. Uses hash-based fallback embeddings if model loading fails
4. Maintains the same 128-dimensional output format

## Complete Setup Process

### 1. Database Setup
```sql
-- Run the schema creation script
psql -f create_database_schema.sql
```

### 2. Download MovieLens Dataset
```bash
wget https://files.grouplens.org/datasets/movielens/ml-100k.zip
unzip ml-100k.zip
```

### 3. Install Secure Python Dependencies
```bash
pip install -r requirements_secure.txt
```

### 4. Load Data
```bash
python load_movielens_data.py "host=your-server dbname=movielens_demo user=your-username"
```

### 5. Generate Embeddings (Secure Version)
```bash
python generate_embeddings_secure.py "host=your-server dbname=movielens_demo user=your-username"
```

### 6. Create Vector Indexes
```sql
-- Create HNSW indexes for DiskANN
CREATE INDEX idx_movies_embedding_hnsw 
ON movies USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_users_embedding_hnsw 
ON users USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

### 7. Setup Apache AGE Graph
```bash
python setup_age_graph.py "host=your-server dbname=movielens_demo user=your-username"
```

### 8. Run Demo Queries
```sql
psql -f demo_queries.sql
```

## Security Verification

### Check Installed Packages
```bash
pip list
```

Ensure the following packages are NOT present:
- `joblib`
- `scikit-learn` (unless explicitly needed and using a safe version)
- `sentence-transformers` (replaced with direct `transformers` usage)

### Verify Embedding Quality
After running the secure embedding generation, verify the results:

```sql
-- Check embedding coverage
SELECT 
    'movies' as table_name,
    COUNT(*) as total_records,
    COUNT(embedding) as records_with_embeddings,
    ROUND(COUNT(embedding)::numeric / COUNT(*) * 100, 2) as coverage_pct
FROM movies
UNION ALL
SELECT 
    'users' as table_name,
    COUNT(*) as total_records,
    COUNT(embedding) as records_with_embeddings,
    ROUND(COUNT(embedding)::numeric / COUNT(*) * 100, 2) as coverage_pct
FROM users;
```

Expected results:
- Movies: 100% coverage (1,682 records)
- Users: 100% coverage (943 records)

## Performance Considerations

The secure version may have slightly different performance characteristics:

### Embedding Quality
- Text embeddings use the same pre-trained model (`all-MiniLM-L6-v2`)
- Fallback to hash-based embeddings if model loading fails
- Manual normalization maintains vector quality

### Speed
- Direct `transformers` usage may be slightly slower than `sentence-transformers`
- No impact on database query performance
- Vector similarity search performance remains identical

## Troubleshooting

### If Model Loading Fails
The secure script includes fallback mechanisms:
1. Attempts to load `sentence-transformers/all-MiniLM-L6-v2`
2. Falls back to hash-based embeddings if model unavailable
3. Continues processing with manual feature engineering

### Memory Issues
If you encounter memory issues with the transformer model:
1. The script will automatically fall back to hash-based embeddings
2. Reduce batch processing if needed
3. Consider using a smaller model variant

### Dependency Conflicts
If you need `scikit-learn` for other projects:
```bash
# Install a specific safe version
pip install scikit-learn==1.3.0  # Uses joblib 1.3.x which is safer
```

## Next Steps

After completing the secure setup:
1. Test vector similarity queries using DiskANN
2. Explore graph analytics with Apache AGE
3. Run hybrid queries combining both technologies
4. Monitor performance and optimize as needed

This secure setup provides the same functionality as the original demo while avoiding the `joblib` security concerns.

