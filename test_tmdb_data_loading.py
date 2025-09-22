#!/usr/bin/env python3
"""
Test Script for TMDB Data Loading

This script tests the TMDB data loading functionality with sample data
to ensure all components work correctly before processing the full dataset.

Usage:
    python test_tmdb_data_loading.py <connection_string>

Example:
    python test_tmdb_data_loading.py "host=localhost dbname=tmdb_demo user=postgres"
"""

import pandas as pd
import psycopg2
import json
import sys
import os
import logging
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_sample_data():
    """Create sample TMDB data for testing"""
    logger.info("Creating sample TMDB data for testing...")
    
    # Sample movies_metadata.csv
    movies_data = {
        'id': [862, 8844, 15602, 31357, 11862],
        'title': ['Toy Story', 'Jumanji', 'Grumpier Old Men', 'Waiting to Exhale', 'Father of the Bride Part II'],
        'overview': [
            'Led by Woody, Andy\'s toys live happily in his room until Andy\'s birthday brings Buzz Lightyear onto the scene.',
            'When siblings Judy and Peter discover an enchanted board game that opens the door to a magical world, they unwittingly invite Alan -- an adult who\'s been trapped inside the game for 26 years -- into their living room.',
            'A family wedding reignites the ancient feud between next-door neighbors and fishing buddies John and Max.',
            'Cheated on, mistreated and stepped on, the women are holding their breath, waiting for the elusive "good man" to break a string of less-than-stellar lovers.',
            'Just when George Banks has recovered from his daughter\'s wedding, he receives the news that she\'s pregnant... and that his wife is expecting too.'
        ],
        'genres': [
            '[{"id": 16, "name": "Animation"}, {"id": 35, "name": "Comedy"}, {"id": 10751, "name": "Family"}]',
            '[{"id": 12, "name": "Adventure"}, {"id": 10751, "name": "Family"}, {"id": 14, "name": "Fantasy"}]',
            '[{"id": 10749, "name": "Romance"}, {"id": 35, "name": "Comedy"}]',
            '[{"id": 35, "name": "Comedy"}, {"id": 18, "name": "Drama"}, {"id": 10749, "name": "Romance"}]',
            '[{"id": 35, "name": "Comedy"}]'
        ],
        'release_date': ['1995-10-30', '1995-12-15', '1995-12-22', '1995-12-22', '1995-02-10'],
        'budget': [30000000, 65000000, 0, 16000000, 30000000],
        'revenue': [373554033, 262797249, 0, 81452156, 76578911],
        'runtime': [81, 104, 101, 127, 106],
        'vote_average': [7.7, 6.9, 6.5, 6.1, 5.7],
        'vote_count': [5415, 2413, 92, 34, 173],
        'imdb_id': ['tt0114709', 'tt0113497', 'tt0113228', 'tt0114885', 'tt0113041']
    }
    
    movies_df = pd.DataFrame(movies_data)
    movies_df.to_csv('sample_movies_metadata.csv', index=False)
    
    # Sample credits.csv
    credits_data = {
        'id': [862, 8844, 15602, 31357, 11862],
        'cast': [
            '[{"cast_id": 14, "character": "Woody (voice)", "credit_id": "52fe4284c3a36847f8024f95", "gender": 2, "id": 31, "name": "Tom Hanks", "order": 0}, {"cast_id": 15, "character": "Buzz Lightyear (voice)", "credit_id": "52fe4284c3a36847f8024f99", "gender": 2, "id": 12898, "name": "Tim Allen", "order": 1}]',
            '[{"cast_id": 1, "character": "Alan Parrish", "credit_id": "52fe44bfc3a36847f80a7cd1", "gender": 2, "id": 2231, "name": "Robin Williams", "order": 0}, {"cast_id": 2, "character": "Sarah Whittle", "credit_id": "52fe44bfc3a36847f80a7cd5", "gender": 1, "id": 8944, "name": "Bonnie Hunt", "order": 1}]',
            '[{"cast_id": 2, "character": "John Gustafson", "credit_id": "52fe466a9251416c75077a89", "gender": 2, "id": 30, "name": "Walter Matthau", "order": 0}, {"cast_id": 3, "character": "Max Goldman", "credit_id": "52fe466a9251416c75077a8d", "gender": 2, "id": 193, "name": "Jack Lemmon", "order": 1}]',
            '[{"cast_id": 1, "character": "Savannah Jackson", "credit_id": "52fe44779251416c91011acb", "gender": 1, "id": 563, "name": "Whitney Houston", "order": 0}, {"cast_id": 2, "character": "Bernadine Harris", "credit_id": "52fe44779251416c91011acf", "gender": 1, "id": 7624, "name": "Angela Bassett", "order": 1}]',
            '[{"cast_id": 1, "character": "George Banks", "credit_id": "52fe44959251416c75039ed7", "gender": 2, "id": 1532, "name": "Steve Martin", "order": 0}, {"cast_id": 2, "character": "Nina Banks", "credit_id": "52fe44959251416c75039edb", "gender": 1, "id": 1533, "name": "Diane Keaton", "order": 1}]'
        ],
        'crew': [
            '[{"credit_id": "52fe4284c3a36847f8024f49", "department": "Directing", "gender": 2, "id": 7879, "job": "Director", "name": "John Lasseter"}, {"credit_id": "52fe4284c3a36847f8024f4f", "department": "Writing", "gender": 2, "id": 12891, "job": "Screenplay", "name": "Joss Whedon"}]',
            '[{"credit_id": "52fe44bfc3a36847f80a7ce1", "department": "Directing", "gender": 2, "id": 15092, "job": "Director", "name": "Joe Johnston"}, {"credit_id": "52fe44bfc3a36847f80a7ce7", "department": "Writing", "gender": 2, "id": 15093, "job": "Screenplay", "name": "Jonathan Hensleigh"}]',
            '[{"credit_id": "52fe466a9251416c75077a91", "department": "Directing", "gender": 2, "id": 40, "job": "Director", "name": "Howard Deutch"}, {"credit_id": "52fe466a9251416c75077a97", "department": "Writing", "gender": 2, "id": 17825, "job": "Screenplay", "name": "Mark Steven Johnson"}]',
            '[{"credit_id": "52fe44779251416c91011ad3", "department": "Directing", "gender": 2, "id": 9032, "job": "Director", "name": "Forest Whitaker"}, {"credit_id": "52fe44779251416c91011ad9", "department": "Writing", "gender": 1, "id": 12154, "job": "Screenplay", "name": "Terry McMillan"}]',
            '[{"credit_id": "52fe44959251416c75039edf", "department": "Directing", "gender": 2, "id": 4945, "job": "Director", "name": "Charles Shyer"}, {"credit_id": "52fe44959251416c75039ee5", "department": "Writing", "gender": 2, "id": 4945, "job": "Screenplay", "name": "Charles Shyer"}]'
        ]
    }
    
    credits_df = pd.DataFrame(credits_data)
    credits_df.to_csv('sample_credits.csv', index=False)
    
    # Sample keywords.csv
    keywords_data = {
        'id': [862, 8844, 15602, 31357, 11862],
        'keywords': [
            '[{"id": 931, "name": "jealousy"}, {"id": 4290, "name": "toy"}, {"id": 5202, "name": "boy"}, {"id": 6054, "name": "friendship"}, {"id": 9713, "name": "friends"}]',
            '[{"id": 10090, "name": "board game"}, {"id": 10849, "name": "disappearance"}, {"id": 13014, "name": "based on children\'s book"}, {"id": 14796, "name": "fantasy world"}]',
            '[{"id": 1495, "name": "fishing"}, {"id": 12392, "name": "best friend"}, {"id": 179431, "name": "duringcreditsstinger"}]',
            '[{"id": 818, "name": "based on novel"}, {"id": 1009, "name": "divorce"}, {"id": 1523, "name": "husband wife relationship"}]',
            '[{"id": 1009, "name": "divorce"}, {"id": 1523, "name": "husband wife relationship"}, {"id": 2693, "name": "remake"}]'
        ]
    }
    
    keywords_df = pd.DataFrame(keywords_data)
    keywords_df.to_csv('sample_keywords.csv', index=False)
    
    # Sample ratings.csv (smaller subset)
    ratings_data = {
        'userId': [1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4],
        'movieId': [862, 8844, 15602, 862, 31357, 11862, 8844, 15602, 31357, 862, 8844, 11862],
        'rating': [4.0, 3.5, 4.5, 5.0, 3.0, 2.5, 4.0, 4.5, 3.5, 3.5, 4.0, 3.0],
        'timestamp': [964982703, 964981247, 964982224, 964982931, 964981208, 964982176, 964981680, 964982653, 964981855, 964982400, 964981179, 964982588]
    }
    
    ratings_df = pd.DataFrame(ratings_data)
    ratings_df.to_csv('sample_ratings.csv', index=False)
    
    logger.info("Sample data files created successfully!")
    return ['sample_movies_metadata.csv', 'sample_credits.csv', 'sample_keywords.csv', 'sample_ratings.csv']

