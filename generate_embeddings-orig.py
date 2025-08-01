#!/usr/bin/env python3
"""
Embedding Generator for MovieLens DiskANN Demo

This script generates vector embeddings for users and movies in the MovieLens dataset
to enable similarity search using DiskANN in PostgreSQL.

Usage:
    python generate_embeddings.py <connection_string>

Example:
    python generate_embeddings.py "host=localhost dbname=movielens_demo user=postgres"
"""

import pandas as pd
import psycopg2
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import StandardScaler, LabelEncoder
import sys
import warnings
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

warnings.filterwarnings('ignore')

def connect_to_db(connection_string):
    """Connect to PostgreSQL database"""
    try:
        conn = psycopg2.connect(connection_string)
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        sys.exit(1)

def generate_movie_embeddings(conn):
    """Generate embeddings for movies based on title and genres"""
    logger.info("Generating movie embeddings...")
    
    # Load sentence transformer model
    logger.info("Loading sentence transformer model...")
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
    logger.info(f"Processing {len(movies)} movies...")
    
    # Genre names for text representation
    genre_names = [
        'action', 'adventure', 'animation', 'children', 'comedy', 'crime',
        'documentary', 'drama', 'fantasy', 'film noir', 'horror', 'musical',
        'mystery', 'romance', 'sci-fi', 'thriller', 'war', 'western'
    ]
    
    embeddings_generated = 0
    
    for i, movie in enumerate(movies):
        movie_id = movie[0]
        title = movie[1]
        genres = movie[2:]
        
        # Create genre text representation
        active_genres = [genre_names[j] for j, is_active in enumerate(genres) if is_active]
        genre_text = ' '.join(active_genres) if active_genres else 'general'
        
        # Combine title and genres for embedding
        text_for_embedding = f"{title} {genre_text}"
        
        try:
            # Generate text embedding
            text_embedding = model.encode(text_for_embedding)
            
            # Create genre vector (one-hot encoding)
            genre_vector = np.array(genres, dtype=float)
            
            # Combine text and genre embeddings
            # Ensure text embedding is exactly 110 dimensions
            if len(text_embedding) > 110:
                text_embedding = text_embedding[:110]
            else:
                text_embedding = np.pad(text_embedding, (0, 110 - len(text_embedding)))
            
            # Combine with 18-dimensional genre vector
            combined_embedding = np.concatenate([text_embedding, genre_vector])
            
            # Ensure exactly 128 dimensions
            if len(combined_embedding) > 128:
                combined_embedding = combined_embedding[:128]
            else:
                combined_embedding = np.pad(combined_embedding, (0, 128 - len(combined_embedding)))
            
            # Normalize the embedding
            embedding_norm = np.linalg.norm(combined_embedding)
            if embedding_norm > 0:
                combined_embedding = combined_embedding / embedding_norm
            
            # Update movie with embedding
            cursor.execute("""
                UPDATE movies SET embedding = %s WHERE movie_id = %s
            """, (combined_embedding.tolist(), movie_id))
            
            embeddings_generated += 1
            
            if (i + 1) % 100 == 0:
                logger.info(f"Processed {i + 1}/{len(movies)} movies...")
                conn.commit()  # Commit periodically
                
        except Exception as e:
            logger.error(f"Error processing movie {movie_id}: {e}")
            continue
    
    conn.commit()
    cursor.close()
    logger.info(f"Generated embeddings for {embeddings_generated} movies")

