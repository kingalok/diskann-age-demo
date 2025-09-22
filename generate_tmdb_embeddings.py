#!/usr/bin/env python3
"""
TMDB Embeddings Generator for DiskANN and Apache AGE Demo

This script generates vector embeddings for movies and users in the TMDB dataset
using transformer models and various feature engineering techniques.

Usage:
    python generate_tmdb_embeddings.py <connection_string> [--batch-size N] [--model-name MODEL]

Example:
    python generate_tmdb_embeddings.py "host=localhost dbname=tmdb_demo user=postgres" --batch-size 100
"""

import pandas as pd
import psycopg2
import numpy as np
import sys
import os
import argparse
import logging
from typing import Dict, List, Optional, Tuple
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TMDBEmbeddingsGenerator:
    def __init__(self, connection_string: str, model_name: str = "all-MiniLM-L6-v2", batch_size: int = 100):
        self.connection_string = connection_string
        self.model_name = model_name
        self.batch_size = batch_size
        self.conn = None
        self.model = None
        
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
    
    def load_model(self):
        """Load the sentence transformer model"""
        try:
            from transformers import AutoTokenizer, AutoModel
            import torch
            
            logger.info(f"Loading model: {self.model_name}")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModel.from_pretrained(self.model_name)
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            self.model.to(self.device)
            logger.info(f"Model loaded successfully on device: {self.device}")
            
        except ImportError:
            logger.error("Required packages not found. Please install: pip install transformers torch")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            sys.exit(1)
    
    def encode_text(self, texts: List[str]) -> np.ndarray:
        """Encode text using the transformer model"""
        import torch
        
        if not texts:
            return np.array([])
        
        # Clean and prepare texts
        cleaned_texts = []
        for text in texts:
            if text and isinstance(text, str):
                cleaned_texts.append(text.strip()[:512])  # Limit to 512 chars
            else:
                cleaned_texts.append("")
        
        try:
            # Tokenize
            inputs = self.tokenizer(
                cleaned_texts,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors='pt'
            ).to(self.device)
            
            # Generate embeddings
            with torch.no_grad():
                outputs = self.model(**inputs)
                # Use mean pooling
                embeddings = outputs.last_hidden_state.mean(dim=1)
                # Normalize
                embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
            
            return embeddings.cpu().numpy()
            
        except Exception as e:
            logger.error(f"Error encoding text: {e}")
            # Return zero embeddings as fallback
            return np.zeros((len(texts), 384))  # MiniLM-L6-v2 has 384 dimensions
    
    def create_movie_text_features(self, movie_data: Dict) -> str:
        """Create combined text features for a movie"""
        features = []
        
        # Add title
        if movie_data.get('title'):
            features.append(f"Title: {movie_data['title']}")
        
        # Add overview
        if movie_data.get('overview'):
            features.append(f"Overview: {movie_data['overview']}")
        
        # Add tagline
        if movie_data.get('tagline'):
            features.append(f"Tagline: {movie_data['tagline']}")
        
        # Add genres
        if movie_data.get('genres'):
            try:
                genres = json.loads(movie_data['genres']) if isinstance(movie_data['genres'], str) else movie_data['genres']
                if genres:
                    genre_names = [g.get('name', '') for g in genres if isinstance(g, dict)]
                    if genre_names:
                        features.append(f"Genres: {', '.join(genre_names)}")
            except:
                pass
        
        return " | ".join(features) if features else "No description available"
    
    def generate_movie_embeddings(self):
        """Generate embeddings for all movies"""
        logger.info("Generating movie embeddings...")
        
        cursor = self.conn.cursor()
        
        # Get all movies without embeddings
        cursor.execute("""
            SELECT movie_id, title, overview, tagline, genres, 
                   production_companies, production_countries, spoken_languages
            FROM movies 
            WHERE embedding IS NULL
            ORDER BY movie_id
        """)
        
        movies = cursor.fetchall()
        logger.info(f"Found {len(movies)} movies without embeddings")
        
        if not movies:
            logger.info("All movies already have embeddings")
            cursor.close()
            return
        
        # Process in batches
        total_processed = 0
        
        for i in range(0, len(movies), self.batch_size):
            batch = movies[i:i + self.batch_size]
            
            # Create text features for each movie
            movie_texts = []
            movie_ids = []
            
            for movie in batch:
                movie_data = {
                    'title': movie[1],
                    'overview': movie[2],
                    'tagline': movie[3],
                    'genres': movie[4]
                }
                
                text_features = self.create_movie_text_features(movie_data)
                movie_texts.append(text_features)
                movie_ids.append(movie[0])
            
            # Generate embeddings
            embeddings = self.encode_text(movie_texts)
            
            # Update database
            for movie_id, embedding in zip(movie_ids, embeddings):
                # Convert to list for JSON serialization
                embedding_list = embedding.tolist()
                
                cursor.execute("""
                    UPDATE movies 
                    SET embedding = %s 
                    WHERE movie_id = %s
                """, (embedding_list, movie_id))
            
            self.conn.commit()
            total_processed += len(batch)
            logger.info(f"Processed {total_processed}/{len(movies)} movies")
        
        cursor.close()
        logger.info("✓ Movie embeddings generation completed")
    
    def generate_user_embeddings(self):
        """Generate embeddings for users based on their rating patterns"""
        logger.info("Generating user embeddings...")
        
        cursor = self.conn.cursor()
        
        # Get users without embeddings
        cursor.execute("""
            SELECT DISTINCT u.user_id
            FROM users u
            WHERE u.embedding IS NULL
            ORDER BY u.user_id
        """)
        
        users = cursor.fetchall()
        logger.info(f"Found {len(users)} users without embeddings")
        
        if not users:
            logger.info("All users already have embeddings")
            cursor.close()
            return
        
        # Process in batches
        total_processed = 0
        
        for i in range(0, len(users), self.batch_size):
            batch = users[i:i + self.batch_size]
            user_ids = [user[0] for user in batch]
            
            # Get user rating patterns and movie features
            user_embeddings = []
            
            for user_id in user_ids:
                # Get user's highly rated movies (rating >= 4.0)
                cursor.execute("""
                    SELECT m.title, m.overview, m.genres, r.rating
                    FROM ratings r
                    JOIN movies m ON r.movie_id = m.movie_id
                    WHERE r.user_id = %s AND r.rating >= 4.0
                    ORDER BY r.rating DESC, r.timestamp DESC
                    LIMIT 20
                """, (user_id,))
                
                user_movies = cursor.fetchall()
                
                if user_movies:
                    # Create user profile text from their favorite movies
                    movie_descriptions = []
                    for movie in user_movies:
                        movie_data = {
                            'title': movie[0],
                            'overview': movie[1],
                            'genres': movie[2]
                        }
                        movie_text = self.create_movie_text_features(movie_data)
                        movie_descriptions.append(movie_text)
                    
                    # Combine top movies into user profile
                    user_profile = f"User preferences based on highly rated movies: {' | '.join(movie_descriptions[:5])}"
                else:
                    # Fallback for users with no high ratings
                    user_profile = f"User {user_id} with limited rating history"
                
                # Generate embedding for user profile
                user_embedding = self.encode_text([user_profile])[0]
                user_embeddings.append((user_id, user_embedding.tolist()))
            
            # Update database
            for user_id, embedding in user_embeddings:
                cursor.execute("""
                    UPDATE users 
                    SET embedding = %s 
                    WHERE user_id = %s
                """, (embedding, user_id))
            
            self.conn.commit()
            total_processed += len(batch)
            logger.info(f"Processed {total_processed}/{len(users)} users")
        
        cursor.close()
        logger.info("✓ User embeddings generation completed")
    
    def verify_embeddings(self):
        """Verify that embeddings have been generated correctly"""
        logger.info("Verifying embeddings...")
        
        cursor = self.conn.cursor()
        
        # Check movie embeddings
        cursor.execute("""
            SELECT 
                COUNT(*) as total_movies,
                COUNT(embedding) as movies_with_embeddings,
                ROUND(COUNT(embedding)::numeric / COUNT(*) * 100, 2) as coverage_pct
            FROM movies
        """)
        
        movie_stats = cursor.fetchone()
        logger.info(f"Movies: {movie_stats[1]}/{movie_stats[0]} have embeddings ({movie_stats[2]}%)")
        
        # Check user embeddings
        cursor.execute("""
            SELECT 
                COUNT(*) as total_users,
                COUNT(embedding) as users_with_embeddings,
                ROUND(COUNT(embedding)::numeric / COUNT(*) * 100, 2) as coverage_pct
            FROM users
        """)
        
        user_stats = cursor.fetchone()
        logger.info(f"Users: {user_stats[1]}/{user_stats[0]} have embeddings ({user_stats[2]}%)")
        
        # Test embedding dimensions
        cursor.execute("""
            SELECT array_length(embedding, 1) as embedding_dim
            FROM movies 
            WHERE embedding IS NOT NULL 
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        if result:
            logger.info(f"Embedding dimension: {result[0]}")
        
        cursor.close()
        
        if movie_stats[2] > 90 and user_stats[2] > 90:
            logger.info("✓ Embedding generation verification successful")
        else:
            logger.warning("⚠ Some embeddings may be missing")

def main():
    parser = argparse.ArgumentParser(description='Generate embeddings for TMDB dataset')
    parser.add_argument('connection_string', help='PostgreSQL connection string')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for processing')
    parser.add_argument('--model-name', default='all-MiniLM-L6-v2', help='Transformer model name')
    
    args = parser.parse_args()
    
    # Initialize generator
    generator = TMDBEmbeddingsGenerator(
        args.connection_string, 
        args.model_name, 
        args.batch_size
    )
    
    try:
        # Connect to database
        generator.connect_to_db()
        
        # Load model
        generator.load_model()
        
        # Generate embeddings
        generator.generate_movie_embeddings()
        generator.generate_user_embeddings()
        
        # Verify results
        generator.verify_embeddings()
        
        logger.info("✓ Embedding generation completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Create DiskANN HNSW indexes on embedding columns")
        logger.info("2. Set up Apache AGE graph with the loaded data")
        logger.info("3. Run demo queries to test both DiskANN and AGE functionality")
        
    except Exception as e:
        logger.error(f"Error during embedding generation: {e}")
        raise
    finally:
        generator.close_connection()

if __name__ == "__main__":
    main()

