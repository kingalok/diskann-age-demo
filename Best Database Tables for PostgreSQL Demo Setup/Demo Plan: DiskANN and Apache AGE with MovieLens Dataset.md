# Demo Plan: DiskANN and Apache AGE with MovieLens Dataset

## 1. Database Selection: MovieLens Dataset

The MovieLens dataset is chosen for this demonstration due to its suitability for both vector similarity search (DiskANN) and graph analysis (Apache AGE). It contains user ratings for movies, which allows for the creation of user and movie embeddings, and the inherent relationships between users, movies, and ratings can be naturally modeled as a graph.

### Dataset Overview (MovieLens 100K - u.data, u.item, u.user):

*   **u.data**: Contains user ratings of movies.
    *   `user_id`
    *   `item_id` (movie_id)
    *   `rating`
    *   `timestamp`

*   **u.item**: Contains movie information.
    *   `movie_id`
    *   `movie_title`
    *   `release_date`
    *   `video_release_date`
    *   `IMDb_URL`
    *   `genres` (19 different genres, binary flags)

*   **u.user**: Contains user demographic information.
    *   `user_id`
    *   `age`
    *   `gender`
    *   `occupation`
    *   `zip_code`

## 2. Database Tables for PostgreSQL Flexible Server

Based on the MovieLens dataset, the following PostgreSQL tables can be created:

### `users` table:

*   `user_id` (Primary Key)
*   `age`
*   `gender`
*   `occupation`
*   `zip_code`

### `movies` table:

*   `movie_id` (Primary Key)
*   `title`
*   `release_date`
*   `imdb_url`
*   `genre_action` (boolean)
*   `genre_adventure` (boolean)
*   ...
*   `genre_western` (boolean)

### `ratings` table:

*   `user_id` (Foreign Key to `users.user_id`)
*   `movie_id` (Foreign Key to `movies.movie_id`)
*   `rating`
*   `timestamp`

## 3. Integration with DiskANN and Apache AGE

### DiskANN Integration (Vector Similarity Search):

DiskANN will be used for approximate nearest neighbor search on vector embeddings. For this demo, we can generate embeddings for:

*   **Movie Embeddings**: Based on movie genres, title (using a pre-trained language model), and potentially aggregated user ratings.
    *   A new column, `embedding` (type `vector`), will be added to the `movies` table.
    *   DiskANN index will be created on this `embedding` column to enable fast similarity searches (e.g., finding movies similar to a given movie).

*   **User Embeddings**: Based on user's rated movies, genres they prefer, and demographic information.
    *   A new column, `embedding` (type `vector`), will be added to the `users` table.
    *   DiskANN index will be created on this `embedding` column to find similar users.

### Apache AGE Integration (Graph Analysis):

Apache AGE will be used to model and query the relationships within the MovieLens dataset as a graph. The core entities and relationships will be:

*   **Nodes (Vertices)**:
    *   `User` (properties: `user_id`, `age`, `gender`, `occupation`)
    *   `Movie` (properties: `movie_id`, `title`, `release_date`, `imdb_url`, `genres`)

*   **Edges (Relationships)**:
    *   `RATED` (properties: `rating`, `timestamp`) from `User` to `Movie`

This graph structure will allow for complex graph queries such as:

*   Finding movies rated highly by users similar to a given user.
*   Identifying communities of users with similar movie tastes.
*   Recommending movies based on graph traversals (e.g., 


finding movies connected to a user through highly-rated movies of similar users).

## 4. Demo Scenarios and Queries

### DiskANN Demo Scenarios:

*   **Find similar movies**: Given a `movie_id`, find other movies with similar embeddings (e.g., similar genres, themes, or user reception).
    *   Query: `SELECT movie_id, title FROM movies ORDER BY embedding <-> (SELECT embedding FROM movies WHERE movie_id = ?) LIMIT 10;`

*   **Find similar users**: Given a `user_id`, find other users with similar taste profiles.
    *   Query: `SELECT user_id, age, gender FROM users ORDER BY embedding <-> (SELECT embedding FROM users WHERE user_id = ?) LIMIT 10;`

### Apache AGE Demo Scenarios:

*   **User-Movie Interaction**: Show how a specific user rated a specific movie.
    *   Query: `SELECT * FROM ag_graph.cypher('movielens', $$ MATCH (u:User)-[r:RATED]->(m:Movie) WHERE u.user_id = 1 AND m.movie_id = 5 RETURN u.user_id, m.title, r.rating $$) as (user_id agtype, movie_title agtype, rating agtype);`

*   **Movies rated by a specific user**: List all movies rated by a given user.
    *   Query: `SELECT * FROM ag_graph.cypher('movielens', $$ MATCH (u:User)-[r:RATED]->(m:Movie) WHERE u.user_id = 1 RETURN m.title, r.rating $$) as (movie_title agtype, rating agtype);`

*   **Users who rated a specific movie**: Find all users who rated a particular movie and their ratings.
    *   Query: `SELECT * FROM ag_graph.cypher('movielens', $$ MATCH (u:User)-[r:RATED]->(m:Movie) WHERE m.movie_id = 5 RETURN u.user_id, r.rating $$) as (user_id agtype, rating agtype);`

*   **Collaborative Filtering (Basic)**: Recommend movies to a user based on what similar users (who rated the same movies highly) have also rated highly.
    *   Query: `SELECT * FROM ag_graph.cypher('movielens', $$ MATCH (u1:User)-[r1:RATED]->(m:Movie)<-[r2:RATED]-(u2:User) WHERE u1.user_id = 1 AND r1.rating >= 4 AND r2.rating >= 4 AND u1 <> u2 WITH u2 MATCH (u2)-[r3:RATED]->(m2:Movie) WHERE NOT EXISTS((u1)-[:RATED]->(m2)) RETURN DISTINCT m2.title LIMIT 10 $$) as (recommended_movie agtype);`

*   **Pathfinding**: Find the shortest path between two movies through common users.
    *   Query: `SELECT * FROM ag_graph.cypher('movielens', $$ MATCH p = shortestPath((m1:Movie)-[*..4]-(m2:Movie)) WHERE m1.movie_id = 5 AND m2.movie_id = 10 RETURN p $$) as (path agtype);`

## 5. Implementation Plan (High-Level)

1.  **Set up PostgreSQL Flexible Server**: Provision an instance of PostgreSQL Flexible Server.
2.  **Install Extensions**: Install `pgvector` (for vector support, required by DiskANN) and `apache_age` extensions.
3.  **Data Ingestion**: Load MovieLens data into the `users`, `movies`, and `ratings` tables.
4.  **Generate Embeddings**: Use a Python script and a pre-trained model (e.g., Sentence Transformers for movie titles/genres, or a simple aggregation for user profiles) to generate vector embeddings for movies and users. Store these in the respective `embedding` columns.
5.  **Create DiskANN Indexes**: Create DiskANN indexes on the `embedding` columns of `movies` and `users` tables.
6.  **Initialize AGE Graph**: Create a graph in Apache AGE and populate it with `User` and `Movie` nodes and `RATED` edges based on the `users`, `movies`, and `ratings` tables.
7.  **Demonstrate Queries**: Execute the DiskANN and Apache AGE queries outlined above to showcase their capabilities.

## 6. Deliverables

*   Detailed setup guide (Markdown/PDF)
*   SQL scripts for table creation, extension installation, and data loading.
*   Python script for embedding generation.
*   SQL/Cypher scripts for demo queries.
*   Presentation slides (if requested).