def test_database_connection(connection_string: str):
    """Test database connection and schema"""
    logger.info("Testing database connection...")
    
    try:
        conn = psycopg2.connect(connection_string)
        cursor = conn.cursor()
        
        # Test if schema exists
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('movies', 'persons', 'movie_cast', 'movie_crew', 'keywords', 'movie_keywords')
        """)
        
        existing_tables = [row[0] for row in cursor.fetchall()]
        logger.info(f"Found existing tables: {existing_tables}")
        
        if len(existing_tables) < 6:
            logger.warning("Not all required tables found. Please run create_tmdb_schema.sql first.")
            return False
        
        cursor.close()
        conn.close()
        logger.info("✓ Database connection and schema validation successful")
        return True
        
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False

def test_data_loading(connection_string: str, sample_files: List[str]):
    """Test data loading with sample data"""
    logger.info("Testing data loading with sample data...")
    
    try:
        # Import the TMDBDataLoader class
        sys.path.append('.')
        from load_tmdb_data import TMDBDataLoader
        
        # Initialize loader with sample size
        loader = TMDBDataLoader(connection_string, sample_size=5)
        loader.connect_to_db()
        
        # Test loading each component
        logger.info("Testing movies data loading...")
        loader.load_movies_data('sample_movies_metadata.csv')
        
        logger.info("Testing credits data loading...")
        loader.load_credits_data('sample_credits.csv')
        
        logger.info("Testing keywords data loading...")
        loader.load_keywords_data('sample_keywords.csv')
        
        logger.info("Testing ratings data loading...")
        loader.load_ratings_data('sample_ratings.csv')
        
        # Verify data was loaded
        loader.verify_data_load()
        
        loader.close_connection()
        logger.info("✓ Data loading test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Data loading test failed: {e}")
        return False

def cleanup_sample_files(sample_files: List[str]):
    """Clean up sample data files"""
    logger.info("Cleaning up sample data files...")
    
    for file in sample_files:
        try:
            if os.path.exists(file):
                os.remove(file)
                logger.info(f"Removed {file}")
        except Exception as e:
            logger.warning(f"Could not remove {file}: {e}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python test_tmdb_data_loading.py <connection_string>")
        print("Example: python test_tmdb_data_loading.py \"host=localhost dbname=tmdb_demo user=postgres\"")
        sys.exit(1)
    
    connection_string = sys.argv[1]
    
    logger.info("Starting TMDB data loading test...")
    
    # Step 1: Create sample data
    sample_files = create_sample_data()
    
    try:
        # Step 2: Test database connection
        if not test_database_connection(connection_string):
            logger.error("Database connection test failed. Exiting.")
            return
        
        # Step 3: Test data loading
        if not test_data_loading(connection_string, sample_files):
            logger.error("Data loading test failed. Exiting.")
            return
        
        logger.info("✓ All tests passed successfully!")
        logger.info("The TMDB data loading system is ready for production use.")
        
    finally:
        # Step 4: Cleanup
        cleanup_sample_files(sample_files)

if __name__ == "__main__":
    main()

