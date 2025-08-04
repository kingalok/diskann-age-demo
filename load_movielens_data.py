#!/usr/bin/env python3
"""
MovieLens Data Loader for DiskANN and Apache AGE Demo

This script loads the MovieLens 100K dataset into PostgreSQL tables
optimized for both vector similarity search (DiskANN) and graph analytics (Apache AGE).

Usage:
    python load_movielens_data.py <connection_string>

Example:
    python load_movielens_data.py "host=localhost dbname=movielens_demo user=postgres"
"""

import pandas as pd
import psycopg2
from datetime import datetime
import sys
import os

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
    
    if not os.path.exists(filepath):
        print(f"Error: File {filepath} not found")
        return
    
    # Read the users file
    users_df = pd.read_csv(
        filepath,
        sep='|',
        names=['user_id', 'age', 'gender', 'occupation', 'zip_code'],
        encoding='latin-1'
    )
    
    print(f"Read {len(users_df)} users from file")
    
    # Insert data into users table
    cursor = conn.cursor()
    
    # Clear existing data
    cursor.execute("DELETE FROM users")
    
    for _, row in users_df.iterrows():
        cursor.execute("""
            INSERT INTO users (user_id, age, gender, occupation, zip_code)
            VALUES (%s, %s, %s, %s, %s)
        """, (int(row['user_id']), int(row['age']), str(row['gender']), str(row['occupation']), str(row['zip_code'])))
    
    conn.commit()
    cursor.close()
    print(f"Loaded {len(users_df)} users into database")

def load_movies_data(conn, filepath):
    """Load movies data from u.item file"""
    print("Loading movies data...")
    
    if not os.path.exists(filepath):
        print(f"Error: File {filepath} not found")
        return
    
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
    
    print(f"Read {len(movies_df)} movies from file")
    
    # Genre mapping (excluding 'unknown' genre)
    genre_names = [
        'action', 'adventure', 'animation', 'children', 'comedy', 'crime',
        'documentary', 'drama', 'fantasy', 'film_noir', 'horror', 'musical',
        'mystery', 'romance', 'sci_fi', 'thriller', 'war', 'western'
    ]
    
    cursor = conn.cursor()
    
    # Clear existing data
    cursor.execute("DELETE FROM movies")
    
    for _, row in movies_df.iterrows():
        # Parse release date
        release_date = None
        if pd.notna(row['release_date']) and row['release_date']:
            try:
                release_date = datetime.strptime(row['release_date'], '%d-%b-%Y').date()
            except ValueError:
                # Try alternative date format
                try:
                    release_date = datetime.strptime(row['release_date'], '%Y').date()
                except ValueError:
                    release_date = None
        
        # Prepare genre boolean values (exclude 'unknown' genre at index 18)
        genre_values = [bool(row[f'genre_{i}']) for i in range(18)]
        
        cursor.execute("""
            INSERT INTO movies (
                movie_id, title, release_date, imdb_url,
                genre_action, genre_adventure, genre_animation, genre_children,
                genre_comedy, genre_crime, genre_documentary, genre_drama,
                genre_fantasy, genre_film_noir, genre_horror, genre_musical,
                genre_mystery, genre_romance, genre_sci_fi, genre_thriller,
                genre_war, genre_western
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, [int(row['movie_id']), str(row['title']), release_date, str(row['imdb_url'])] + genre_values)
    
    conn.commit()
    cursor.close()
    print(f"Loaded {len(movies_df)} movies into database")

def load_ratings_data(conn, filepath):
    """Load ratings data from u.data file"""
    print("Loading ratings data...")
    
    if not os.path.exists(filepath):
        print(f"Error: File {filepath} not found")
        return
    
    # Read the ratings file
    ratings_df = pd.read_csv(
        filepath,
        sep='\t',
        names=['user_id', 'movie_id', 'rating', 'timestamp']
    )
    
    print(f"Read {len(ratings_df)} ratings from file")
    
    cursor = conn.cursor()
    
    # Clear existing data
    cursor.execute("DELETE FROM ratings")
    
    # Insert in batches for better performance
    batch_size = 1000
    for i in range(0, len(ratings_df), batch_size):
        batch = ratings_df.iloc[i:i+batch_size]
        
        # Prepare batch insert
        values = []
        for _, row in batch.iterrows():
            values.append((int(row['user_id']), int(row['movie_id']), int(row['rating']), int(row['timestamp'])))
        
        # Execute batch insert
        cursor.executemany("""
            INSERT INTO ratings (user_id, movie_id, rating, timestamp)
            VALUES (%s, %s, %s, %s)
        """, values)
        
        if (i + batch_size) % 10000 == 0:
            print(f"Loaded {i + batch_size} ratings...")
    
    conn.commit()
    cursor.close()
    print(f"Loaded {len(ratings_df)} ratings into database")

def verify_data_load(conn):
    """Verify that data has been loaded correctly"""
    print("\nVerifying data load...")
    
    cursor = conn.cursor()
    
    # Check record counts
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM movies")
    movie_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM ratings")
    rating_count = cursor.fetchone()[0]
    
    print(f"Users: {user_count}")
    print(f"Movies: {movie_count}")
    print(f"Ratings: {rating_count}")
    
    # Check for referential integrity
    cursor.execute("""
        SELECT COUNT(*) FROM ratings r
        LEFT JOIN users u ON r.user_id = u.user_id
        WHERE u.user_id IS NULL
    """)
    orphaned_user_ratings = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM ratings r
        LEFT JOIN movies m ON r.movie_id = m.movie_id
        WHERE m.movie_id IS NULL
    """)
    orphaned_movie_ratings = cursor.fetchone()[0]
    
    if orphaned_user_ratings > 0:
        print(f"Warning: {orphaned_user_ratings} ratings reference non-existent users")
    
    if orphaned_movie_ratings > 0:
        print(f"Warning: {orphaned_movie_ratings} ratings reference non-existent movies")
    
    if orphaned_user_ratings == 0 and orphaned_movie_ratings == 0:
        print("✓ Referential integrity verified")
    
    # Sample data
    print("\nSample data:")
    cursor.execute("SELECT * FROM users LIMIT 3")
    users_sample = cursor.fetchall()
    print("Users sample:", users_sample)
    
    cursor.execute("SELECT movie_id, title FROM movies LIMIT 3")
    movies_sample = cursor.fetchall()
    print("Movies sample:", movies_sample)
    
    cursor.execute("SELECT * FROM ratings LIMIT 3")
    ratings_sample = cursor.fetchall()
    print("Ratings sample:", ratings_sample)
    
    cursor.close()

