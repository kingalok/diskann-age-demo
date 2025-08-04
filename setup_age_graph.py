#!/usr/bin/env python3
"""
Apache AGE Graph Setup for MovieLens Demo

This script sets up the Apache AGE graph database with MovieLens data,
creating nodes for users and movies, and relationships for ratings.

Usage:
    python setup_age_graph.py <connection_string>

Example:
    python setup_age_graph.py "host=localhost dbname=movielens_demo user=postgres"
"""

import psycopg2
import sys
import logging
import json
from typing import List, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def connect_to_db(connection_string: str):
    """Connect to PostgreSQL database"""
    try:
        conn = psycopg2.connect(connection_string)
        conn.autocommit = True  # Required for AGE operations
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        sys.exit(1)

def setup_age_environment(conn):
    """Set up Apache AGE environment"""
    logger.info("Setting up Apache AGE environment...")
    
    cursor = conn.cursor()
    
    try:
        # Load AGE extension
        cursor.execute("LOAD 'age';")
        
        # Set search path
        cursor.execute("SET search_path = ag_catalog, \"$user\", public;")
        
        # Check if graph already exists
        cursor.execute("SELECT * FROM ag_catalog.ag_graph WHERE name = 'movielens';")
        existing_graph = cursor.fetchone()
        
        if existing_graph:
            logger.info("Graph 'movielens' already exists. Dropping and recreating...")
            cursor.execute("SELECT ag_catalog.drop_graph('movielens', true);")
        
        # Create the graph
        cursor.execute("SELECT ag_catalog.create_graph('movielens');")
        logger.info("Created graph 'movielens'")
        
    except Exception as e:
        logger.error(f"Error setting up AGE environment: {e}")
        raise
    finally:
        cursor.close()

def create_user_nodes(conn):
    """Create User nodes in the graph"""
    logger.info("Creating User nodes...")
    
    cursor = conn.cursor()
    
    try:
        # Fetch user data
        cursor.execute("""
            SELECT user_id, age, gender, occupation, zip_code
            FROM users
            ORDER BY user_id
        """)
        users = cursor.fetchall()
        
        logger.info(f"Creating {len(users)} User nodes...")
        
        # Create User nodes in batches
        batch_size = 100
        created_count = 0
        
        for i in range(0, len(users), batch_size):
            batch = users[i:i+batch_size]
            
            for user in batch:
                user_id, age, gender, occupation, zip_code = user
                
                # Escape quotes in string values
                occupation_safe = occupation.replace("'", "''") if occupation else ''
                zip_code_safe = zip_code.replace("'", "''") if zip_code else ''
                gender_safe = gender.replace("'", "''") if gender else ''
                
                cypher_query = f"""
                SELECT * FROM ag_catalog.cypher('movielens', $$
                    CREATE (u:User {{
                        user_id: {user_id},
                        age: {age},
                        gender: '{gender_safe}',
                        occupation: '{occupation_safe}',
                        zip_code: '{zip_code_safe}'
                    }})
                $$) as (result agtype);
                """
                
                cursor.execute(cypher_query)
                created_count += 1
            
            if (i + batch_size) % 500 == 0:
                logger.info(f"Created {min(i + batch_size, len(users))} User nodes...")
        
        logger.info(f"Successfully created {created_count} User nodes")
        
    except Exception as e:
        logger.error(f"Error creating User nodes: {e}")
        raise
    finally:
        cursor.close()

