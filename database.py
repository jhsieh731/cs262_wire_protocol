import sqlite3
from typing import List, Tuple, Optional
import os
from datetime import datetime

class MessageDatabase:
    def __init__(self, db_file: str = "messages.db"):
        """Initialize the database connection."""
        self.db_file = db_file
        self.conn = None
        self.create_tables()

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

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
        CREATE TABLE IF NOT EXISTS users (
            userid INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            associated_socket TEXT
        );
        """

        create_messages_sql = """
        CREATE TABLE IF NOT EXISTS messages (
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

        # Guard for empty strings; msg_server will handle this as failure
        if not username or not password or not socket:
            return []

        # convert username to lowercase
        username = username.lower()

        try:
            conn = self.connect()
            if conn is None:
                return []
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Check if the username and password match records
            cursor.execute(login_sql, (username, password))
            res = cursor.fetchall()
            print("res: ", res)

            # Check if multiple users have the same username and password
            if len(res) > 1:
                print("Error: multiple users with the same username and password")
                return []
            user = res[0] if len(res) == 1 else None

            # login
            if user:
                # update socket
                print("logging in, socket: ", socket, len(socket))
                cursor.execute(update_socket_sql, (socket, user["userid"]))
                conn.commit()
                return [dict(user)]
            
            # Register; Check if the username is unique
            cursor.execute(check_username_sql, (username,))
            if cursor.fetchone() is None:
                # Create a new account
                cursor.execute(create_account_sql, (username, password, socket))
                conn.commit()
                cursor.execute(login_sql, (username, password))
                new_user = cursor.fetchone()
                print("new_user: ", new_user)
                if new_user:
                    return [dict(new_user)]
            return []
        except sqlite3.Error as e:
            print(f"Error in login_or_create_account: {e}")
            return []
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

    def get_associated_socket(self, user_uuid: str) -> Optional[str]:
        """
        Get the associated socket (or None) for a user by their UUID.
        """
        try:
            conn = self.connect()
            if conn is None:
                return None

            cursor = conn.cursor()
            cursor.execute("SELECT associated_socket FROM users WHERE userid = ?", (user_uuid,))
            result = cursor.fetchone()
            
            if result:
                return result[0]
            return None
            
        except sqlite3.Error as e:
            print(f"Error getting associated socket: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def store_message(self, sender_uuid: str, recipient_uuid: str, message_text: str, status: bool, timestamp) -> tuple[bool, str]:
        """
        Store a message in the database.
        Returns (success, error_message)
        """
        try:
            conn = self.connect()
            if conn is None:
                return False, "Database connection failed"

            cursor = conn.cursor()
            
            # Set message status based on recipient's socket status
            status = "delivered" if status else "pending"
            
            # Insert the message using UUIDs directly
            cursor.execute("""
                INSERT INTO messages (senderuuid, recipientuuid, message, status, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (sender_uuid, recipient_uuid, message_text, status, timestamp,))
            
            conn.commit()
            return True, ""
            
        except sqlite3.Error as e:
            print(f"Error storing message: {e}")
            return False, str(e)
        finally:
            if conn:
                conn.close()

    def search_accounts(self, search_term: str, offset: int):
        """
        Search for user accounts with pagination.
        Returns (list of user dictionaries, total count of matching users)
        """
        try:
            print(f"\nDB Searching for term: '{search_term}' offset {offset}")
            conn = self.connect()
            if conn is None:
                print("Database connection failed")
                return [], 0
                
            cursor = conn.cursor()

            # Convert search term to lowercase
            search_term = search_term.lower()
            
            # First get total count
            count_sql = "SELECT COUNT(*) FROM users WHERE username LIKE '%' || ? || '%'"
            cursor.execute(count_sql, (search_term,))
            
            total_count = cursor.fetchone()[0]
            print(f"Total matching users: {total_count}")
            
            # Get paginated results
            search_sql = """
                    SELECT userid, username 
                    FROM users 
                    WHERE username LIKE '%' || ? || '%'
                    ORDER BY username ASC
                    LIMIT 10 OFFSET ?
                """
            cursor.execute(search_sql, (search_term, offset))
            
            results = [list(row) for row in cursor.fetchall()]
            print(f"\nQuery results: {results}")
            return results, total_count
            
        except sqlite3.Error as e:
            print(f"Error searching accounts: {e}")
            return [], 0
        finally:
            if conn:
                conn.close()

    def get_user_password(self, uuid: int) -> str:
        """
        Get a user's password by their UUID.
        """
        try:
            conn = self.connect()
            if conn is None:
                return None

            cursor = conn.cursor()
            cursor.execute("SELECT hashed_password FROM users WHERE userid = ?", (uuid,))
            result = cursor.fetchone()
            return result[0] if result else None
            
        except sqlite3.Error as e:
            print(f"Error getting user password: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def delete_user(self, uuid: int) -> bool:
        """
        Delete a user by their UUID.
        """
        try:
            conn = self.connect()
            if conn is None:
                print("Failed to connect to database in delete_user")
                return False

            cursor = conn.cursor()
            print(f"Attempting to delete user with UUID: {uuid}")
            
            # First check if user exists
            cursor.execute("SELECT userid FROM users WHERE userid = ?", (uuid,))
            user = cursor.fetchone()
            if not user:
                print(f"No user found with UUID: {uuid}")
                return False
                
            # Delete the user
            cursor.execute("DELETE FROM users WHERE userid = ?", (uuid,))
            conn.commit()
            
            # Verify deletion
            cursor.execute("SELECT userid FROM users WHERE userid = ?", (uuid,))
            if cursor.fetchone() is None:
                print(f"Successfully deleted user with UUID: {uuid}")
                return True
            else:
                print(f"Failed to delete user with UUID: {uuid} - user still exists")
                return False
            
        except sqlite3.Error as e:
            print(f"Error deleting user: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def get_user_username(self, uuid: int) -> dict:
        """
        Get a user's information by their UUID.
        """
        print(f"Getting user info for UUID: {uuid}")
        try:
            conn = self.connect()
            if conn is None:
                return {}

            cursor = conn.cursor()
            cursor.execute("SELECT username FROM users WHERE userid = ?", (uuid,))
            user = cursor.fetchone()
            print(416, user)
            return user[0] if user else None
            
        except sqlite3.Error as e:
            print(f"Error getting user info: {e}")
            return {}
        finally:
            if conn:
                conn.close()

    def load_messages(self, user_uuid, num_messages):
        """Load the most recent messages for a user."""
        try:
            conn = self.connect()
            if conn is None:
                return []

            # get snapshot of num_messages most recent messages
            delivered_sql = """
                SELECT DISTINCT 
                    m.msgid,
                    sender.username AS sender_username, 
                    recipient.username AS recipient_username, 
                    m.message, 
                    m.timestamp
                FROM 
                    messages m
                JOIN 
                    users sender ON m.senderuuid = sender.userid
                JOIN 
                    users recipient ON m.recipientuuid = recipient.userid
                WHERE 
                    (m.status = 'delivered' AND m.recipientuuid = ?)
                    OR (m.senderuuid = ? AND (m.status = 'delivered' OR m.status = 'pending'))
                ORDER BY 
                    m.timestamp DESC
                LIMIT ?;
            """

            # count number of pending messages
            pending_sql = """
                SELECT 
                    COUNT(*)
                FROM 
                    messages
                WHERE 
                    status = 'pending' 
                    AND (recipientuuid = ?);
            """
            cursor = conn.cursor()
            cursor.execute(delivered_sql, (user_uuid, user_uuid, num_messages))
            messages = cursor.fetchall()
            print("messages: ", messages)
            cursor.execute(pending_sql, (user_uuid,))
            pending = cursor.fetchone()[0]
            print("pending: ", pending)
            return [list(message) for message in messages], pending
            
        except sqlite3.Error as e:
            print(f"Error loading messages: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def load_page_data(self, user_uuid):
        """For initial load of the data for the main page."""
        messages, num_pending = self.load_messages(user_uuid, 10)
        accounts, total_count = self.search_accounts("", 0)
        return messages, num_pending, accounts, total_count

    def delete_messages(self, msg_ids):
        """Delete messages by their IDs."""
        try:
            conn = self.connect()
            if conn is None:
                return 0

            # run deletions
            cursor = conn.cursor()
            for msg_id in msg_ids:
                cursor.execute("DELETE FROM messages WHERE msgid = ?", (msg_id,))
                print(f"Deleted message: {msg_id}")
            conn.commit()  # Commit the transaction before verification
            print(f"Deleted messages: {msg_ids}")

            # verify deletion
            sql = "SELECT COUNT(msgid) AS num_remaining FROM messages WHERE msgid IN ({})".format(",".join("?" * len(msg_ids)))
            print("SQL:", sql)
            cursor.execute(sql, msg_ids)
            print(460)
            num_remaining = cursor.fetchone()[0]
            print("NUM REMAINING:", num_remaining)

            num_deleted = len(msg_ids) - num_remaining
            print(f"Deleted {num_deleted} messages")
            return num_deleted

        except sqlite3.Error as e:
            print(f"Error deleting messages: {e}")
            return 0
        finally:
            if conn:
                conn.close()

    def load_undelivered(self, user_uuid, num_messages):
        """Load the most recent undelivered messages for a user."""
        try:
            conn = self.connect()
            if conn is None:
                return []

            sql = """
                SELECT 
                    m.msgid,
                    sender.username AS sender_username, 
                    recipient.username AS recipient_username, 
                    m.message, 
                    m.timestamp
                FROM 
                    messages m
                JOIN 
                    users sender ON m.senderuuid = sender.userid
                JOIN 
                    users recipient ON m.recipientuuid = recipient.userid
                WHERE 
                    m.status = 'pending' 
                    AND m.recipientuuid = ?
                ORDER BY 
                    m.timestamp DESC
                LIMIT ?;
            """
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, (user_uuid, num_messages))
            messages = cursor.fetchall()

            # update status to delivered for these messages
            msg_ids = [msg["msgid"] for msg in messages]
            # cursor.execute("UPDATE messages SET status = 'delivered' WHERE msgid IN ({})".format(",".join("?" * len(msg_ids))), msg_ids)
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("UPDATE messages SET status = 'delivered', timestamp = ? WHERE msgid IN ({})".format(",".join("?" * len(msg_ids))), [current_time] + msg_ids)
            conn.commit()
            return [dict(message) for message in messages]

        except sqlite3.Error as e:
            print(f"Error loading undelivered messages: {e}")
            return []
        finally:
            if conn:
                conn.close()