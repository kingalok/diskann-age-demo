#!/usr/bin/env python3
"""
MovieLens 25M Data Loader for DiskANN and Apache AGE Demo

This script loads the MovieLens 25M dataset into PostgreSQL tables
optimized for both vector similarity search (DiskANN) and graph analytics (Apache AGE).

Dataset: https://grouplens.org/datasets/movielens/25m/

Required files:
- movies.csv
- ratings.csv
- tags.csv
- links.csv
- genome-scores.csv
- genome-tags.csv

Usage:
    python load_movielens_25m_data.py <connection_string> [--max-ratings N] [--max-tags N]

Example:
    python load_movielens_25m_data.py "host=localhost dbname=movielens_25m user=postgres" --max-ratings 1000000 --max-tags 100000
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
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class MovieLens25MDataLoader:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
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

    def load_movies_data(self, movies_filepath: str, links_filepath: str):
        """Load movies data from movies.csv and links.csv"""
        logger.info("Loading movies data...")
        
        if not os.path.exists(movies_filepath):
            logger.error(f"File {movies_filepath} not found")
            return
        if not os.path.exists(links_filepath):
            logger.error(f"File {links_filepath} not found")
            return
        
        try:
            movies_df = pd.read_csv(movies_filepath)
            links_df = pd.read_csv(links_filepath)
            logger.info(f"Read {len(movies_df)} movies and {len(links_df)} links from files")
            
            # Merge movies and links dataframes
            movies_df = pd.merge(movies_df, links_df, on=\'movieId\', how=\'left\')
            
            # Rename columns to match schema
            movies_df = movies_df.rename(columns={
                \'movieId\': \'movie_id\',
                \'imdbId\': \'imdb_id\',
                \'tmdbId\': \'tmdb_id\'
            })
            
            # Process genres
            movies_df["genres"] = movies_df["genres"].apply(
                lambda x: x.split("|") if pd.notna(x) and x != "(no genres listed)" else []
            )
            
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
                    values.append((
                        self.safe_int(row["movie_id"]),
                        str(row["title"])[:500] if pd.notna(row["title"]) else "Unknown",
                        row["genres"],
                        str(self.safe_int(row["imdb_id"])) if pd.notna(row["imdb_id"]) else None,
                        self.safe_int(row["tmdb_id"])
                    ))
                
                # Execute batch insert
                cursor.executemany("""
                    INSERT INTO movies (movie_id, title, genres, imdb_id, tmdb_id)
                    VALUES (%s, %s, %s, %s, %s)
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

    def load_ratings_data(self, filepath: str, max_ratings: int = 25000000):
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
            ratings_df["movieId"] = ratings_df["movieId"].apply(self.safe_int)
            ratings_df = ratings_df[ratings_df["movieId"].isin(existing_movie_ids)]
            logger.info(f"Filtered to {len(ratings_df)} ratings for existing movies")
            
            # Clear existing data
            cursor.execute("DELETE FROM ratings")
            cursor.execute("DELETE FROM users")
            logger.info("Cleared existing ratings and users data")
            
            # Get unique users
            unique_users = ratings_df["userId"].unique()
            user_values = [(int(user_id),) for user_id in unique_users if pd.notna(user_id)]
            
            # Insert users
            cursor.executemany("""
                INSERT INTO users (user_id)
                VALUES (%s)
                ON CONFLICT (user_id) DO NOTHING
            """, user_values)
            
            logger.info(f"Inserted {len(user_values)} users")
            
            # Insert ratings in batches
            batch_size = 10000
            total_inserted = 0
            
            for i in range(0, len(ratings_df), batch_size):
                batch = ratings_df.iloc[i:i+batch_size]
                values = []
                
                for _, row in batch.iterrows():
                    user_id = self.safe_int(row["userId"])
                    movie_id = self.safe_int(row["movieId"])
                    rating = self.safe_float(row["rating"])
                    timestamp = self.safe_int(row["timestamp"])
                    
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

    def load_tags_data(self, filepath: str, max_tags: int = 1000000):
        """Load user-applied tags data from tags.csv"""
        logger.info("Loading user-applied tags data...")
        
        if not os.path.exists(filepath):
            logger.error(f"File {filepath} not found")
            return
        
        try:
            tags_df = pd.read_csv(filepath)
            if len(tags_df) > max_tags:
                tags_df = tags_df.sample(n=max_tags, random_state=42)
            logger.info(f"Read {len(tags_df)} user-applied tags from file")
            
            cursor = self.conn.cursor()
            
            # Get list of movie IDs and user IDs that exist in our tables
            cursor.execute("SELECT movie_id FROM movies")
            existing_movie_ids = set(row[0] for row in cursor.fetchall())
            cursor.execute("SELECT user_id FROM users")
            existing_user_ids = set(row[0] for row in cursor.fetchall())
            
            # Filter tags to only include existing movies and users
            tags_df["movieId"] = tags_df["movieId"].apply(self.safe_int)
            tags_df["userId"] = tags_df["userId"].apply(self.safe_int)
            tags_df = tags_df[tags_df["movieId"].isin(existing_movie_ids) & tags_df["userId"].isin(existing_user_ids)]
            logger.info(f"Filtered to {len(tags_df)} user-applied tags for existing movies and users")
            
            # Clear existing data
            cursor.execute("DELETE FROM tags")
            logger.info("Cleared existing user-applied tags data")
            
            batch_size = 10000
            total_inserted = 0
            
            for i in range(0, len(tags_df), batch_size):
                batch = tags_df.iloc[i:i+batch_size]
                values = []
                
                for _, row in batch.iterrows():
                    user_id = self.safe_int(row["userId"])
                    movie_id = self.safe_int(row["movieId"])
                    tag = str(row["tag"])[:255] if pd.notna(row["tag"]) else None
                    timestamp = self.safe_int(row["timestamp"])
                    
                    if user_id and movie_id and tag:
                        values.append((user_id, movie_id, tag, timestamp))
                
                if values:
                    cursor.executemany("""
                        INSERT INTO tags (user_id, movie_id, tag, timestamp)
                        VALUES (%s, %s, %s, %s)
                    """, values)
                    
                    total_inserted += len(values)
                    logger.info(f"Inserted batch {i//batch_size + 1}, total: {total_inserted}")
            
            self.conn.commit()
            cursor.close()
            logger.info(f"Successfully loaded {total_inserted} user-applied tags into database")
            
        except Exception as e:
            logger.error(f"Error loading user-applied tags data: {e}")
            if self.conn:
                self.conn.rollback()
            raise

    def load_genome_data(self, genome_tags_filepath: str, genome_scores_filepath: str):
        """Load Tag Genome data from genome-tags.csv and genome-scores.csv"""
        logger.info("Loading Tag Genome data...")
        
        if not os.path.exists(genome_tags_filepath):
            logger.error(f"File {genome_tags_filepath} not found")
            return
        if not os.path.exists(genome_scores_filepath):
            logger.error(f"File {genome_scores_filepath} not found")
            return
        
        try:
            genome_tags_df = pd.read_csv(genome_tags_filepath)
            genome_scores_df = pd.read_csv(genome_scores_filepath)
            logger.info(f"Read {len(genome_tags_df)} genome tags and {len(genome_scores_df)} genome scores from files")
            
            cursor = self.conn.cursor()
            
            # Clear existing data
            cursor.execute("DELETE FROM genome_scores")
            cursor.execute("DELETE FROM genome_tags")
            logger.info("Cleared existing Tag Genome data")
            
            # Insert genome tags
            genome_tags_values = [
                (self.safe_int(row["tagId"]), str(row["tag"])[:255])
                for _, row in genome_tags_df.iterrows()
                if pd.notna(row["tagId"]) and pd.notna(row["tag"])
            ]
            cursor.executemany("""
                INSERT INTO genome_tags (tag_id, tag)
                VALUES (%s, %s)
                ON CONFLICT (tag_id) DO NOTHING
            """, genome_tags_values)
            logger.info(f"Inserted {len(genome_tags_values)} genome tags")
            
            # Get list of movie IDs that exist in our movies table
            cursor.execute("SELECT movie_id FROM movies")
            existing_movie_ids = set(row[0] for row in cursor.fetchall())
            
            # Filter genome scores to only include movies we have
            genome_scores_df["movieId"] = genome_scores_df["movieId"].apply(self.safe_int)
            genome_scores_df = genome_scores_df[genome_scores_df["movieId"].isin(existing_movie_ids)]
            logger.info(f"Filtered to {len(genome_scores_df)} genome scores for existing movies")
            
            # Insert genome scores in batches
            batch_size = 10000
            total_inserted = 0
            
            for i in range(0, len(genome_scores_df), batch_size):
                batch = genome_scores_df.iloc[i:i+batch_size]
                values = []
                
                for _, row in batch.iterrows():
                    movie_id = self.safe_int(row["movieId"])
                    tag_id = self.safe_int(row["tagId"])
                    relevance = self.safe_float(row["relevance"])
                    
                    if movie_id and tag_id and relevance is not None:
                        values.append((movie_id, tag_id, relevance))
                
                if values:
                    cursor.executemany("""
                        INSERT INTO genome_scores (movie_id, tag_id, relevance)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (movie_id, tag_id) DO NOTHING
                    """, values)
                    
                    total_inserted += len(values)
                    logger.info(f"Inserted batch {i//batch_size + 1}, total: {total_inserted}")
            
            self.conn.commit()
            cursor.close()
            logger.info(f"Successfully loaded {total_inserted} genome scores into database")
            
        except Exception as e:
            logger.error(f"Error loading Tag Genome data: {e}")
            if self.conn:
                self.conn.rollback()
            raise

    def verify_data_load(self):
        """Verify that data has been loaded correctly"""
        logger.info("Verifying data load...")
        
        cursor = self.conn.cursor()
        
        # Check record counts
        tables = ["movies", "users", "ratings", "tags", "genome_tags", "genome_scores"]
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            logger.info(f"{table}: {count:,} records")
        
        # Check for referential integrity (sample checks)
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
            logger.info("✓ Referential integrity verified for ratings")
        
        # Sample data
        logger.info("Sample data:")
        cursor.execute("SELECT movie_id, title, genres FROM movies LIMIT 3")
        movies_sample = cursor.fetchall()
        for movie in movies_sample:
            logger.info(f"Movie: {movie}")
        
        cursor.execute("SELECT user_id FROM users LIMIT 3")
        users_sample = cursor.fetchall()
        for user in users_sample:
            logger.info(f"User: {user}")
        
        cursor.close()

