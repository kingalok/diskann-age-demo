# DiskANN and Apache AGE Demo Setup Guide

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [PostgreSQL Flexible Server Setup](#postgresql-flexible-server-setup)
3. [Extension Installation](#extension-installation)
4. [Dataset Download and Preparation](#dataset-download-and-preparation)
5. [Database Schema Creation](#database-schema-creation)
6. [Data Ingestion](#data-ingestion)
7. [Embedding Generation](#embedding-generation)
8. [DiskANN Index Creation](#diskann-index-creation)
9. [Apache AGE Graph Setup](#apache-age-graph-setup)
10. [Demo Queries and Testing](#demo-queries-and-testing)
11. [Troubleshooting](#troubleshooting)

## Prerequisites

Before beginning the setup process, ensure you have the following prerequisites in place:

### System Requirements

- PostgreSQL Flexible Server 15 or later
- Minimum 8GB RAM (16GB recommended for optimal performance)
- At least 10GB available disk space
- Network connectivity for downloading datasets and dependencies

### Software Dependencies

- Python 3.8 or later with pip
- PostgreSQL client tools (psql)
- Git (for cloning repositories if needed)
- curl or wget for downloading datasets

### Required Python Packages

The following Python packages will be installed during the setup process:

```bash
pip install psycopg2-binary pandas numpy scikit-learn sentence-transformers torch
```

### Access Requirements

- Administrative access to PostgreSQL Flexible Server
- Ability to install extensions (requires superuser privileges)
- Network access to download the MovieLens dataset

## PostgreSQL Flexible Server Setup

### Server Configuration

Configure your PostgreSQL Flexible Server with the following recommended settings for optimal performance with DiskANN and Apache AGE:

```sql
-- Memory configuration
ALTER SYSTEM SET shared_buffers = '2GB';
ALTER SYSTEM SET effective_cache_size = '6GB';
ALTER SYSTEM SET maintenance_work_mem = '512MB';
ALTER SYSTEM SET work_mem = '256MB';

-- Vector-specific configuration
ALTER SYSTEM SET max_parallel_workers_per_gather = 4;
ALTER SYSTEM SET max_parallel_workers = 8;

-- Restart required after these changes
SELECT pg_reload_conf();
```

### Connection Setup

Ensure you can connect to your PostgreSQL Flexible Server using the following connection parameters:

```bash
# Example connection string
psql "host=your-server.postgres.database.azure.com port=5432 dbname=postgres user=your-username sslmode=require"
```

Replace the connection parameters with your actual server details.

## Extension Installation

### Installing pgvector

The pgvector extension is required for DiskANN functionality. Install it using the following commands:

```sql
-- Connect as a superuser
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify installation
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### Installing Apache AGE

Apache AGE installation requires specific steps depending on your PostgreSQL version:

```sql
-- Install Apache AGE extension
CREATE EXTENSION IF NOT EXISTS age;

-- Load AGE into the current session
LOAD 'age';

-- Set search path to include AGE
SET search_path = ag_catalog, "$user", public;

-- Verify installation
SELECT * FROM pg_extension WHERE extname = 'age';
```

### Verifying Extension Installation

Run the following query to confirm both extensions are properly installed:

```sql
SELECT 
    extname,
    extversion,
    extrelocatable,
    extschema
FROM pg_extension 
WHERE extname IN ('vector', 'age');
```

## Dataset Download and Preparation

### Downloading MovieLens Dataset

Download the MovieLens 100K dataset, which is ideal for demonstration purposes:

```bash
# Create a working directory
mkdir -p ~/movielens-demo
cd ~/movielens-demo

# Download the MovieLens 100K dataset
wget https://files.grouplens.org/datasets/movielens/ml-100k.zip

# Extract the dataset
unzip ml-100k.zip
cd ml-100k

# Verify the files are present
ls -la
```

The dataset should contain the following key files:
- `u.data`: User ratings data
- `u.item`: Movie information
- `u.user`: User demographic information
- `u.genre`: Genre list
- `u.occupation`: Occupation list

### Understanding the Data Format

#### u.data Format
```
user_id | item_id | rating | timestamp
```

#### u.item Format
```
movie_id | movie_title | release_date | video_release_date | IMDb_URL | [genre_columns]
```

#### u.user Format
```
user_id | age | gender | occupation | zip_code
```

## Database Schema Creation

### Creating the Database

Create a dedicated database for the demo:

```sql
-- Create the demo database
CREATE DATABASE movielens_demo;

-- Connect to the new database
\c movielens_demo;

-- Install extensions in the new database
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
```

### Creating Tables

Execute the following SQL to create the required tables:

```sql
-- Users table with vector embedding support
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    age INTEGER,
    gender CHAR(1),
    occupation VARCHAR(50),
    zip_code VARCHAR(10),
    embedding vector(128)  -- 128-dimensional embedding vector
);

-- Movies table with vector embedding support
CREATE TABLE movies (
    movie_id INTEGER PRIMARY KEY,
    title VARCHAR(255),
    release_date DATE,
    imdb_url VARCHAR(255),
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
    embedding vector(128)  -- 128-dimensional embedding vector
);

-- Ratings table
CREATE TABLE ratings (
    user_id INTEGER REFERENCES users(user_id),
    movie_id INTEGER REFERENCES movies(movie_id),
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    timestamp INTEGER,
    PRIMARY KEY (user_id, movie_id)
);

-- Create indexes for performance
CREATE INDEX idx_ratings_user_id ON ratings(user_id);
CREATE INDEX idx_ratings_movie_id ON ratings(movie_id);
CREATE INDEX idx_ratings_rating ON ratings(rating);
CREATE INDEX idx_users_age ON users(age);
CREATE INDEX idx_users_gender ON users(gender);
CREATE INDEX idx_movies_title ON movies(title);
```

## Data Ingestion

### Preparing Data Ingestion Scripts

Create a Python script to load the MovieLens data into PostgreSQL:

```python
# save as load_movielens_data.py
import pandas as pd
import psycopg2
from datetime import datetime
import sys

def connect_to_db(connection_string):
    """Connect to PostgreSQL database"""
    try:
        conn = psycopg2.connect(connection_string)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)

def load_users_data(conn, filepath):
    """Load users data from u.user file"""
    print("Loading users data...")
    
    # Read the users file
    users_df = pd.read_csv(
        filepath,
        sep='|',
        names=['user_id', 'age', 'gender', 'occupation', 'zip_code'],
        encoding='latin-1'
    )
    
    # Insert data into users table
    cursor = conn.cursor()
    for _, row in users_df.iterrows():
        cursor.execute("""
            INSERT INTO users (user_id, age, gender, occupation, zip_code)
            VALUES (%s, %s, %s, %s, %s)
        """, (row['user_id'], row['age'], row['gender'], row['occupation'], row['zip_code']))
    
    conn.commit()
    cursor.close()
    print(f"Loaded {len(users_df)} users")

def load_movies_data(conn, filepath):
    """Load movies data from u.item file"""
    print("Loading movies data...")
    
    # Define column names for the movies file
    columns = ['movie_id', 'title', 'release_date', 'video_release_date', 'imdb_url'] + \
              [f'genre_{i}' for i in range(19)]
    
    # Read the movies file
    movies_df = pd.read_csv(
        filepath,
        sep='|',
        names=columns,
        encoding='latin-1'
    )
    
    # Genre mapping
    genre_names = [
        'action', 'adventure', 'animation', 'children', 'comedy', 'crime',
        'documentary', 'drama', 'fantasy', 'film_noir', 'horror', 'musical',
        'mystery', 'romance', 'sci_fi', 'thriller', 'war', 'western', 'unknown'
    ]
    
    cursor = conn.cursor()
    for _, row in movies_df.iterrows():
        # Parse release date
        release_date = None
        if pd.notna(row['release_date']) and row['release_date']:
            try:
                release_date = datetime.strptime(row['release_date'], '%d-%b-%Y').date()
            except:
                release_date = None
        
        # Prepare genre boolean values
        genre_values = [bool(row[f'genre_{i}']) for i in range(18)]  # Exclude 'unknown' genre
        
        cursor.execute("""
            INSERT INTO movies (
                movie_id, title, release_date, imdb_url,
                genre_action, genre_adventure, genre_animation, genre_children,
                genre_comedy, genre_crime, genre_documentary, genre_drama,
                genre_fantasy, genre_film_noir, genre_horror, genre_musical,
                genre_mystery, genre_romance, genre_sci_fi, genre_thriller,
                genre_war, genre_western
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, [row['movie_id'], row['title'], release_date, row['imdb_url']] + genre_values)
    
    conn.commit()
    cursor.close()
    print(f"Loaded {len(movies_df)} movies")

def load_ratings_data(conn, filepath):
    """Load ratings data from u.data file"""
    print("Loading ratings data...")
    
    # Read the ratings file
    ratings_df = pd.read_csv(
        filepath,
        sep='\t',
        names=['user_id', 'movie_id', 'rating', 'timestamp']
    )
    
    cursor = conn.cursor()
    for _, row in ratings_df.iterrows():
        cursor.execute("""
            INSERT INTO ratings (user_id, movie_id, rating, timestamp)
            VALUES (%s, %s, %s, %s)
        """, (row['user_id'], row['movie_id'], row['rating'], row['timestamp']))
    
    conn.commit()
    cursor.close()
    print(f"Loaded {len(ratings_df)} ratings")

def main():
    if len(sys.argv) != 2:
        print("Usage: python load_movielens_data.py <connection_string>")
        print("Example: python load_movielens_data.py 'host=localhost dbname=movielens_demo user=postgres'")
        sys.exit(1)
    
    connection_string = sys.argv[1]
    
    # Connect to database
    conn = connect_to_db(connection_string)
    
    try:
        # Load data in order (users and movies first, then ratings)
        load_users_data(conn, 'ml-100k/u.user')
        load_movies_data(conn, 'ml-100k/u.item')
        load_ratings_data(conn, 'ml-100k/u.data')
        
        print("Data loading completed successfully!")
        
    except Exception as e:
        print(f"Error during data loading: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
```

### Running Data Ingestion

Execute the data loading script:

```bash
# Install required Python packages
pip install psycopg2-binary pandas

# Run the data loading script
python load_movielens_data.py "host=your-server.postgres.database.azure.com port=5432 dbname=movielens_demo user=your-username sslmode=require"
```

### Verifying Data Load

Verify that the data has been loaded correctly:

```sql
-- Check record counts
SELECT 'users' as table_name, COUNT(*) as record_count FROM users
UNION ALL
SELECT 'movies' as table_name, COUNT(*) as record_count FROM movies
UNION ALL
SELECT 'ratings' as table_name, COUNT(*) as record_count FROM ratings;

-- Sample data verification
SELECT * FROM users LIMIT 5;
SELECT * FROM movies LIMIT 5;
SELECT * FROM ratings LIMIT 5;
```

Expected results:
- Users: 943 records
- Movies: 1,682 records  
- Ratings: 100,000 records

## Embedding Generation

### Creating Embedding Generation Script

Create a Python script to generate embeddings for users and movies:


```python
# save as generate_embeddings.py
import pandas as pd
import psycopg2
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import StandardScaler
import sys
import warnings
warnings.filterwarnings('ignore')

def connect_to_db(connection_string):
    """Connect to PostgreSQL database"""
    try:
        conn = psycopg2.connect(connection_string)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)

def generate_movie_embeddings(conn):
    """Generate embeddings for movies based on title and genres"""
    print("Generating movie embeddings...")
    
    # Load sentence transformer model
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    cursor = conn.cursor()
    
    # Fetch movie data
    cursor.execute("""
        SELECT movie_id, title, 
               genre_action, genre_adventure, genre_animation, genre_children,
               genre_comedy, genre_crime, genre_documentary, genre_drama,
               genre_fantasy, genre_film_noir, genre_horror, genre_musical,
               genre_mystery, genre_romance, genre_sci_fi, genre_thriller,
               genre_war, genre_western
        FROM movies
        ORDER BY movie_id
    """)
    
    movies = cursor.fetchall()
    
    for movie in movies:
        movie_id = movie[0]
        title = movie[1]
        genres = movie[2:]
        
        # Create genre text representation
        genre_names = [
            'action', 'adventure', 'animation', 'children', 'comedy', 'crime',
            'documentary', 'drama', 'fantasy', 'film noir', 'horror', 'musical',
            'mystery', 'romance', 'sci-fi', 'thriller', 'war', 'western'
        ]
        
        active_genres = [genre_names[i] for i, is_active in enumerate(genres) if is_active]
        genre_text = ' '.join(active_genres) if active_genres else 'general'
        
        # Combine title and genres for embedding
        text_for_embedding = f"{title} {genre_text}"
        
        # Generate text embedding
        text_embedding = model.encode(text_for_embedding)
        
        # Create genre vector (one-hot encoding)
        genre_vector = np.array(genres, dtype=float)
        
        # Combine text and genre embeddings
        # Pad or truncate to ensure consistent dimensionality
        if len(text_embedding) > 110:
            text_embedding = text_embedding[:110]
        else:
            text_embedding = np.pad(text_embedding, (0, 110 - len(text_embedding)))
        
        combined_embedding = np.concatenate([text_embedding, genre_vector])
        
        # Ensure exactly 128 dimensions
        if len(combined_embedding) > 128:
            combined_embedding = combined_embedding[:128]
        else:
            combined_embedding = np.pad(combined_embedding, (0, 128 - len(combined_embedding)))
        
        # Update movie with embedding
        cursor.execute("""
            UPDATE movies SET embedding = %s WHERE movie_id = %s
        """, (combined_embedding.tolist(), movie_id))
    
    conn.commit()
    cursor.close()
    print(f"Generated embeddings for {len(movies)} movies")

def generate_user_embeddings(conn):
    """Generate embeddings for users based on demographics and rating patterns"""
    print("Generating user embeddings...")
    
    cursor = conn.cursor()
    
    # Fetch user data with rating statistics
    cursor.execute("""
        SELECT u.user_id, u.age, u.gender, u.occupation,
               COUNT(r.rating) as num_ratings,
               AVG(r.rating::float) as avg_rating,
               STDDEV(r.rating::float) as rating_stddev
        FROM users u
        LEFT JOIN ratings r ON u.user_id = r.user_id
        GROUP BY u.user_id, u.age, u.gender, u.occupation
        ORDER BY u.user_id
    """)
    
    users = cursor.fetchall()
    
    # Get genre preferences for each user
    cursor.execute("""
        SELECT u.user_id,
               AVG(CASE WHEN m.genre_action THEN r.rating ELSE NULL END) as action_pref,
               AVG(CASE WHEN m.genre_adventure THEN r.rating ELSE NULL END) as adventure_pref,
               AVG(CASE WHEN m.genre_animation THEN r.rating ELSE NULL END) as animation_pref,
               AVG(CASE WHEN m.genre_children THEN r.rating ELSE NULL END) as children_pref,
               AVG(CASE WHEN m.genre_comedy THEN r.rating ELSE NULL END) as comedy_pref,
               AVG(CASE WHEN m.genre_crime THEN r.rating ELSE NULL END) as crime_pref,
               AVG(CASE WHEN m.genre_documentary THEN r.rating ELSE NULL END) as documentary_pref,
               AVG(CASE WHEN m.genre_drama THEN r.rating ELSE NULL END) as drama_pref,
               AVG(CASE WHEN m.genre_fantasy THEN r.rating ELSE NULL END) as fantasy_pref,
               AVG(CASE WHEN m.genre_film_noir THEN r.rating ELSE NULL END) as film_noir_pref,
               AVG(CASE WHEN m.genre_horror THEN r.rating ELSE NULL END) as horror_pref,
               AVG(CASE WHEN m.genre_musical THEN r.rating ELSE NULL END) as musical_pref,
               AVG(CASE WHEN m.genre_mystery THEN r.rating ELSE NULL END) as mystery_pref,
               AVG(CASE WHEN m.genre_romance THEN r.rating ELSE NULL END) as romance_pref,
               AVG(CASE WHEN m.genre_sci_fi THEN r.rating ELSE NULL END) as sci_fi_pref,
               AVG(CASE WHEN m.genre_thriller THEN r.rating ELSE NULL END) as thriller_pref,
               AVG(CASE WHEN m.genre_war THEN r.rating ELSE NULL END) as war_pref,
               AVG(CASE WHEN m.genre_western THEN r.rating ELSE NULL END) as western_pref
        FROM users u
        LEFT JOIN ratings r ON u.user_id = r.user_id
        LEFT JOIN movies m ON r.movie_id = m.movie_id
        GROUP BY u.user_id
        ORDER BY u.user_id
    """)
    
    genre_prefs = cursor.fetchall()
    genre_pref_dict = {row[0]: row[1:] for row in genre_prefs}
    
    # Prepare occupation encoding
    occupations = list(set([user[3] for user in users]))
    occupation_to_idx = {occ: idx for idx, occ in enumerate(occupations)}
    
    for user in users:
        user_id, age, gender, occupation, num_ratings, avg_rating, rating_stddev = user
        
        # Handle None values
        num_ratings = num_ratings or 0
        avg_rating = avg_rating or 2.5
        rating_stddev = rating_stddev or 0
        
        # Create demographic features
        age_normalized = (age - 18) / (73 - 18)  # Normalize age to 0-1
        gender_encoded = 1.0 if gender == 'M' else 0.0
        
        # One-hot encode occupation (simplified to first 20 dimensions)
        occupation_vector = np.zeros(20)
        if occupation in occupation_to_idx and occupation_to_idx[occupation] < 20:
            occupation_vector[occupation_to_idx[occupation]] = 1.0
        
        # Rating behavior features
        rating_features = np.array([
            num_ratings / 100.0,  # Normalize number of ratings
            (avg_rating - 1) / 4,  # Normalize average rating to 0-1
            rating_stddev / 2.0    # Normalize rating standard deviation
        ])
        
        # Genre preferences (18 dimensions)
        genre_pref_vector = np.array(genre_pref_dict.get(user_id, [None] * 18))
        # Replace None with neutral rating (2.5) and normalize
        genre_pref_vector = np.where(
            genre_pref_vector == None, 
            2.5, 
            genre_pref_vector
        ).astype(float)
        genre_pref_vector = (genre_pref_vector - 1) / 4  # Normalize to 0-1
        
        # Combine all features
        user_embedding = np.concatenate([
            [age_normalized, gender_encoded],  # 2 dimensions
            occupation_vector,                 # 20 dimensions
            rating_features,                   # 3 dimensions
            genre_pref_vector                  # 18 dimensions
        ])
        
        # Pad to 128 dimensions
        if len(user_embedding) < 128:
            user_embedding = np.pad(user_embedding, (0, 128 - len(user_embedding)))
        else:
            user_embedding = user_embedding[:128]
        
        # Update user with embedding
        cursor.execute("""
            UPDATE users SET embedding = %s WHERE user_id = %s
        """, (user_embedding.tolist(), user_id))
    
    conn.commit()
    cursor.close()
    print(f"Generated embeddings for {len(users)} users")

def main():
    if len(sys.argv) != 2:
        print("Usage: python generate_embeddings.py <connection_string>")
        sys.exit(1)
    
    connection_string = sys.argv[1]
    
    # Connect to database
    conn = connect_to_db(connection_string)
    
    try:
        generate_movie_embeddings(conn)
        generate_user_embeddings(conn)
        print("Embedding generation completed successfully!")
        
    except Exception as e:
        print(f"Error during embedding generation: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
```

### Running Embedding Generation

Execute the embedding generation script:

```bash
# Install additional required packages
pip install sentence-transformers torch scikit-learn

# Run the embedding generation script
python generate_embeddings.py "host=your-server.postgres.database.azure.com port=5432 dbname=movielens_demo user=your-username sslmode=require"
```

### Verifying Embeddings

Check that embeddings have been generated:

```sql
-- Verify embeddings are present
SELECT 
    COUNT(*) as total_users,
    COUNT(embedding) as users_with_embeddings
FROM users;

SELECT 
    COUNT(*) as total_movies,
    COUNT(embedding) as movies_with_embeddings
FROM movies;

-- Sample embedding data
SELECT user_id, array_length(embedding, 1) as embedding_dimension 
FROM users 
WHERE embedding IS NOT NULL 
LIMIT 5;
```

## DiskANN Index Creation

### Installing pgvectorscale (if available)

If pgvectorscale is available in your environment, install it for DiskANN support:

```sql
-- Install pgvectorscale extension (if available)
CREATE EXTENSION IF NOT EXISTS vectorscale CASCADE;
```

### Creating Vector Indexes

Create appropriate vector indexes for similarity search:

```sql
-- Create HNSW indexes for vector similarity search
-- (DiskANN may require specific index types depending on your PostgreSQL version)

-- Index for movie embeddings
CREATE INDEX idx_movies_embedding_hnsw 
ON movies USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Index for user embeddings  
CREATE INDEX idx_users_embedding_hnsw 
ON users USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Alternative: Create IVFFlat indexes if HNSW is not available
-- CREATE INDEX idx_movies_embedding_ivfflat 
-- ON movies USING ivfflat (embedding vector_cosine_ops) 
-- WITH (lists = 100);

-- CREATE INDEX idx_users_embedding_ivfflat 
-- ON users USING ivfflat (embedding vector_cosine_ops) 
-- WITH (lists = 100);
```

### Optimizing Index Parameters

Adjust index parameters based on your data size and performance requirements:

```sql
-- Set vector search parameters
SET hnsw.ef_search = 40;
SET ivfflat.probes = 10;
```

## Apache AGE Graph Setup

### Creating the Graph

Initialize the Apache AGE graph for the MovieLens data:

```sql
-- Create the graph
SELECT ag_catalog.create_graph('movielens');

-- Set the search path to include AGE
SET search_path = ag_catalog, "$user", public;
```

### Populating Graph Nodes

Create nodes for users and movies:

```sql
-- Create User nodes
SELECT * FROM ag_catalog.cypher('movielens', $$
    LOAD CSV WITH HEADERS FROM 'file:///tmp/users.csv' AS row
    CREATE (u:User {
        user_id: toInteger(row.user_id),
        age: toInteger(row.age),
        gender: row.gender,
        occupation: row.occupation,
        zip_code: row.zip_code
    })
$$) as (result agtype);

-- Alternative: Create User nodes from existing table
DO $$
DECLARE
    user_record RECORD;
BEGIN
    FOR user_record IN SELECT * FROM users LOOP
        PERFORM ag_catalog.cypher('movielens', 
            format('CREATE (u:User {user_id: %s, age: %s, gender: "%s", occupation: "%s", zip_code: "%s"})',
                user_record.user_id,
                user_record.age,
                user_record.gender,
                user_record.occupation,
                user_record.zip_code
            )
        );
    END LOOP;
END $$;

-- Create Movie nodes
DO $$
DECLARE
    movie_record RECORD;
BEGIN
    FOR movie_record IN SELECT movie_id, title FROM movies LOOP
        PERFORM ag_catalog.cypher('movielens', 
            format('CREATE (m:Movie {movie_id: %s, title: "%s"})',
                movie_record.movie_id,
                replace(movie_record.title, '"', '\"')
            )
        );
    END LOOP;
END $$;
```

### Creating Graph Relationships

Create RATED relationships between users and movies:

```sql
-- Create RATED relationships
DO $$
DECLARE
    rating_record RECORD;
BEGIN
    FOR rating_record IN SELECT user_id, movie_id, rating, timestamp FROM ratings LOOP
        PERFORM ag_catalog.cypher('movielens', 
            format('MATCH (u:User {user_id: %s}), (m:Movie {movie_id: %s}) CREATE (u)-[:RATED {rating: %s, timestamp: %s}]->(m)',
                rating_record.user_id,
                rating_record.movie_id,
                rating_record.rating,
                rating_record.timestamp
            )
        );
    END LOOP;
END $$;
```

### Verifying Graph Creation

Verify that the graph has been created correctly:

```sql
-- Count nodes and relationships
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (n) RETURN labels(n) as node_type, count(n) as count
$$) as (node_type agtype, count agtype);

SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH ()-[r]->() RETURN type(r) as relationship_type, count(r) as count
$$) as (relationship_type agtype, count agtype);

-- Sample graph data
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (u:User)-[r:RATED]->(m:Movie) 
    RETURN u.user_id, m.title, r.rating 
    LIMIT 5
$$) as (user_id agtype, movie_title agtype, rating agtype);
```

## Demo Queries and Testing

### DiskANN Similarity Queries

Test vector similarity search functionality:

```sql
-- Find movies similar to a specific movie (e.g., movie_id = 1)
SELECT 
    m2.movie_id,
    m2.title,
    1 - (m1.embedding <=> m2.embedding) as similarity_score
FROM movies m1, movies m2
WHERE m1.movie_id = 1 
    AND m2.movie_id != 1
    AND m1.embedding IS NOT NULL 
    AND m2.embedding IS NOT NULL
ORDER BY m1.embedding <=> m2.embedding
LIMIT 10;

-- Find users similar to a specific user (e.g., user_id = 1)
SELECT 
    u2.user_id,
    u2.age,
    u2.gender,
    u2.occupation,
    1 - (u1.embedding <=> u2.embedding) as similarity_score
FROM users u1, users u2
WHERE u1.user_id = 1 
    AND u2.user_id != 1
    AND u1.embedding IS NOT NULL 
    AND u2.embedding IS NOT NULL
ORDER BY u1.embedding <=> u2.embedding
LIMIT 10;
```

### Apache AGE Graph Queries

Test graph analytics functionality:

```sql
-- Find all movies rated by a specific user
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (u:User {user_id: 1})-[r:RATED]->(m:Movie)
    RETURN m.title, r.rating
    ORDER BY r.rating DESC
$$) as (movie_title agtype, rating agtype);

-- Find users who rated a specific movie highly (rating >= 4)
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (u:User)-[r:RATED]->(m:Movie {movie_id: 1})
    WHERE r.rating >= 4
    RETURN u.user_id, u.age, u.gender, r.rating
$$) as (user_id agtype, age agtype, gender agtype, rating agtype);

-- Collaborative filtering: Find movies liked by similar users
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (u1:User {user_id: 1})-[r1:RATED]->(m1:Movie)
    WHERE r1.rating >= 4
    MATCH (u2:User)-[r2:RATED]->(m1)<-[r3:RATED]-(u2)-[r4:RATED]->(m2:Movie)
    WHERE u2.user_id <> 1 AND r2.rating >= 4 AND r4.rating >= 4
    AND NOT EXISTS((u1)-[:RATED]->(m2))
    RETURN DISTINCT m2.title, count(*) as recommendation_strength
    ORDER BY recommendation_strength DESC
    LIMIT 10
$$) as (movie_title agtype, recommendation_strength agtype);
```

### Performance Testing

Test query performance and optimization:

```sql
-- Enable query timing
\timing on

-- Test vector similarity search performance
EXPLAIN (ANALYZE, BUFFERS) 
SELECT movie_id, title
FROM movies
WHERE embedding IS NOT NULL
ORDER BY embedding <=> (SELECT embedding FROM movies WHERE movie_id = 1)
LIMIT 10;

-- Test graph query performance
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM ag_catalog.cypher('movielens', $$
    MATCH (u:User {user_id: 1})-[r:RATED]->(m:Movie)
    RETURN count(*)
$$) as (count agtype);
```

## Troubleshooting

### Common Issues and Solutions

#### Extension Installation Issues

**Problem**: Extensions fail to install
**Solution**: 
```sql
-- Check available extensions
SELECT * FROM pg_available_extensions WHERE name IN ('vector', 'age');

-- Verify superuser privileges
SELECT current_user, session_user, current_setting('is_superuser');
```

#### Vector Index Creation Issues

**Problem**: Vector indexes fail to create
**Solution**:
```sql
-- Check vector extension version
SELECT extversion FROM pg_extension WHERE extname = 'vector';

-- Verify embedding data
SELECT COUNT(*) FROM movies WHERE embedding IS NOT NULL;
SELECT array_length(embedding, 1) FROM movies WHERE embedding IS NOT NULL LIMIT 1;
```

#### AGE Graph Issues

**Problem**: Graph operations fail
**Solution**:
```sql
-- Verify AGE installation
SELECT ag_catalog.ag_version();

-- Check graph existence
SELECT * FROM ag_catalog.ag_graph;

-- Reset search path
SET search_path = ag_catalog, "$user", public;
```

#### Performance Issues

**Problem**: Queries are slow
**Solution**:
```sql
-- Check index usage
EXPLAIN (ANALYZE, BUFFERS) SELECT ...;

-- Update table statistics
ANALYZE movies;
ANALYZE users;
ANALYZE ratings;

-- Adjust vector search parameters
SET hnsw.ef_search = 100;
```

### Monitoring and Maintenance

#### Regular Maintenance Tasks

```sql
-- Update statistics
ANALYZE;

-- Reindex if necessary
REINDEX INDEX idx_movies_embedding_hnsw;
REINDEX INDEX idx_users_embedding_hnsw;

-- Check index bloat
SELECT schemaname, tablename, attname, n_distinct, correlation 
FROM pg_stats 
WHERE tablename IN ('movies', 'users');
```

#### Performance Monitoring

```sql
-- Monitor query performance
SELECT query, mean_time, calls, total_time
FROM pg_stat_statements
WHERE query LIKE '%embedding%' OR query LIKE '%cypher%'
ORDER BY mean_time DESC;

-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE indexname LIKE '%embedding%';
```

This comprehensive setup guide provides all the necessary steps to create a fully functional demonstration of DiskANN and Apache AGE capabilities using the MovieLens dataset. The setup includes data ingestion, embedding generation, index creation, and sample queries to showcase both technologies working together in PostgreSQL Flexible Server.

