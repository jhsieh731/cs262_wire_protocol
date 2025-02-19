import sqlite3
from typing import List, Tuple, Optional
from logger import set_logger

logger = set_logger("db", "db.log")

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
            logger.error(f"Error connecting to database: {e}")
            return None

    def create_tables(self):
        """Create the messages table if it doesn't exist."""
        create_users_sql = """
        CREATE TABLE IF NOT EXISTS users (
            userid INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL
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
                logger.error("Error: Could not establish database connection")
        except sqlite3.Error as e:
            logger.error(f"Error creating table: {e}")
        finally:
            if conn:
                conn.close()

    def check_username(self, username: str):
        """Check if a username already exists in the database."""
        try:
            conn = self.connect()
            if conn is None or username is None:
                return None, False

            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", (username,))
            return cursor.fetchone()[0] > 0, True
            
        except sqlite3.Error as e:
            logger.error(f"Error checking username: {e}")
            return None, False
        finally:
            if conn:
                conn.close()

    def register(self, username: str, password: str):
        """Register a new user."""
        try:
            conn = self.connect()
            if conn is None or not all([username, password]):
                return None, "Database connection failed"

            # add user to database
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, hashed_password) VALUES (?, ?);",
                (username, password)
            )
            conn.commit()
            uuid = cursor.lastrowid
            return uuid, ""
            
        except sqlite3.Error as e:
            logger.error(f"Error registering user: {e}")
            return None, str(e)
        finally:
            if conn:
                conn.close()

    def login(self, username: str, password: str):
        """Login if the username and password match."""
        login_sql = """SELECT * FROM users WHERE username = ? AND hashed_password = ?;"""

        # Guard for empty strings
        if not username or not password:
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

            # Check if multiple users (or none) have the same username and password
            if len(res) != 1:
                logger.error("Error: multiple users with the same username and password")
                return []
            
            return [dict(res[0])]

        except sqlite3.Error as e:
            logger.error(f"Error in login: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def load_private_chat(self, current_uuid: int, other_username: str) -> List[dict]:
        """Load all messages between current user and other user.
        
        Args:
            current_uuid: UUID of the current user
            other_username: Username of the other user
            
        Returns:
            List of messages with sender, recipient, and message content
        """
        try:
            conn = self.connect()
            if not conn:
                return []
                
            cursor = conn.cursor()
            
            # First get the UUID of the other user
            cursor.execute("""
                SELECT userid FROM users WHERE username = ?
            """, (other_username,))
            result = cursor.fetchone()
            if not result:
                return []
                
            other_uuid = result[0]
            
            # Get all messages between these users
            cursor.execute("""
                SELECT m.message, m.timestamp, s.username as sender_username, r.username as recipient_username, status
                FROM messages m
                JOIN users s ON m.senderuuid = s.userid
                JOIN users r ON m.recipientuuid = r.userid
                WHERE (m.senderuuid = ? AND m.recipientuuid = ?)
                   OR (m.senderuuid = ? AND m.recipientuuid = ?)
                ORDER BY m.timestamp ASC
            """, (current_uuid, other_uuid, other_uuid, current_uuid))
            
            messages = [{
                "message": row[0],
                "timestamp": row[1],
                "sender_username": row[2],
                "recipient_username": row[3],
                "status": row[4]
            } for row in cursor.fetchall()]
            
            return messages
            
        except sqlite3.Error as e:
            logger.error(f"Error loading private chat: {e}")
            return []
            
    def get_user_uuid(self, username: str) -> Tuple[bool, str, Optional[int]]:
        """Get a user's UUID by their username."""
        try:
            conn = self.connect()
            if conn is None:
                return False, "Database connection failed", None
            
            cursor = conn.cursor()
            cursor.execute("SELECT userid FROM users WHERE username = ?", (username,))
            result = cursor.fetchone()
            
            if not result:
                return False, f"User {username} not found", None
                
            return True, "", result[0]
            
        except sqlite3.Error as e:
            logger.error(f"Error getting user UUID: {e}")
            return False, str(e), None
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
            logger.error(f"Error getting associated socket: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def store_message(self, sender_uuid: int, recipient_username: str, message: str, status: bool, timestamp: str) -> Tuple[bool, str]:
        """Store a message in the database."""
        try:
            conn = self.connect()
            if conn is None:
                return False, "Database connection failed"

            cursor = conn.cursor()
            
            # Get recipient's UUID
            cursor.execute("SELECT userid FROM users WHERE username = ?", (recipient_username,))
            recipient = cursor.fetchone()
            if not recipient:
                return False, f"User {recipient_username} not found"
                
            recipient_uuid = recipient[0]
            
            # Store the message
            cursor.execute("""
                INSERT INTO messages (senderuuid, recipientuuid, message, status, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (sender_uuid, recipient_uuid, message, 'delivered' if status else 'pending', timestamp))
            
            conn.commit()
            return True, ""
            
        except sqlite3.Error as e:
            logger.error(f"Error storing message: {e}")
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
            logger.info(f"DB Searching for term: '{search_term}' offset {offset}")
            conn = self.connect()
            if conn is None:
                logger.error("Database connection failed")
                return [], 0
                
            cursor = conn.cursor()

            # Convert search term to lowercase
            search_term = search_term.lower().replace("*", "%")

            if not search_term:
                search_term = "%"  # Match all users if search term is empty
            
            # First get total count
            count_sql = "SELECT COUNT(*) FROM users WHERE username LIKE ?"
            cursor.execute(count_sql, (search_term,))
            
            total_count = cursor.fetchone()[0]
            logger.info(f"Total matching users: {total_count}")
            
            # Get paginated results
            search_sql = """
                    SELECT userid, username 
                    FROM users 
                    WHERE username LIKE ?
                    ORDER BY username ASC
                    LIMIT 10 OFFSET ?
                """
            cursor.execute(search_sql, (search_term, offset))
            
            results = [list(row) for row in cursor.fetchall()]
            logger.info(f"Query results: {results}")
            return results, total_count
            
        except sqlite3.Error as e:
            logger.error(f"Error searching accounts: {e}")
            return [], 0
        finally:
            if conn:
                conn.close()

    def get_user_password(self, uuid: int) -> Optional[str]:
        """Get a user's hashed password."""
        try:
            conn = self.connect()
            if conn is None:
                return None

            cursor = conn.cursor()
            cursor.execute(
                "SELECT hashed_password FROM users WHERE userid = ?",
                (uuid,)
            )
            result = cursor.fetchone()
            return result[0] if result else None

        except sqlite3.Error as e:
            logger.error(f"Error getting user password: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def delete_user_messages(self, uuid: int) -> List[Tuple[int, int]]:
        """Delete all messages for a user and return affected users with message counts."""
        try:
            conn = self.connect()
            if conn is None:
                return []

            cursor = conn.cursor()
            
            # First get all affected users and their message counts
            cursor.execute("""
                SELECT DISTINCT 
                    CASE 
                        WHEN senderuuid = ? THEN recipientuuid 
                        ELSE senderuuid 
                    END as affected_uuid,
                    COUNT(*) as msg_count
                FROM messages 
                WHERE senderuuid = ? OR recipientuuid = ?
                GROUP BY affected_uuid
            """, (uuid, uuid, uuid))
            
            affected_users = [(row[0], row[1]) for row in cursor.fetchall()]
            
            # Delete all messages
            cursor.execute("""
                DELETE FROM messages 
                WHERE senderuuid = ? OR recipientuuid = ?
            """, (uuid, uuid))
            
            conn.commit()
            return affected_users
            
        except sqlite3.Error as e:
            logger.error(f"Error deleting user messages: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def delete_user(self, uuid: int) -> bool:
        """Delete a user by their UUID."""
        try:
            conn = self.connect()
            if conn is None:
                return False

            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE userid = ?", (uuid,))
            conn.commit()
            
            return cursor.rowcount > 0
            
        except sqlite3.Error as e:
            logger.error(f"Error deleting user: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def get_user_username(self, uuid: int) -> Optional[str]:
        """Get a user's username by their UUID."""
        try:
            conn = self.connect()
            if conn is None:
                return None

            cursor = conn.cursor()
            cursor.execute("SELECT username FROM users WHERE userid = ?", (uuid,))
            result = cursor.fetchone()
            return result[0] if result else None
            
        except sqlite3.Error as e:
            logger.error(f"Error getting username: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def load_messages(self, user_uuid: int, num_messages: int) -> Tuple[List[dict], int]:
        """Load messages for a user and return total undelivered count."""
        try:
            conn = self.connect()
            if conn is None:
                return [], 0

            cursor = conn.cursor()
            
            # Get messages
            cursor.execute("""
                SELECT 
                    m.msgid,
                    s.username as sender_username,
                    r.username as recipient_username,
                    m.message,
                    m.timestamp,
                    m.status
                FROM messages m
                JOIN users s ON m.senderuuid = s.userid
                JOIN users r ON m.recipientuuid = r.userid
                WHERE 
                    (m.senderuuid = ? OR m.recipientuuid = ?)
                    AND (m.status != 'pending' OR m.senderuuid = ?)
                ORDER BY m.timestamp DESC
                LIMIT ?
            """, (user_uuid, user_uuid, user_uuid, num_messages))
            
            messages = cursor.fetchall()
            
            # Get undelivered count
            cursor.execute("""
                SELECT COUNT(*)
                FROM messages
                WHERE recipientuuid = ? AND status = 'pending'
            """, (user_uuid,))
            
            undelivered_count = cursor.fetchone()[0]
            
            return messages, undelivered_count
            
        except sqlite3.Error as e:
            logger.error(f"Error loading messages: {e}")
            return [], 0
        finally:
            if conn:
                conn.close()

    def load_page_data(self, user_uuid):
        """For initial load of the data for the main page."""
        messages, num_pending = self.load_messages(user_uuid, 10)
        accounts, total_count = self.search_accounts("", 0)
        return messages, num_pending, accounts, total_count

    def delete_messages(self, msg_ids: List[int]) -> List[Tuple[int, int]]:
        """Delete messages and return affected users with message counts."""
        try:
            conn = self.connect()
            if conn is None:
                return []

            cursor = conn.cursor()
            
            # First get affected users and their message counts
            placeholders = ','.join('?' * len(msg_ids))
            cursor.execute(f"""
                SELECT 
                    userid,
                    COUNT(*) as msg_count
                FROM (
                    SELECT DISTINCT 
                        CASE 
                            WHEN senderuuid = userid THEN senderuuid 
                            ELSE recipientuuid 
                        END as userid
                    FROM messages 
                    CROSS JOIN users
                    WHERE msgid IN ({placeholders})
                ) t
                GROUP BY userid
            """, msg_ids)
            
            affected_users = [(row[0], row[1]) for row in cursor.fetchall()]
            
            # Delete the messages
            cursor.execute(f"DELETE FROM messages WHERE msgid IN ({placeholders})", msg_ids)
            conn.commit()
            
            return affected_users
            
        except sqlite3.Error as e:
            logger.error(f"Error deleting messages: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def load_undelivered(self, user_uuid: int, num_messages: int) -> List[dict]:
        """Load undelivered messages for a user and mark them as delivered."""
        try:
            conn = self.connect()
            if conn is None:
                return []

            cursor = conn.cursor()
            
            # Get undelivered messages
            cursor.execute("""
                SELECT 
                    m.msgid,
                    s.username as sender_username,
                    r.username as recipient_username,
                    m.message,
                    m.timestamp
                FROM messages m
                JOIN users s ON m.senderuuid = s.userid
                JOIN users r ON m.recipientuuid = r.userid
                WHERE 
                    m.recipientuuid = ?
                    AND m.status = 'pending'
                ORDER BY m.timestamp DESC
                LIMIT ?
            """, (user_uuid, num_messages))
            
            messages = cursor.fetchall()
            
            # Mark messages as delivered
            msg_ids = [msg[0] for msg in messages]
            if msg_ids:
                placeholders = ','.join('?' * len(msg_ids))
                cursor.execute(f"""
                    UPDATE messages 
                    SET status = 'delivered' 
                    WHERE msgid IN ({placeholders})
                """, msg_ids)
                conn.commit()
            
            return [
                {
                    'msgid': msg[0],
                    'sender_username': msg[1],
                    'recipient_username': msg[2],
                    'message': msg[3],
                    'timestamp': msg[4],
                    'status': 'delivered'
                }
                for msg in messages
            ]
            
        except sqlite3.Error as e:
            logger.error(f"Error loading undelivered messages: {e}")
            return []
        finally:
            if conn:
                conn.close()