def main():
    parser = argparse.ArgumentParser(description=\'Load MovieLens 25M Dataset into PostgreSQL\')
    parser.add_argument(\'connection_string\', help=\'PostgreSQL connection string\')
    parser.add_argument(\'--max-ratings\', type=int, default=25000000, help=\'Maximum number of ratings to load\')
    parser.add_argument(\'--max-tags\', type=int, default=1000000, help=\'Maximum number of user-applied tags to load\')
    
    args = parser.parse_args()
    
    # Check if data files exist
    data_files = {
        \'movies\': \'movies.csv\',
        \'ratings\': \'ratings.csv\',
        \'tags\': \'tags.csv\',
        \'links\': \'links.csv\',
        \'genome_scores\': \'genome-scores.csv\',
        \'genome_tags\': \'genome-tags.csv\'
    }
    
    missing_files = []
    for name, filepath in data_files.items():
        if not os.path.exists(filepath):
            missing_files.append(filepath)
    
    if missing_files:
        logger.error("The following MovieLens 25M data files are missing:")
        for filepath in missing_files:
            logger.error(f"  - {filepath}")
        logger.error("\nPlease download the MovieLens 25M dataset from:")
        logger.error("https://grouplens.org/datasets/movielens/25m/")
        sys.exit(1)
    
    # Initialize loader
    loader = MovieLens25MDataLoader(args.connection_string)
    
    try:
        # Connect to database
        loader.connect_to_db()
        
        # Load data in order
        loader.load_movies_data(data_files["movies"], data_files["links"])
        loader.load_ratings_data(data_files["ratings"], args.max_ratings)
        loader.load_tags_data(data_files["tags"], args.max_tags)
        loader.load_genome_data(data_files["genome_tags"], data_files["genome_scores"])
        
        # Verify the data load
        loader.verify_data_load()
        
        logger.info("✓ Data loading completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Run generate_movielens_25m_embeddings.py to create vector embeddings")
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

