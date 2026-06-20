import sqlite3

def initialize_database():
    """
    Initializes history.db and creates the history table schema 
    if it does not already exist.
    """
    connection = sqlite3.connect("history.db")
    cursor = connection.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            summary TEXT NOT NULL,
            key_insights TEXT NOT NULL,
            transcript TEXT NOT NULL,
            quiz_json TEXT NOT NULL,
            word_count INTEGER DEFAULT 0,
            duration TEXT DEFAULT '0:00',
            favorite INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    connection.commit()
    connection.close()
    print("[DATABASE INFRASTRUCTURE] history.db provisioned successfully.")

if __name__ == "__main__":
    initialize_database()