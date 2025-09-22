#!/usr/bin/env python3
"""
TMDB Movies Data Loader for DiskANN and Apache AGE Demo

This script loads 'The Movies Dataset' from Kaggle into PostgreSQL tables
optimized for both vector similarity search (DiskANN) and graph analytics (Apache AGE).

Dataset: https://www.kaggle.com/datasets/rounakbanik/the-movies-dataset

Required files:
- movies_metadata.csv
- credits.csv  
- keywords.csv
- ratings.csv (subset for demo)

Usage:
    python load_tmdb_data.py <connection_string> [--sample-size N]

Example:
    python load_tmdb_data.py "host=localhost dbname=tmdb_demo user=postgres" --sample-size 5000
"""

import pandas as pd
import psycopg2
import psycopg2.extras
import json
import sys
import os
import argparse
from datetime import datetime
import logging
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TMDBDataLoader:
    def __init__(self, connection_string: str, sample_size: Optional[int] = None):
        self.connection_string = connection_string
        self.sample_size = sample_size
        self.conn = None
        
    def connect_to_db(self):
        """Connect to PostgreSQL database"""
        try:
            self.conn = psycopg2.connect(self.connection_string)
            self.conn.autocommit = False
            logger.info("Connected to database successfully")
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            sys.exit(1)
    
    def close_connection(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def safe_json_loads(self, json_str: str) -> List[Dict]:
        """Safely parse JSON string, return empty list if invalid"""
        if pd.isna(json_str) or not json_str or json_str == '[]':
            return []
        try:
            # Fix common JSON formatting issues
            json_str = json_str.replace("'", '"')
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return []
    
    def safe_int(self, value) -> Optional[int]:
        """Safely convert value to int, return None if invalid"""
        if pd.isna(value):
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None
    
    def safe_float(self, value) -> Optional[float]:
        """Safely convert value to float, return None if invalid"""
        if pd.isna(value):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def safe_date(self, date_str: str) -> Optional[str]:
        """Safely parse date string, return None if invalid"""
        if pd.isna(date_str) or not date_str:
            return None
        try:
            # Try different date formats
            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y']:
                try:
                    parsed_date = datetime.strptime(date_str, fmt)
                    return parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    continue
            return None
        except Exception:
            return None
    
    def load_movies_data(self, filepath: str):
        """Load movies data from movies_metadata.csv"""
        logger.info("Loading movies data...")
        
        if not os.path.exists(filepath):
            logger.error(f"File {filepath} not found")
            return
        
        try:
            # Read the movies file with error handling
            movies_df = pd.read_csv(filepath, low_memory=False)
            logger.info(f"Read {len(movies_df)} movies from file")
            
            # Apply sampling if specified
            if self.sample_size and len(movies_df) > self.sample_size:
                movies_df = movies_df.sample(n=self.sample_size, random_state=42)
                logger.info(f"Sampled {len(movies_df)} movies for demo")
            
            # Clean and prepare data
            movies_df = movies_df.dropna(subset=['id'])  # Remove rows without movie ID
            movies_df['id'] = movies_df['id'].apply(self.safe_int)
            movies_df = movies_df[movies_df['id'].notna()]  # Remove invalid IDs
            
            cursor = self.conn.cursor()
            
            # Clear existing data
            cursor.execute("DELETE FROM movies")
            logger.info("Cleared existing movies data")
            
            batch_size = 1000
            total_inserted = 0
            
            for i in range(0, len(movies_df), batch_size):
                batch = movies_df.iloc[i:i+batch_size]
                values = []
                
                for _, row in batch.iterrows():
                    # Parse JSONB fields
                    genres = self.safe_json_loads(row.get('genres', '[]'))
                    production_companies = self.safe_json_loads(row.get('production_companies', '[]'))
                    production_countries = self.safe_json_loads(row.get('production_countries', '[]'))
                    spoken_languages = self.safe_json_loads(row.get('spoken_languages', '[]'))
                    
                    values.append((
                        self.safe_int(row['id']),  # movie_id
                        str(row.get('imdb_id', ''))[:20] if pd.notna(row.get('imdb_id')) else None,
                        str(row.get('title', ''))[:500] if pd.notna(row.get('title')) else 'Unknown',
                        str(row.get('original_title', ''))[:500] if pd.notna(row.get('original_title')) else None,
                        str(row.get('overview', '')) if pd.notna(row.get('overview')) else None,
                        str(row.get('tagline', '')) if pd.notna(row.get('tagline')) else None,
                        self.safe_date(row.get('release_date')),
                        self.safe_int(row.get('budget')),
                        self.safe_int(row.get('revenue')),
                        self.safe_int(row.get('runtime')),
                        self.safe_float(row.get('vote_average')),
                        self.safe_int(row.get('vote_count')),
                        str(row.get('homepage', ''))[:500] if pd.notna(row.get('homepage')) else None,
                        str(row.get('status', ''))[:50] if pd.notna(row.get('status')) else None,
                        str(row.get('original_language', ''))[:10] if pd.notna(row.get('original_language')) else None,
                        json.dumps(genres) if genres else None,
                        json.dumps(production_companies) if production_companies else None,
                        json.dumps(production_countries) if production_countries else None,
                        json.dumps(spoken_languages) if spoken_languages else None
                    ))
                
                # Execute batch insert
                cursor.executemany("""
                    INSERT INTO movies (
                        movie_id, imdb_id, title, original_title, overview, tagline,
                        release_date, budget, revenue, runtime, vote_average, vote_count,
                        homepage, status, original_language, genres, production_companies,
                        production_countries, spoken_languages
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (movie_id) DO NOTHING
                """, values)
                
                total_inserted += len(values)
                logger.info(f"Inserted batch {i//batch_size + 1}, total: {total_inserted}")
            
            self.conn.commit()
            cursor.close()
            logger.info(f"Successfully loaded {total_inserted} movies into database")
            
        except Exception as e:
            logger.error(f"Error loading movies data: {e}")
            if self.conn:
                self.conn.rollback()
            raise
    
    def load_credits_data(self, filepath: str):
        """Load cast and crew data from credits.csv"""
        logger.info("Loading credits data...")
        
        if not os.path.exists(filepath):
            logger.error(f"File {filepath} not found")
            return
        
        try:
            credits_df = pd.read_csv(filepath)
            logger.info(f"Read {len(credits_df)} credit records from file")
            
            # Get list of movie IDs that exist in our movies table
            cursor = self.conn.cursor()
            cursor.execute("SELECT movie_id FROM movies")
            existing_movie_ids = set(row[0] for row in cursor.fetchall())
            
            # Filter credits to only include movies we have
            credits_df['id'] = credits_df['id'].apply(self.safe_int)
            credits_df = credits_df[credits_df['id'].isin(existing_movie_ids)]
            logger.info(f"Filtered to {len(credits_df)} credits for existing movies")
            
            # Clear existing data
            cursor.execute("DELETE FROM movie_cast")
            cursor.execute("DELETE FROM movie_crew")
            cursor.execute("DELETE FROM persons")
            logger.info("Cleared existing credits data")
            
            # Track unique persons
            persons_dict = {}
            cast_records = []
            crew_records = []
            
            for _, row in credits_df.iterrows():
                movie_id = self.safe_int(row['id'])
                if not movie_id:
                    continue
                
                # Process cast
                cast_data = self.safe_json_loads(row.get('cast', '[]'))
                for cast_member in cast_data:
                    person_id = self.safe_int(cast_member.get('id'))
                    if not person_id:
                        continue
                    
                    # Add person to dictionary
                    if person_id not in persons_dict:
                        persons_dict[person_id] = {
                            'person_id': person_id,
                            'name': str(cast_member.get('name', ''))[:255],
                            'gender': self.safe_int(cast_member.get('gender')),
                            'profile_path': str(cast_member.get('profile_path', ''))[:255] if cast_member.get('profile_path') else None,
                            'known_for_department': 'Acting'
                        }
                    
                    # Add cast record
                    cast_records.append((
                        movie_id,
                        person_id,
                        str(cast_member.get('character', ''))[:500],
                        str(cast_member.get('credit_id', ''))[:50],
                        self.safe_int(cast_member.get('cast_id')),
                        self.safe_int(cast_member.get('order'))
                    ))
                
                # Process crew
                crew_data = self.safe_json_loads(row.get('crew', '[]'))
                for crew_member in crew_data:
                    person_id = self.safe_int(crew_member.get('id'))
                    if not person_id:
                        continue
                    
                    # Add person to dictionary
                    if person_id not in persons_dict:
                        persons_dict[person_id] = {
                            'person_id': person_id,
                            'name': str(crew_member.get('name', ''))[:255],
                            'gender': self.safe_int(crew_member.get('gender')),
                            'profile_path': str(crew_member.get('profile_path', ''))[:255] if crew_member.get('profile_path') else None,
                            'known_for_department': str(crew_member.get('department', ''))[:50]
                        }
                    
                    # Add crew record
                    crew_records.append((
                        movie_id,
                        person_id,
                        str(crew_member.get('department', ''))[:100],
                        str(crew_member.get('job', ''))[:100],
                        str(crew_member.get('credit_id', ''))[:50]
                    ))
            
            # Insert persons
            persons_values = [
                (p['person_id'], p['name'], p['gender'], p['profile_path'], p['known_for_department'])
                for p in persons_dict.values()
            ]
            
            cursor.executemany("""
                INSERT INTO persons (person_id, name, gender, profile_path, known_for_department)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (person_id) DO NOTHING
            """, persons_values)
            
            logger.info(f"Inserted {len(persons_values)} persons")
            
            # Insert cast records in batches
            batch_size = 1000
            for i in range(0, len(cast_records), batch_size):
                batch = cast_records[i:i+batch_size]
                cursor.executemany("""
                    INSERT INTO movie_cast (movie_id, person_id, character, credit_id, cast_id, order_in_credits)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (movie_id, person_id, credit_id) DO NOTHING
                """, batch)
            
            logger.info(f"Inserted {len(cast_records)} cast records")
            
            # Insert crew records in batches
            for i in range(0, len(crew_records), batch_size):
                batch = crew_records[i:i+batch_size]
                cursor.executemany("""
                    INSERT INTO movie_crew (movie_id, person_id, department, job, credit_id)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (movie_id, person_id, credit_id) DO NOTHING
                """, batch)
            
            logger.info(f"Inserted {len(crew_records)} crew records")
            
            self.conn.commit()
            cursor.close()
            
        except Exception as e:
            logger.error(f"Error loading credits data: {e}")
            if self.conn:
                self.conn.rollback()
            raise
    
    def load_keywords_data(self, filepath: str):
        """Load keywords data from keywords.csv"""
        logger.info("Loading keywords data...")
        
        if not os.path.exists(filepath):
            logger.error(f"File {filepath} not found")
            return
        
        try:
            keywords_df = pd.read_csv(filepath)
            logger.info(f"Read {len(keywords_df)} keyword records from file")
            
            # Get list of movie IDs that exist in our movies table
            cursor = self.conn.cursor()
            cursor.execute("SELECT movie_id FROM movies")
            existing_movie_ids = set(row[0] for row in cursor.fetchall())
            
            # Filter keywords to only include movies we have
            keywords_df['id'] = keywords_df['id'].apply(self.safe_int)
            keywords_df = keywords_df[keywords_df['id'].isin(existing_movie_ids)]
            logger.info(f"Filtered to {len(keywords_df)} keyword records for existing movies")
            
            # Clear existing data
            cursor.execute("DELETE FROM movie_keywords")
            cursor.execute("DELETE FROM keywords")
            logger.info("Cleared existing keywords data")
            
            # Track unique keywords
            keywords_dict = {}
            movie_keyword_records = []
            
            for _, row in keywords_df.iterrows():
                movie_id = self.safe_int(row['id'])
                if not movie_id:
                    continue
                
                keywords_data = self.safe_json_loads(row.get('keywords', '[]'))
                for keyword in keywords_data:
                    keyword_id = self.safe_int(keyword.get('id'))
                    keyword_name = str(keyword.get('name', ''))[:255]
                    
                    if not keyword_id or not keyword_name:
                        continue
                    
                    # Add keyword to dictionary
                    if keyword_id not in keywords_dict:
                        keywords_dict[keyword_id] = {
                            'keyword_id': keyword_id,
                            'name': keyword_name
                        }
                    
                    # Add movie-keyword relationship
                    movie_keyword_records.append((movie_id, keyword_id))
            
            # Insert keywords
            keywords_values = [
                (k['keyword_id'], k['name'])
                for k in keywords_dict.values()
            ]
            
            cursor.executemany("""
                INSERT INTO keywords (keyword_id, name)
                VALUES (%s, %s)
                ON CONFLICT (keyword_id) DO NOTHING
            """, keywords_values)
            
            logger.info(f"Inserted {len(keywords_values)} keywords")
            
            # Insert movie-keyword relationships
            cursor.executemany("""
                INSERT INTO movie_keywords (movie_id, keyword_id)
                VALUES (%s, %s)
                ON CONFLICT (movie_id, keyword_id) DO NOTHING
            """, movie_keyword_records)
            
            logger.info(f"Inserted {len(movie_keyword_records)} movie-keyword relationships")
            
            self.conn.commit()
            cursor.close()
            
        except Exception as e:
            logger.error(f"Error loading keywords data: {e}")
            if self.conn:
                self.conn.rollback()
            raise
    
    def load_ratings_data(self, filepath: str, max_ratings: int = 1000000):
        """Load ratings data from ratings.csv (with sampling for demo)"""
        logger.info("Loading ratings data...")
        
        if not os.path.exists(filepath):
            logger.error(f"File {filepath} not found")
            return
        
        try:
            # Read ratings file in chunks to handle large size
            chunk_size = 100000
            ratings_chunks = []
            total_rows = 0
            
            for chunk in pd.read_csv(filepath, chunksize=chunk_size):
                ratings_chunks.append(chunk)
                total_rows += len(chunk)
                if total_rows >= max_ratings:
                    break
            
            ratings_df = pd.concat(ratings_chunks, ignore_index=True)
            if len(ratings_df) > max_ratings:
                ratings_df = ratings_df.sample(n=max_ratings, random_state=42)
            
            logger.info(f"Read {len(ratings_df)} ratings from file")
            
            # Get list of movie IDs that exist in our movies table
            cursor = self.conn.cursor()
            cursor.execute("SELECT movie_id FROM movies")
            existing_movie_ids = set(row[0] for row in cursor.fetchall())
            
            # Filter ratings to only include movies we have
            ratings_df['movieId'] = ratings_df['movieId'].apply(self.safe_int)
            ratings_df = ratings_df[ratings_df['movieId'].isin(existing_movie_ids)]
            logger.info(f"Filtered to {len(ratings_df)} ratings for existing movies")
            
            # Clear existing data
            cursor.execute("DELETE FROM ratings")
            cursor.execute("DELETE FROM users")
            logger.info("Cleared existing ratings and users data")
            
            # Get unique users
            unique_users = ratings_df['userId'].unique()
            user_values = [(int(user_id),) for user_id in unique_users if pd.notna(user_id)]
            
            # Insert users
            cursor.executemany("""
                INSERT INTO users (user_id)
                VALUES (%s)
                ON CONFLICT (user_id) DO NOTHING
            """, user_values)
            
            logger.info(f"Inserted {len(user_values)} users")
            
            # Insert ratings in batches
            batch_size = 1000
            total_inserted = 0
            
            for i in range(0, len(ratings_df), batch_size):
                batch = ratings_df.iloc[i:i+batch_size]
                values = []
                
                for _, row in batch.iterrows():
                    user_id = self.safe_int(row['userId'])
                    movie_id = self.safe_int(row['movieId'])
                    rating = self.safe_float(row['rating'])
                    timestamp = self.safe_int(row['timestamp'])
                    
                    if user_id and movie_id and rating is not None:
                        values.append((user_id, movie_id, rating, timestamp))
                
                if values:
                    cursor.executemany("""
                        INSERT INTO ratings (user_id, movie_id, rating, timestamp)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (user_id, movie_id) DO NOTHING
                    """, values)
                    
                    total_inserted += len(values)
                    logger.info(f"Inserted batch {i//batch_size + 1}, total: {total_inserted}")
            
            self.conn.commit()
            cursor.close()
            logger.info(f"Successfully loaded {total_inserted} ratings into database")
            
        except Exception as e:
            logger.error(f"Error loading ratings data: {e}")
            if self.conn:
                self.conn.rollback()
            raise
    
    def verify_data_load(self):
        """Verify that data has been loaded correctly"""
        logger.info("Verifying data load...")
        
        cursor = self.conn.cursor()
        
        # Check record counts
        tables = ['movies', 'users', 'ratings', 'persons', 'movie_cast', 'movie_crew', 'keywords', 'movie_keywords']
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            logger.info(f"{table}: {count:,} records")
        
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
            logger.warning(f"{orphaned_user_ratings} ratings reference non-existent users")
        
        if orphaned_movie_ratings > 0:
            logger.warning(f"{orphaned_movie_ratings} ratings reference non-existent movies")
        
        if orphaned_user_ratings == 0 and orphaned_movie_ratings == 0:
            logger.info("✓ Referential integrity verified")
        
        # Sample data
        logger.info("Sample data:")
        cursor.execute("SELECT movie_id, title, vote_average FROM movies LIMIT 3")
        movies_sample = cursor.fetchall()
        for movie in movies_sample:
            logger.info(f"Movie: {movie}")
        
        cursor.execute("SELECT user_id FROM users LIMIT 3")
        users_sample = cursor.fetchall()
        for user in users_sample:
            logger.info(f"User: {user}")
        
        cursor.close()

def main():
    parser = argparse.ArgumentParser(description='Load TMDB Movies Dataset into PostgreSQL')
    parser.add_argument('connection_string', help='PostgreSQL connection string')
    parser.add_argument('--sample-size', type=int, help='Number of movies to sample for demo (default: all)')
    parser.add_argument('--max-ratings', type=int, default=1000000, help='Maximum number of ratings to load')
    
    args = parser.parse_args()
    
    # Check if data files exist
    data_files = {
        'movies': 'movies_metadata.csv',
        'credits': 'credits.csv',
        'keywords': 'keywords.csv',
        'ratings': 'ratings.csv'
    }
    
    missing_files = []
    for name, filepath in data_files.items():
        if not os.path.exists(filepath):
            missing_files.append(filepath)
    
    if missing_files:
        logger.error("The following TMDB data files are missing:")
        for filepath in missing_files:
            logger.error(f"  - {filepath}")
        logger.error("\nPlease download 'The Movies Dataset' from:")
        logger.error("https://www.kaggle.com/datasets/rounakbanik/the-movies-dataset")
        sys.exit(1)
    
    # Initialize loader
    loader = TMDBDataLoader(args.connection_string, args.sample_size)
    
    try:
        # Connect to database
        loader.connect_to_db()
        
        # Load data in order
        loader.load_movies_data(data_files['movies'])
        loader.load_credits_data(data_files['credits'])
        loader.load_keywords_data(data_files['keywords'])
        loader.load_ratings_data(data_files['ratings'], args.max_ratings)
        
        # Verify the data load
        loader.verify_data_load()
        
        logger.info("✓ Data loading completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Run generate_tmdb_embeddings.py to create vector embeddings")
        logger.info("2. Create DiskANN indexes on the embedding columns")
        logger.info("3. Set up Apache AGE graph with the loaded data")
        
    except Exception as e:
        logger.error(f"Error during data loading: {e}")
        if loader.conn:
            loader.conn.rollback()
        raise
    finally:
        loader.close_connection()

if __name__ == "__main__":
    main()

