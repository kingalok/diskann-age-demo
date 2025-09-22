#!/usr/bin/env python3
"""
TMDB Apache AGE Graph Setup for DiskANN and Apache AGE Demo

This script sets up the Apache AGE graph with nodes and relationships
from the TMDB dataset, creating a rich graph structure for analytics.

Usage:
    python setup_tmdb_age_graph.py <connection_string> [--batch-size N] [--sample-size N]

Example:
    python setup_tmdb_age_graph.py "host=localhost dbname=tmdb_demo user=postgres" --batch-size 1000
"""

import psycopg2
import sys
import argparse
import logging
import json
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TMDBAGEGraphSetup:
    def __init__(self, connection_string: str, batch_size: int = 1000, sample_size: Optional[int] = None):
        self.connection_string = connection_string
        self.batch_size = batch_size
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
    
    def setup_age_environment(self):
        """Set up Apache AGE environment"""
        logger.info("Setting up Apache AGE environment...")
        
        cursor = self.conn.cursor()
        
        try:
            # Load AGE extension
            cursor.execute("LOAD 'age';")
            
            # Set search path
            cursor.execute("SET search_path = ag_catalog, \"$user\", public;")
            
            # Check if graph exists, drop if it does
            cursor.execute("""
                SELECT COUNT(*) FROM ag_catalog.ag_graph WHERE name = 'tmdb_movies'
            """)
            
            if cursor.fetchone()[0] > 0:
                logger.info("Dropping existing graph...")
                cursor.execute("SELECT ag_catalog.drop_graph('tmdb_movies', true);")
            
            # Create new graph
            cursor.execute("SELECT ag_catalog.create_graph('tmdb_movies');")
            
            self.conn.commit()
            logger.info("✓ Apache AGE environment setup completed")
            
        except Exception as e:
            logger.error(f"Error setting up AGE environment: {e}")
            self.conn.rollback()
            raise
        finally:
            cursor.close()
    
    def create_movie_nodes(self):
        """Create Movie nodes in the graph"""
        logger.info("Creating Movie nodes...")
        
        cursor = self.conn.cursor()
        
        try:
            # Get movies data
            query = """
                SELECT movie_id, title, vote_average, vote_count, 
                       release_date, budget, revenue, runtime, genres
                FROM movies
                ORDER BY movie_id
            """
            
            if self.sample_size:
                query += f" LIMIT {self.sample_size}"
            
            cursor.execute(query)
            movies = cursor.fetchall()
            logger.info(f"Found {len(movies)} movies to create as nodes")
            
            # Process in batches
            total_created = 0
            
            for i in range(0, len(movies), self.batch_size):
                batch = movies[i:i + self.batch_size]
                
                for movie in batch:
                    movie_id, title, vote_avg, vote_count, release_date, budget, revenue, runtime, genres = movie
                    
                    # Parse genres
                    genre_list = []
                    if genres:
                        try:
                            genre_data = json.loads(genres) if isinstance(genres, str) else genres
                            genre_list = [g.get('name', '') for g in genre_data if isinstance(g, dict)]
                        except:
                            pass
                    
                    # Create Movie node
                    cursor.execute("""
                        SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
                            CREATE (m:Movie {
                                movie_id: %s,
                                title: %s,
                                vote_average: %s,
                                vote_count: %s,
                                release_date: %s,
                                budget: %s,
                                revenue: %s,
                                runtime: %s,
                                genres: %s
                            })
                            RETURN m.movie_id
                        $$) as (movie_id agtype);
                    """, (
                        movie_id,
                        title[:100] if title else "Unknown",  # Limit title length
                        float(vote_avg) if vote_avg else 0.0,
                        int(vote_count) if vote_count else 0,
                        str(release_date) if release_date else "",
                        int(budget) if budget else 0,
                        int(revenue) if revenue else 0,
                        int(runtime) if runtime else 0,
                        json.dumps(genre_list)
                    ))
                
                self.conn.commit()
                total_created += len(batch)
                logger.info(f"Created {total_created}/{len(movies)} Movie nodes")
            
            logger.info("✓ Movie nodes creation completed")
            
        except Exception as e:
            logger.error(f"Error creating Movie nodes: {e}")
            self.conn.rollback()
            raise
        finally:
            cursor.close()
    
    def create_person_nodes(self):
        """Create Person nodes in the graph"""
        logger.info("Creating Person nodes...")
        
        cursor = self.conn.cursor()
        
        try:
            # Get persons data
            cursor.execute("""
                SELECT person_id, name, gender, known_for_department
                FROM persons
                ORDER BY person_id
            """)
            
            persons = cursor.fetchall()
            logger.info(f"Found {len(persons)} persons to create as nodes")
            
            # Process in batches
            total_created = 0
            
            for i in range(0, len(persons), self.batch_size):
                batch = persons[i:i + self.batch_size]
                
                for person in batch:
                    person_id, name, gender, department = person
                    
                    # Create Person node
                    cursor.execute("""
                        SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
                            CREATE (p:Person {
                                person_id: %s,
                                name: %s,
                                gender: %s,
                                known_for_department: %s
                            })
                            RETURN p.person_id
                        $$) as (person_id agtype);
                    """, (
                        person_id,
                        name[:100] if name else "Unknown",
                        int(gender) if gender else 0,
                        department[:50] if department else "Unknown"
                    ))
                
                self.conn.commit()
                total_created += len(batch)
                logger.info(f"Created {total_created}/{len(persons)} Person nodes")
            
            logger.info("✓ Person nodes creation completed")
            
        except Exception as e:
            logger.error(f"Error creating Person nodes: {e}")
            self.conn.rollback()
            raise
        finally:
            cursor.close()
    
    def create_user_nodes(self):
        """Create User nodes in the graph"""
        logger.info("Creating User nodes...")
        
        cursor = self.conn.cursor()
        
        try:
            # Get users data
            cursor.execute("""
                SELECT user_id
                FROM users
                ORDER BY user_id
            """)
            
            users = cursor.fetchall()
            logger.info(f"Found {len(users)} users to create as nodes")
            
            # Process in batches
            total_created = 0
            
            for i in range(0, len(users), self.batch_size):
                batch = users[i:i + self.batch_size]
                
                for user in batch:
                    user_id = user[0]
                    
                    # Create User node
                    cursor.execute("""
                        SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
                            CREATE (u:User {
                                user_id: %s
                            })
                            RETURN u.user_id
                        $$) as (user_id agtype);
                    """, (user_id,))
                
                self.conn.commit()
                total_created += len(batch)
                logger.info(f"Created {total_created}/{len(users)} User nodes")
            
            logger.info("✓ User nodes creation completed")
            
        except Exception as e:
            logger.error(f"Error creating User nodes: {e}")
            self.conn.rollback()
            raise
        finally:
            cursor.close()
    
    def create_genre_nodes(self):
        """Create Genre nodes in the graph"""
        logger.info("Creating Genre nodes...")
        
        cursor = self.conn.cursor()
        
        try:
            # Get unique genres from movies
            cursor.execute("""
                SELECT DISTINCT genres
                FROM movies
                WHERE genres IS NOT NULL
            """)
            
            genre_rows = cursor.fetchall()
            unique_genres = set()
            
            for row in genre_rows:
                genres_data = row[0]
                if genres_data:
                    try:
                        genre_list = json.loads(genres_data) if isinstance(genres_data, str) else genres_data
                        for genre in genre_list:
                            if isinstance(genre, dict) and genre.get('name'):
                                unique_genres.add(genre['name'])
                    except:
                        pass
            
            logger.info(f"Found {len(unique_genres)} unique genres")
            
            # Create Genre nodes
            for genre_name in unique_genres:
                cursor.execute("""
                    SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
                        CREATE (g:Genre {
                            name: %s
                        })
                        RETURN g.name
                    $$) as (name agtype);
                """, (genre_name,))
            
            self.conn.commit()
            logger.info("✓ Genre nodes creation completed")
            
        except Exception as e:
            logger.error(f"Error creating Genre nodes: {e}")
            self.conn.rollback()
            raise
        finally:
            cursor.close()
    
    def create_rated_relationships(self):
        """Create RATED relationships between Users and Movies"""
        logger.info("Creating RATED relationships...")
        
        cursor = self.conn.cursor()
        
        try:
            # Get ratings data
            query = """
                SELECT user_id, movie_id, rating, timestamp
                FROM ratings
                ORDER BY user_id, movie_id
            """
            
            if self.sample_size:
                query += f" LIMIT {self.sample_size * 10}"  # More ratings than movies
            
            cursor.execute(query)
            ratings = cursor.fetchall()
            logger.info(f"Found {len(ratings)} ratings to create as relationships")
            
            # Process in batches
            total_created = 0
            
            for i in range(0, len(ratings), self.batch_size):
                batch = ratings[i:i + self.batch_size]
                
                for rating in batch:
                    user_id, movie_id, rating_value, timestamp = rating
                    
                    # Create RATED relationship
                    cursor.execute("""
                        SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
                            MATCH (u:User {user_id: %s})
                            MATCH (m:Movie {movie_id: %s})
                            CREATE (u)-[r:RATED {
                                rating: %s,
                                timestamp: %s
                            }]->(m)
                            RETURN r.rating
                        $$) as (rating agtype);
                    """, (
                        user_id,
                        movie_id,
                        float(rating_value),
                        int(timestamp) if timestamp else 0
                    ))
                
                self.conn.commit()
                total_created += len(batch)
                logger.info(f"Created {total_created}/{len(ratings)} RATED relationships")
            
            logger.info("✓ RATED relationships creation completed")
            
        except Exception as e:
            logger.error(f"Error creating RATED relationships: {e}")
            self.conn.rollback()
            raise
        finally:
            cursor.close()
    
    def create_acted_in_relationships(self):
        """Create ACTED_IN relationships between Persons and Movies"""
        logger.info("Creating ACTED_IN relationships...")
        
        cursor = self.conn.cursor()
        
        try:
            # Get cast data
            cursor.execute("""
                SELECT movie_id, person_id, character, order_in_credits
                FROM movie_cast
                ORDER BY movie_id, order_in_credits
            """)
            
            cast_data = cursor.fetchall()
            logger.info(f"Found {len(cast_data)} cast relationships to create")
            
            # Process in batches
            total_created = 0
            
            for i in range(0, len(cast_data), self.batch_size):
                batch = cast_data[i:i + self.batch_size]
                
                for cast in batch:
                    movie_id, person_id, character, order_in_credits = cast
                    
                    # Create ACTED_IN relationship
                    cursor.execute("""
                        SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
                            MATCH (p:Person {person_id: %s})
                            MATCH (m:Movie {movie_id: %s})
                            CREATE (p)-[r:ACTED_IN {
                                character: %s,
                                order: %s
                            }]->(m)
                            RETURN r.character
                        $$) as (character agtype);
                    """, (
                        person_id,
                        movie_id,
                        character[:100] if character else "Unknown",
                        int(order_in_credits) if order_in_credits else 999
                    ))
                
                self.conn.commit()
                total_created += len(batch)
                logger.info(f"Created {total_created}/{len(cast_data)} ACTED_IN relationships")
            
            logger.info("✓ ACTED_IN relationships creation completed")
            
        except Exception as e:
            logger.error(f"Error creating ACTED_IN relationships: {e}")
            self.conn.rollback()
            raise
        finally:
            cursor.close()
    
    def create_directed_relationships(self):
        """Create DIRECTED relationships between Persons and Movies"""
        logger.info("Creating DIRECTED relationships...")
        
        cursor = self.conn.cursor()
        
        try:
            # Get director data
            cursor.execute("""
                SELECT movie_id, person_id
                FROM movie_crew
                WHERE job = 'Director'
                ORDER BY movie_id
            """)
            
            director_data = cursor.fetchall()
            logger.info(f"Found {len(director_data)} director relationships to create")
            
            # Process in batches
            total_created = 0
            
            for i in range(0, len(director_data), self.batch_size):
                batch = director_data[i:i + self.batch_size]
                
                for director in batch:
                    movie_id, person_id = director
                    
                    # Create DIRECTED relationship
                    cursor.execute("""
                        SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
                            MATCH (p:Person {person_id: %s})
                            MATCH (m:Movie {movie_id: %s})
                            CREATE (p)-[r:DIRECTED]->(m)
                            RETURN p.person_id
                        $$) as (person_id agtype);
                    """, (person_id, movie_id))
                
                self.conn.commit()
                total_created += len(batch)
                logger.info(f"Created {total_created}/{len(director_data)} DIRECTED relationships")
            
            logger.info("✓ DIRECTED relationships creation completed")
            
        except Exception as e:
            logger.error(f"Error creating DIRECTED relationships: {e}")
            self.conn.rollback()
            raise
        finally:
            cursor.close()
    
    def create_has_genre_relationships(self):
        """Create HAS_GENRE relationships between Movies and Genres"""
        logger.info("Creating HAS_GENRE relationships...")
        
        cursor = self.conn.cursor()
        
        try:
            # Get movies with genres
            cursor.execute("""
                SELECT movie_id, genres
                FROM movies
                WHERE genres IS NOT NULL
                ORDER BY movie_id
            """)
            
            movies_with_genres = cursor.fetchall()
            logger.info(f"Found {len(movies_with_genres)} movies with genres")
            
            total_created = 0
            
            for movie_id, genres_data in movies_with_genres:
                if genres_data:
                    try:
                        genre_list = json.loads(genres_data) if isinstance(genres_data, str) else genres_data
                        for genre in genre_list:
                            if isinstance(genre, dict) and genre.get('name'):
                                genre_name = genre['name']
                                
                                # Create HAS_GENRE relationship
                                cursor.execute("""
                                    SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
                                        MATCH (m:Movie {movie_id: %s})
                                        MATCH (g:Genre {name: %s})
                                        CREATE (m)-[r:HAS_GENRE]->(g)
                                        RETURN m.movie_id
                                    $$) as (movie_id agtype);
                                """, (movie_id, genre_name))
                                
                                total_created += 1
                    except:
                        pass
                
                if total_created % 1000 == 0:
                    self.conn.commit()
                    logger.info(f"Created {total_created} HAS_GENRE relationships")
            
            self.conn.commit()
            logger.info(f"✓ HAS_GENRE relationships creation completed ({total_created} total)")
            
        except Exception as e:
            logger.error(f"Error creating HAS_GENRE relationships: {e}")
            self.conn.rollback()
            raise
        finally:
            cursor.close()
    
    def verify_graph_creation(self):
        """Verify that the graph has been created correctly"""
        logger.info("Verifying graph creation...")
        
        cursor = self.conn.cursor()
        
        try:
            # Count nodes by type
            node_types = ['Movie', 'Person', 'User', 'Genre']
            
            for node_type in node_types:
                cursor.execute(f"""
                    SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
                        MATCH (n:{node_type})
                        RETURN count(n)
                    $$) as (count agtype);
                """)
                
                count = cursor.fetchone()[0]
                logger.info(f"{node_type} nodes: {count}")
            
            # Count relationships by type
            rel_types = ['RATED', 'ACTED_IN', 'DIRECTED', 'HAS_GENRE']
            
            for rel_type in rel_types:
                cursor.execute(f"""
                    SELECT * FROM ag_catalog.cypher('tmdb_movies', $$
                        MATCH ()-[r:{rel_type}]->()
                        RETURN count(r)
                    $$) as (count agtype);
                """)
                
                count = cursor.fetchone()[0]
                logger.info(f"{rel_type} relationships: {count}")
            
            logger.info("✓ Graph verification completed")
            
        except Exception as e:
            logger.error(f"Error verifying graph: {e}")
            raise
        finally:
            cursor.close()

