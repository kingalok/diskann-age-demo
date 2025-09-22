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
