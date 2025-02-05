import sqlite3
from typing import List, Tuple
import os

class MessageDatabase:
    def __init__(self, db_file: str = "messages.db"):
        """Initialize the database connection."""
        self.db_file = db_file
        self.conn = None
        self.create_tables()

    def connect(self):
        """Create a database connection."""
        try:
            self.conn = sqlite3.connect(self.db_file)
            return self.conn
        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")
            return None

    def create_tables(self):
        """Create the messages table if it doesn't exist."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id TEXT NOT NULL,
            receiver_id TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
        try:
            conn = self.connect()
            if conn is not None:
                cursor = conn.cursor()
                cursor.execute(create_table_sql)
                conn.commit()
            else:
                print("Error: Could not establish database connection")
        except sqlite3.Error as e:
            print(f"Error creating table: {e}")
        finally:
            if conn:
                conn.close()

    def store_message(self, sender_id: str, receiver_id: str, content: str) -> bool:
        """Store a new message in the database."""
        sql = """INSERT INTO messages (sender_id, receiver_id, content)
                VALUES (?, ?, ?);"""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(sql, (sender_id, receiver_id, content))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error storing message: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def get_messages(self, user_id: str) -> List[Tuple]:
        """Retrieve all messages for a specific user (as sender or receiver)."""
        sql = """SELECT sender_id, receiver_id, content, timestamp 
                FROM messages 
                WHERE sender_id = ? OR receiver_id = ?
                ORDER BY timestamp DESC;"""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(sql, (user_id, user_id))
            return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error retrieving messages: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def clear_all_messages(self):
        """Clear all messages from the database. Use with caution!"""
        sql = "DELETE FROM messages;"
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(sql)
            conn.commit()
        except sqlite3.Error as e:
            print(f"Error clearing messages: {e}")
        finally:
            if conn:
                conn.close()