def create_movie_nodes(conn):
    """Create Movie nodes in the graph"""
    logger.info("Creating Movie nodes...")
    
    cursor = conn.cursor()
    
    try:
        # Fetch movie data
        cursor.execute("""
            SELECT movie_id, title, release_date,
                   genre_action, genre_adventure, genre_animation, genre_children,
                   genre_comedy, genre_crime, genre_documentary, genre_drama,
                   genre_fantasy, genre_film_noir, genre_horror, genre_musical,
                   genre_mystery, genre_romance, genre_sci_fi, genre_thriller,
                   genre_war, genre_western
            FROM movies
            ORDER BY movie_id
        """)
        movies = cursor.fetchall()
        
        logger.info(f"Creating {len(movies)} Movie nodes...")
        
        # Genre names for creating genre arrays
        genre_names = [
            'action', 'adventure', 'animation', 'children', 'comedy', 'crime',
            'documentary', 'drama', 'fantasy', 'film_noir', 'horror', 'musical',
            'mystery', 'romance', 'sci_fi', 'thriller', 'war', 'western'
        ]
        
        created_count = 0
        
        for movie in movies:
            movie_id = movie[0]
            title = movie[1]
            release_date = movie[2]
            genres = movie[3:]  # Boolean values for each genre
            
            # Handle title escaping properly for Cypher
            if title:
                # Use JSON-style escaping for the title
                title_safe = json.dumps(title)[1:-1]  # Remove outer quotes
            else:
                title_safe = ''
            
            # Create genre list
            active_genres = [genre_names[i] for i, is_active in enumerate(genres) if is_active]
            genres_str = "', '".join(active_genres)
            genres_array = f"['{genres_str}']" if active_genres else "[]"
            
            # Format release date
            release_year = release_date.year if release_date else None
            
            # Use parameterized query to avoid escaping issues
            cypher_query = f"""
            SELECT * FROM ag_catalog.cypher('movielens', $$
                CREATE (m:Movie {{
                    movie_id: {movie_id},
                    title: '{title_safe}',
                    release_year: {release_year if release_year else 'null'},
                    genres: {genres_array}
                }})
            $$) as (result agtype);
            """
            
            cursor.execute(cypher_query)
            created_count += 1
            
            if created_count % 100 == 0:
                logger.info(f"Created {created_count} Movie nodes...")
        
        logger.info(f"Successfully created {created_count} Movie nodes")
        
    except Exception as e:
        logger.error(f"Error creating Movie nodes: {e}")
        raise
    finally:
        cursor.close()

def create_rating_relationships(conn):
    """Create RATED relationships between users and movies"""
    logger.info("Creating RATED relationships...")
    
    cursor = conn.cursor()
    
    try:
        # Fetch ratings data
        cursor.execute("""
            SELECT user_id, movie_id, rating, timestamp
            FROM ratings
            ORDER BY user_id, movie_id
        """)
        ratings = cursor.fetchall()
        
        logger.info(f"Creating {len(ratings)} RATED relationships...")
        
        # Create relationships in batches
        batch_size = 1000
        created_count = 0
        
        for i in range(0, len(ratings), batch_size):
            batch = ratings[i:i+batch_size]
            
            for rating_data in batch:
                user_id, movie_id, rating, timestamp = rating_data
                
                cypher_query = f"""
                SELECT * FROM ag_catalog.cypher('movielens', $$
                    MATCH (u:User {{user_id: {user_id}}}), (m:Movie {{movie_id: {movie_id}}})
                    CREATE (u)-[:RATED {{
                        rating: {rating},
                        timestamp: {timestamp}
                    }}]->(m)
                $$) as (result agtype);
                """
                
                cursor.execute(cypher_query)
                created_count += 1
            
            if (i + batch_size) % 10000 == 0:
                logger.info(f"Created {min(i + batch_size, len(ratings))} RATED relationships...")
        
        logger.info(f"Successfully created {created_count} RATED relationships")
        
    except Exception as e:
        logger.error(f"Error creating RATED relationships: {e}")
        raise
    finally:
        cursor.close()