def main():
    parser = argparse.ArgumentParser(description='Set up Apache AGE graph for TMDB dataset')
    parser.add_argument('connection_string', help='PostgreSQL connection string')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for processing')
    parser.add_argument('--sample-size', type=int, help='Limit number of movies to process (for testing)')
    
    args = parser.parse_args()
    
    # Initialize setup
    setup = TMDBAGEGraphSetup(args.connection_string, args.batch_size, args.sample_size)
    
    try:
        # Connect to database
        setup.connect_to_db()
        
        # Set up AGE environment
        setup.setup_age_environment()
        
        # Create nodes
        setup.create_movie_nodes()
        setup.create_person_nodes()
        setup.create_user_nodes()
        setup.create_genre_nodes()
        
        # Create relationships
        setup.create_rated_relationships()
        setup.create_acted_in_relationships()
        setup.create_directed_relationships()
        setup.create_has_genre_relationships()
        
        # Verify creation
        setup.verify_graph_creation()
        
        logger.info("✓ Apache AGE graph setup completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Run demo queries to test graph analytics functionality")
        logger.info("2. Test hybrid DiskANN + AGE queries")
        logger.info("3. Optimize graph performance if needed")
        
    except Exception as e:
        logger.error(f"Error during graph setup: {e}")
        raise
    finally:
        setup.close_connection()

if __name__ == "__main__":
    main()

