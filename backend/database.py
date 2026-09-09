import sqlite3
import os
from typing import List, Optional, Dict, Any

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "fact_layer.db")

def get_connection():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Documents Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            filepath TEXT NOT NULL,
            category TEXT DEFAULT 'uploaded',
            page_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Facts Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            doc_filename TEXT NOT NULL,
            subject TEXT NOT NULL,
            metric_type TEXT,
            value TEXT NOT NULL,
            numeric_value REAL,
            unit TEXT,
            temporal_context TEXT,
            scope_context TEXT,
            confidence REAL DEFAULT 1.0,
            page_number INTEGER NOT NULL,
            exact_quote TEXT NOT NULL,
            FOREIGN KEY (doc_id) REFERENCES documents (id) ON DELETE CASCADE
        )
    ''')
    
    # Relationships Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact_a_id INTEGER NOT NULL,
            fact_b_id INTEGER NOT NULL,
            doc_a_name TEXT NOT NULL,
            doc_b_name TEXT NOT NULL,
            subject_group TEXT,
            fact_a_summary TEXT NOT NULL,
            fact_b_summary TEXT NOT NULL,
            relationship_type TEXT NOT NULL,
            confidence REAL DEFAULT 1.0,
            reasoning TEXT NOT NULL,
            context_explanation TEXT,
            FOREIGN KEY (fact_a_id) REFERENCES facts (id) ON DELETE CASCADE,
            FOREIGN KEY (fact_b_id) REFERENCES facts (id) ON DELETE CASCADE
        )
    ''')

    # Case Studies Showcase Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS case_studies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_number INTEGER NOT NULL,
            case_name TEXT NOT NULL,
            relationship_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            doc_a_name TEXT NOT NULL,
            fact_a_quote TEXT NOT NULL,
            fact_a_page INTEGER NOT NULL,
            doc_b_name TEXT NOT NULL,
            fact_b_quote TEXT NOT NULL,
            fact_b_page INTEGER NOT NULL,
            reasoning TEXT NOT NULL,
            key_insight TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized at:", DB_PATH)