def generate_user_embeddings(conn):
    """Generate embeddings for users based on demographics and rating patterns"""
    logger.info("Generating user embeddings...")
    
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
    logger.info(f"Processing {len(users)} users...")
    
    # Get genre preferences for each user
    logger.info("Computing genre preferences...")
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
    occupations = list(set([user[3] for user in users if user[3]]))
    occupation_encoder = LabelEncoder()
    occupation_encoder.fit(occupations)
    
    embeddings_generated = 0
    
    for i, user in enumerate(users):
        user_id, age, gender, occupation, num_ratings, avg_rating, rating_stddev = user
        
        try:
            # Handle None values
            num_ratings = num_ratings or 0
            avg_rating = avg_rating or 2.5
            rating_stddev = rating_stddev or 0
            
            # Create demographic features
            age_normalized = (age - 18) / (73 - 18) if age else 0.5  # Normalize age to 0-1
            gender_encoded = 1.0 if gender == 'M' else 0.0
            
            # Encode occupation
            occupation_encoded = 0
            if occupation and occupation in occupations:
                occupation_encoded = occupation_encoder.transform([occupation])[0] / len(occupations)
            
            # Rating behavior features
            rating_features = np.array([
                min(num_ratings / 100.0, 1.0),  # Normalize number of ratings (cap at 100)
                (avg_rating - 1) / 4,           # Normalize average rating to 0-1
                min(rating_stddev / 2.0, 1.0)   # Normalize rating standard deviation (cap at 2)
            ])
            
            # Genre preferences (18 dimensions)
            genre_pref_vector = np.array(genre_pref_dict.get(user_id, [None] * 18))
            # Replace None with neutral rating (2.5) and normalize
            genre_pref_vector = np.where(
                pd.isna(genre_pref_vector), 
                2.5, 
                genre_pref_vector
            ).astype(float)
            genre_pref_vector = (genre_pref_vector - 1) / 4  # Normalize to 0-1
            
            # Combine all features
            user_features = np.concatenate([
                [age_normalized, gender_encoded, occupation_encoded],  # 3 dimensions
                rating_features,                                       # 3 dimensions
                genre_pref_vector                                      # 18 dimensions
            ])  # Total: 24 dimensions
            
            # Pad to 128 dimensions
            user_embedding = np.pad(user_features, (0, 128 - len(user_features)))
            
            # Normalize the embedding
            embedding_norm = np.linalg.norm(user_embedding)
            if embedding_norm > 0:
                user_embedding = user_embedding / embedding_norm
            
            # Update user with embedding
            cursor.execute("""
                UPDATE users SET embedding = %s WHERE user_id = %s
            """, (user_embedding.tolist(), user_id))
            
            embeddings_generated += 1
            
            if (i + 1) % 100 == 0:
                logger.info(f"Processed {i + 1}/{len(users)} users...")
                conn.commit()  # Commit periodically
                
        except Exception as e:
            logger.error(f"Error processing user {user_id}: {e}")
            continue
    
    conn.commit()
    cursor.close()
    logger.info(f"Generated embeddings for {embeddings_generated} users")

def verify_embeddings(conn):
    """Verify that embeddings have been generated correctly"""
    logger.info("Verifying embeddings...")
    
    cursor = conn.cursor()
    
    # Check movie embeddings
    cursor.execute("""
        SELECT 
            COUNT(*) as total_movies,
            COUNT(embedding) as movies_with_embeddings,
            AVG(array_length(embedding, 1)) as avg_embedding_dim
        FROM movies
    """)
    movie_stats = cursor.fetchone()
    
    # Check user embeddings
    cursor.execute("""
        SELECT 
            COUNT(*) as total_users,
            COUNT(embedding) as users_with_embeddings,
            AVG(array_length(embedding, 1)) as avg_embedding_dim
        FROM users
    """)
    user_stats = cursor.fetchone()
    
    logger.info(f"Movie embeddings: {movie_stats[1]}/{movie_stats[0]} (avg dim: {movie_stats[2]})")
    logger.info(f"User embeddings: {user_stats[1]}/{user_stats[0]} (avg dim: {user_stats[2]})")
    
    # Sample embedding verification
    cursor.execute("""
        SELECT movie_id, array_length(embedding, 1) as dim
        FROM movies 
        WHERE embedding IS NOT NULL 
        LIMIT 3
    """)
    movie_samples = cursor.fetchall()
    logger.info(f"Sample movie embeddings: {movie_samples}")
    
    cursor.execute("""
        SELECT user_id, array_length(embedding, 1) as dim
        FROM users 
        WHERE embedding IS NOT NULL 
        LIMIT 3
    """)
    user_samples = cursor.fetchall()
    logger.info(f"Sample user embeddings: {user_samples}")
    
    cursor.close()

def main():
    if len(sys.argv) != 2:
        print("Usage: python generate_embeddings.py <connection_string>")
        print("Example: python generate_embeddings.py 'host=localhost dbname=movielens_demo user=postgres'")
        sys.exit(1)
    
    connection_string = sys.argv[1]
    
    # Connect to database
    conn = connect_to_db(connection_string)
    
    try:
        # Check if required tables exist
        cursor = conn.cursor()
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name IN ('users', 'movies', 'ratings')
        """)
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        
        if len(tables) != 3:
            logger.error("Required tables (users, movies, ratings) not found. Please run load_movielens_data.py first.")
            sys.exit(1)
        
        # Generate embeddings
        generate_movie_embeddings(conn)
        generate_user_embeddings(conn)
        
        # Verify embeddings
        verify_embeddings(conn)
        
        logger.info("✓ Embedding generation completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Create DiskANN indexes on the embedding columns")
        logger.info("2. Set up Apache AGE graph with the loaded data")
        logger.info("3. Run demo queries to test both DiskANN and AGE functionality")
        
    except Exception as e:
        logger.error(f"Error during embedding generation: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()

