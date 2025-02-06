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
        create_users_sql = """
        CREATE TABLE users (
            userid INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            associated_socket TEXT
        );
        """


        create_messages_sql = """
        CREATE TABLE messages (
            msgid INTEGER PRIMARY KEY AUTOINCREMENT,
            senderuuid INTEGER NOT NULL,
            recipientuuid INTEGER NOT NULL,
            message TEXT NOT NULL,
            status TEXT CHECK(status IN ('pending', 'delivered', 'seen')) DEFAULT 'pending',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (senderuuid) REFERENCES users(userid),
            FOREIGN KEY (recipientuuid) REFERENCES users(userid)
        );
        """
        try:
            conn = self.connect()
            if conn is not None:
                cursor = conn.cursor()
                cursor.execute(create_users_sql)
                conn.commit()
                cursor.execute(create_messages_sql)
                conn.commit()
            else:
                print("Error: Could not establish database connection")
        except sqlite3.Error as e:
            print(f"Error creating table: {e}")
        finally:
            if conn:
                conn.close()

    def login_or_create_account(self, username: str, password: str, socket:str):
        """Login if the username and password match exactly 1 record, create an account if the username does not match any, else return an empty list."""
        login_sql = """SELECT * FROM users WHERE username = ? AND hashed_password = ?;"""
        create_account_sql = """INSERT INTO users (username, hashed_password, associated_socket) VALUES (?, ?, ?);"""
        check_username_sql = """SELECT * FROM users WHERE username = ?;"""
        update_socket_sql = """UPDATE users SET associated_socket = ? WHERE userid = ?;"""

        try:
            conn = self.connect()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Check if the username and password match exactly 1 record
            cursor.execute(login_sql, (username, password))
            user = cursor.fetchone()
            if user:
                # update socket
                print("logging in, socket: ", socket, len(socket))
                cursor.execute(update_socket_sql, (socket, user["userid"]))
                conn.commit()
                return [dict(user)]
            
            # Check if the username is unique
            cursor.execute(check_username_sql, (username,))
            if cursor.fetchone() is None:
                # Create a new account
                cursor.execute(create_account_sql, (username, password, socket))
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

    def get_messages(self, sender_uuid: str, receiver_uuid: str) -> List[Tuple]:
        """Retrieve messages based on sender and receiver UUIDs.
        Empty strings for either UUID will match all values for that field."""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            
            # Build the WHERE clause based on which UUIDs are provided
            conditions = []
            params = []
            
            if sender_uuid:
                conditions.append("senderuuid = ?")
                params.append(sender_uuid)
            if receiver_uuid:
                conditions.append("recipientuuid = ?")
                params.append(receiver_uuid)
            
            # If no conditions, return all messages
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            sql = f"""SELECT senderuuid, recipientuuid, message, status, timestamp 
                    FROM messages 
                    WHERE {where_clause}
                    ORDER BY timestamp DESC;"""
            
            print(f"Executing query: {sql} with params: {params}")
            cursor.execute(sql, params)
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
                
    def get_user_uuid(self, username: str) -> tuple[bool, str, str]:
        """
        Get a user's UUID by their username.
        Returns (success, error_message, uuid)
        """
        try:
            conn = self.connect()
            if conn is None:
                return False, "Database connection failed", ""

            cursor = conn.cursor()
            cursor.execute("SELECT userid FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()
            
            if not user:
                return False, f"User {username} not found", ""
                
            return True, "", str(user[0])
            
        except sqlite3.Error as e:
            print(f"Error getting user UUID: {e}")
            return False, str(e), ""
        finally:
            if conn:
                conn.close()

    def get_associated_socket(self, user_uuid: str) -> str:
        """
        Get the associated socket for a user by their UUID.
        Returns the socket string if found, empty string if not found or error.
        """
        try:
            conn = self.connect()
            if conn is None:
                return ""

            cursor = conn.cursor()
            cursor.execute("SELECT associated_socket FROM users WHERE userid = ?", (user_uuid,))
            result = cursor.fetchone()
            
            if result and result[0]:
                return result[0]
            return ""
            
        except sqlite3.Error as e:
            print(f"Error getting associated socket: {e}")
            return ""
        finally:
            if conn:
                conn.close()

    def store_message(self, sender_uuid: str, recipient_uuid: str, message_text: str) -> tuple[bool, str]:
        """
        Store a message in the database.
        Returns (success, error_message)
        """
        try:
            conn = self.connect()
            if conn is None:
                return False, "Database connection failed"

            cursor = conn.cursor()
            
            # Get recipient's associated socket
            recipient_socket = self.get_associated_socket(recipient_uuid)
            
            # Set message status based on recipient's socket status
            status = "delivered" if recipient_socket else "pending"
            
            # Insert the message using UUIDs directly
            cursor.execute("""
                INSERT INTO messages (senderuuid, recipientuuid, message, status)
                VALUES (?, ?, ?, ?)
            """, (sender_uuid, recipient_uuid, message_text, status))
            
            conn.commit()
            return True, ""
            
        except sqlite3.Error as e:
            print(f"Error storing message: {e}")
            return False, str(e)
        finally:
            if conn:
                conn.close()

    def search_accounts(self, search_term: str, current_page: int = 0, accounts_per_page: int = 10) -> tuple[list[dict], int]:
        """
        Search for user accounts with pagination.
        Returns (list of user dictionaries, total count of matching users)
        """
        try:
            print(f"\nSearching for term: '{search_term}' (page {current_page}, per_page {accounts_per_page})")
            conn = self.connect()
            if conn is None:
                print("Database connection failed")
                return [], 0
                
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # First get total count
            if search_term == "":
                count_sql = "SELECT COUNT(*) as total FROM users"
                cursor.execute(count_sql)
            else:
                count_sql = "SELECT COUNT(*) as total FROM users WHERE username LIKE ? || '%'"
                cursor.execute(count_sql, (search_term,))
            
            total_count = cursor.fetchone()["total"]
            print(f"Total matching users: {total_count}")
            
            # Calculate offset
            offset = current_page * accounts_per_page
            
            # Get paginated results
            if search_term == "":
                search_sql = """
                    SELECT userid, username 
                    FROM users 
                    ORDER BY username ASC
                    LIMIT ? OFFSET ?
                """
                print(f"\nExecuting SQL to get users (limit {accounts_per_page}, offset {offset})")
                cursor.execute(search_sql, (accounts_per_page, offset))
            else:
                search_sql = """
                    SELECT userid, username 
                    FROM users 
                    WHERE username LIKE ? || '%'
                    ORDER BY username ASC
                    LIMIT ? OFFSET ?
                """
                print(f"\nExecuting SQL to search for '{search_term}'")
                cursor.execute(search_sql, (search_term, accounts_per_page, offset))
            
            results = [dict(row) for row in cursor.fetchall()]
            print(f"\nQuery results: {results}")
            return results, total_count
            
        except sqlite3.Error as e:
            print(f"Error searching accounts: {e}")
            return [], 0
        finally:
            if conn:
                conn.close()
