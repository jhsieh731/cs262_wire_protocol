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
        CREATE TABLE users (
            userid INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            associated_socket TEXT
        );


        CREATE TABLE messages (
            msgid INTEGER PRIMARY KEY AUTOINCREMENT,
            senderid INTEGER NOT NULL,
            recipientid INTEGER NOT NULL,
            message TEXT NOT NULL,
            status TEXT CHECK(status IN ('pending', 'delivered', 'seen')) DEFAULT 'pending',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (senderid) REFERENCES users(userid),
            FOREIGN KEY (recipientid) REFERENCES users(userid)
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

    def login_or_create_account(self, username: str, password: str):
        """Login if the username and password match exactly 1 record, create an account if the username does not match any, else return an empty list."""
        login_sql = """SELECT * FROM users WHERE username = ? AND hashed_password = ?;"""
        create_account_sql = """INSERT INTO users (username, hashed_password) VALUES (?, ?);"""
        check_username_sql = """SELECT * FROM users WHERE username = ?;"""
        
        try:
            conn = self.connect()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Check if the username and password match exactly 1 record
            cursor.execute(login_sql, (username, password))
            user = cursor.fetchone()
            if user:
                return [dict(user)]
            
            # Check if the username is unique
            cursor.execute(check_username_sql, (username,))
            if cursor.fetchone() is None:
                # Create a new account
                cursor.execute(create_account_sql, (username, password))
                conn.commit()
                cursor.execute(login_sql, (username, password))
                new_user = cursor.fetchone()
                if new_user:
                    return [dict(new_user)]
            
            return []
        except sqlite3.Error as e:
            print(f"Error in login_or_create_account: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def check_unique_username(self, username: str) -> bool:
        """Check if the username is unique."""
        sql = """SELECT * FROM users WHERE username = ?;"""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(sql, (username,))
            return cursor.fetchone() is None
        except sqlite3.Error as e:
            print(f"Error checking unique username: {e}")
            return False
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