def verify_graph_creation(conn):
    """Verify that the graph has been created correctly"""
    logger.info("Verifying graph creation...")
    
    cursor = conn.cursor()
    
    try:
        # Count nodes by type
        cursor.execute("""
            SELECT * FROM ag_catalog.cypher('movielens', $$
                MATCH (n) 
                RETURN labels(n)[0] as node_type, count(n) as count
            $$) as (node_type agtype, count agtype);
        """)
        node_counts = cursor.fetchall()
        
        logger.info("Node counts:")
        for node_type, count in node_counts:
            # Remove quotes from agtype values
            node_type_clean = str(node_type).strip('"')
            logger.info(f"  {node_type_clean}: {count}")
        
        # Count relationships
        cursor.execute("""
            SELECT * FROM ag_catalog.cypher('movielens', $$
                MATCH ()-[r]->() 
                RETURN type(r) as relationship_type, count(r) as count
            $$) as (relationship_type agtype, count agtype);
        """)
        rel_counts = cursor.fetchall()
        
        logger.info("Relationship counts:")
        for rel_type, count in rel_counts:
            # Remove quotes from agtype values
            rel_type_clean = str(rel_type).strip('"')
            logger.info(f"  {rel_type_clean}: {count}")
        
        # Sample data verification
        logger.info("Sample data verification:")
        
        # Sample user
        cursor.execute("""
            SELECT * FROM ag_catalog.cypher('movielens', $$
                MATCH (u:User) 
                RETURN u.user_id, u.age, u.gender, u.occupation
                LIMIT 3
            $$) as (user_id agtype, age agtype, gender agtype, occupation agtype);
        """)
        sample_users = cursor.fetchall()
        logger.info(f"Sample users: {sample_users}")
        
        # Sample movie
        cursor.execute("""
            SELECT * FROM ag_catalog.cypher('movielens', $$
                MATCH (m:Movie) 
                RETURN m.movie_id, m.title, m.genres
                LIMIT 3
            $$) as (movie_id agtype, title agtype, genres agtype);
        """)
        sample_movies = cursor.fetchall()
        logger.info(f"Sample movies: {sample_movies}")
        
        # Sample rating
        cursor.execute("""
            SELECT * FROM ag_catalog.cypher('movielens', $$
                MATCH (u:User)-[r:RATED]->(m:Movie) 
                RETURN u.user_id, m.title, r.rating
                LIMIT 3
            $$) as (user_id agtype, movie_title agtype, rating agtype);
        """)
        sample_ratings = cursor.fetchall()
        logger.info(f"Sample ratings: {sample_ratings}")
        
    except Exception as e:
        logger.error(f"Error verifying graph: {e}")
        raise
    finally:
        cursor.close()

def create_graph_indexes(conn):
    """Create indexes for better graph query performance"""
    logger.info("Creating graph indexes...")
    
    cursor = conn.cursor()
    
    try:
        # Note: AGE index creation syntax may vary depending on version
        # These are examples - adjust based on your AGE version
        
        # Index on User.user_id
        cursor.execute("""
            SELECT * FROM ag_catalog.cypher('movielens', $$
                CREATE INDEX user_id_idx FOR (u:User) ON (u.user_id)
            $$) as (result agtype);
        """)
        
        # Index on Movie.movie_id
        cursor.execute("""
            SELECT * FROM ag_catalog.cypher('movielens', $$
                CREATE INDEX movie_id_idx FOR (m:Movie) ON (m.movie_id)
            $$) as (result agtype);
        """)
        
        logger.info("Graph indexes created successfully")
        
    except Exception as e:
        # Index creation might fail in some AGE versions - this is not critical
        logger.warning(f"Index creation failed (this may be normal): {e}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python setup_age_graph.py <connection_string>")
        print("Example: python setup_age_graph.py 'host=localhost dbname=movielens_demo user=postgres'")
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
        
        # Set up AGE graph
        setup_age_environment(conn)
        create_user_nodes(conn)
        create_movie_nodes(conn)
        create_rating_relationships(conn)
        
        # Create indexes (optional)
        create_graph_indexes(conn)
        
        # Verify creation
        verify_graph_creation(conn)
        
        logger.info("✓ Apache AGE graph setup completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Run demo queries from demo_queries.sql")
        logger.info("2. Test both DiskANN and AGE functionality")
        logger.info("3. Explore hybrid queries combining vector similarity and graph analytics")
        
    except Exception as e:
        logger.error(f"Error during graph setup: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()