def main():
    if len(sys.argv) != 2:
        print("Usage: python load_movielens_data.py <connection_string>")
        print("Example: python load_movielens_data.py 'host=localhost dbname=movielens_demo user=postgres'")
        sys.exit(1)
    
    connection_string = sys.argv[1]
    
    # Check if MovieLens data files exist
    data_files = {
        'users': 'ml-100k/u.user',
        'movies': 'ml-100k/u.item',
        'ratings': 'ml-100k/u.data'
    }
    
    missing_files = []
    for name, filepath in data_files.items():
        if not os.path.exists(filepath):
            missing_files.append(filepath)
    
    if missing_files:
        print("Error: The following MovieLens data files are missing:")
        for filepath in missing_files:
            print(f"  - {filepath}")
        print("\nPlease ensure you have downloaded and extracted the MovieLens 100K dataset.")
        print("Download from: https://files.grouplens.org/datasets/movielens/ml-100k.zip")
        sys.exit(1)
    
    # Connect to database
    conn = connect_to_db(connection_string)
    
    try:
        # Load data in order (users and movies first, then ratings)
        load_users_data(conn, data_files['users'])
        load_movies_data(conn, data_files['movies'])
        load_ratings_data(conn, data_files['ratings'])
        
        # Verify the data load
        verify_data_load(conn)
        
        print("\n✓ Data loading completed successfully!")
        print("\nNext steps:")
        print("1. Run generate_embeddings.py to create vector embeddings")
        print("2. Create DiskANN indexes on the embedding columns")
        print("3. Set up Apache AGE graph with the loaded data")
        
    except Exception as e:
        print(f"Error during data loading: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()

