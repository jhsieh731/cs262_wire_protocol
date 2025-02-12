import unittest
import sys
import os
import sqlite3

# to run: python3 -m unittest test_suite/test_database.py -v


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import MessageDatabase

class TestDatabase(unittest.TestCase):
    def setUp(self):
        # Set up a temporary database for testing
        self.db_file = "test_database.db"
        # Remove existing test database if it exists
        if os.path.exists(self.db_file):
            os.remove(self.db_file)
        self.db = MessageDatabase(self.db_file)

        # Create test users
        self.test_user1 = {
            "username": "testuser1",
            "password": "password123",
            "socket": "127.0.0.1:8000"
        }
        self.test_user2 = {
            "username": "testuser2",
            "password": "password456",
            "socket": "127.0.0.1:8001"
        }

    def tearDown(self):
        # Close the database connection and remove the temporary database file
        self.db.close()
        if os.path.exists(self.db_file):
            os.remove(self.db_file)


    def register_user(self, username, password, socket):
        """Helper method to register a user."""
        is_used, _ = self.db.check_username(username)
        if not is_used:
            self.db.register(username, password, socket)


    def test_close(self):
        """Test database connection closing."""
        # Get initial connection
        conn = self.db.connect()
        self.assertIsNotNone(conn)
        self.assertIsNotNone(self.db.conn)
        
        # Close connection
        self.db.close()
        self.assertIsNone(self.db.conn)
        
        # Test that operations fail after closing
        with self.assertRaises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_connect(self):
        """Test database connection creation."""
        # Close any existing connection
        self.db.close()
        
        # Test successful connection
        conn = self.db.connect()
        self.assertIsNotNone(conn)
        self.assertIsInstance(conn, sqlite3.Connection)
        
        # Test connection with invalid path
        invalid_db = MessageDatabase("/invalid/path/db.db")
        conn = invalid_db.connect()
        self.assertIsNone(conn)

    def test_create_tables(self):
        """Test database table creation."""
        # Drop existing tables if they exist
        conn = self.db.connect()
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS messages")
        cursor.execute("DROP TABLE IF EXISTS users")
        conn.commit()
        
        # Create tables
        self.db.create_tables()
        
        # Verify tables exist and have correct schema
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        table_names = [table[0] for table in tables]
        
        self.assertIn("users", table_names)
        self.assertIn("messages", table_names)
        
        # Verify users table schema
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        self.assertIn("userid", column_names)
        self.assertIn("username", column_names)
        self.assertIn("hashed_password", column_names)
        self.assertIn("associated_socket", column_names)
        
        # Verify messages table schema
        cursor.execute("PRAGMA table_info(messages)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        self.assertIn("msgid", column_names)
        self.assertIn("senderuuid", column_names)
        self.assertIn("recipientuuid", column_names)
        self.assertIn("message", column_names)
        self.assertIn("status", column_names)
        self.assertIn("timestamp", column_names)

    def test_check_username(self):
        # Create test user
        self.register_user(self.test_user1["username"], self.test_user1["password"], self.test_user1["socket"])

        # Test checking existing username
        exists, _ = self.db.check_username(self.test_user1["username"])
        self.assertTrue(exists)

    def test_get_user_uuid(self):
        # Create test user first
        self.register_user(self.test_user1["username"], self.test_user1["password"], self.test_user1["socket"])


        # Test getting UUID of existing user
        success, error, uuid = self.db.get_user_uuid(self.test_user1["username"])
        self.assertTrue(success)
        self.assertEqual(error, "")
        self.assertIsNotNone(uuid)

        # Test getting UUID of non-existent user
        success, error, uuid = self.db.get_user_uuid("nonexistentuser")
        self.assertFalse(success)
        self.assertNotEqual(error, "")
        self.assertEqual(uuid, "")

    def test_get_associated_socket(self):
        # Create test user
        self.register_user(self.test_user1["username"], self.test_user1["password"], self.test_user1["socket"])
        success, error, uuid = self.db.get_user_uuid(self.test_user1["username"])


        # Test getting socket of existing user
        socket = self.db.get_associated_socket(uuid)
        self.assertEqual(socket, self.test_user1["socket"])

        # Test getting socket of non-existent user
        socket = self.db.get_associated_socket(999)  # Non-existent UUID
        self.assertIsNone(socket)

    def test_store_message(self):
        """Test message storage functionality."""
        # Create test users first
        self.register_user(self.test_user1["username"], self.test_user1["password"], self.test_user1["socket"])
        self.register_user(self.test_user2["username"], self.test_user2["password"], self.test_user2["socket"])
        success1, error1, uuid1 = self.db.get_user_uuid(self.test_user1["username"])
        success2, error2, uuid2 = self.db.get_user_uuid(self.test_user2["username"])

        
        # Test storing a valid message
        success, error = self.db.store_message(uuid1, uuid2, "Test message", True, "2025-02-10 10:00:00")
        self.assertTrue(success)
        self.assertEqual(error, "")
        
        # Test storing message with invalid sender
        success, error = self.db.store_message("999", uuid2, "Test message", True, "2025-02-10 10:00:00")
        self.assertFalse(success)
        self.assertNotEqual(error, "")
        
        # Test storing message with invalid recipient
        success, error = self.db.store_message(uuid1, "999", "Test message", True, "2025-02-10 10:00:00")
        self.assertFalse(success)
        self.assertNotEqual(error, "")
        
        # Verify message was stored correctly
        conn = self.db.connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM messages WHERE senderuuid = ? AND recipientuuid = ?", (uuid1, uuid2))
        messages = cursor.fetchall()
        self.assertTrue(len(messages) > 0)
        self.assertTrue(any(msg["message"] == "Test message" for msg in messages))
        
    def test_search_accounts(self):
        # Create test users first
        self.register_user(self.test_user1["username"], self.test_user1["password"], self.test_user1["socket"])
        self.register_user(self.test_user2["username"], self.test_user2["password"], self.test_user2["socket"])

        # Test searching with empty string (should return all users)
        accounts, total = self.db.search_accounts("", 0)
        self.assertEqual(total, 2)
        self.assertEqual(len(accounts), 2)

        # Test searching with specific term
        accounts, total = self.db.search_accounts("testuser1", 0)
        self.assertEqual(total, 1)
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0][1], self.test_user1["username"].lower())  # username is second column

        # Test searching with non-existent term
        accounts, total = self.db.search_accounts("nonexistent", 0)
        self.assertEqual(total, 0)
        self.assertEqual(len(accounts), 0)

    def test_get_user_password(self):
        # Create test user first
        self.register_user(self.test_user1["username"], self.test_user1["password"], self.test_user1["socket"])
        success, error, uuid = self.db.get_user_uuid(self.test_user1["username"])

        # Test getting password of existing user
        password = self.db.get_user_password(uuid)
        self.assertEqual(password, self.test_user1["password"])

        # Test getting password of non-existent user
        password = self.db.get_user_password(999)  # Non-existent UUID
        self.assertIsNone(password)

    def test_delete_user(self):
        # Create test user first
        self.register_user(self.test_user1["username"], self.test_user1["password"], self.test_user1["socket"])
        success, error, uuid = self.db.get_user_uuid(self.test_user1["username"])

        # Test deleting existing user
        success = self.db.delete_user(uuid)
        self.assertTrue(success)

        # Verify user is deleted
        password = self.db.get_user_password(uuid)
        self.assertIsNone(password)

        # Test deleting non-existent user
        success = self.db.delete_user(999)  # Non-existent UUID
        self.assertFalse(success)

    def test_get_user_username(self):
        # Create test user
        self.register_user(self.test_user1["username"], self.test_user1["password"], self.test_user1["socket"])
        success, error, uuid = self.db.get_user_uuid(self.test_user1["username"])

        # Test getting username of existing user
        username = self.db.get_user_username(uuid)
        self.assertEqual(username, self.test_user1["username"])

        # Test getting username of non-existent user
        username = self.db.get_user_username(999)  # Non-existent UUID
        self.assertIsNone(username)

    def test_load_messages(self):
        # Create test users
        self.register_user(self.test_user1["username"], self.test_user1["password"], self.test_user1["socket"])
        self.register_user(self.test_user2["username"], self.test_user2["password"], self.test_user2["socket"])
        success1, error1, uuid1 = self.db.get_user_uuid(self.test_user1["username"])
        success2, error2, uuid2 = self.db.get_user_uuid(self.test_user2["username"])

        # Store some test messages with different timestamps
        self.db.store_message(uuid1, uuid2, "Oldest Message", True, "2025-02-10 10:00:00")
        self.db.store_message(uuid1, uuid2, "Middle Message", True, "2025-02-10 10:01:00")
        self.db.store_message(uuid1, uuid2, "Newest Message", True, "2025-02-10 10:02:00")

        # Test loading messages for user2

        messages, pending = self.db.load_messages(uuid2, 10)
        self.assertEqual(len(messages), 3)  # Should see all messages

        # Verify messages are in correct order (newest to oldest)
        messages_list = [msg[3] for msg in messages]  # message is the 4th column
        self.assertEqual(messages_list[0], "Newest Message")
        self.assertEqual(messages_list[1], "Middle Message")
        self.assertEqual(messages_list[2], "Oldest Message")

    def test_load_page_data(self):
        # Create test users
        self.register_user(self.test_user1["username"], self.test_user1["password"], self.test_user1["socket"])
        self.register_user(self.test_user2["username"], self.test_user2["password"], self.test_user2["socket"])
        success1, error1, uuid1 = self.db.get_user_uuid(self.test_user1["username"])
        success2, error2, uuid2 = self.db.get_user_uuid(self.test_user2["username"])

        # Store some test messages
        self.db.store_message(uuid1, uuid2, "Message 1", True, "2025-02-10 10:00:00")
        self.db.store_message(uuid2, uuid1, "Message 2", False, "2025-02-10 10:01:00")

        # Test loading page data for user1
        messages, num_pending, accounts, total_count = self.db.load_page_data(uuid1)

        # Verify messages
        self.assertTrue(len(messages) > 0)
        self.assertEqual(num_pending, 1)  # One pending message

        # Verify accounts
        self.assertEqual(len(accounts), 2)  # Both test users should be listed
        self.assertEqual(total_count, 2)

    def test_delete_messages(self):
        # Create test users and messages first
        self.register_user(self.test_user1["username"], self.test_user1["password"], self.test_user1["socket"])
        self.register_user(self.test_user2["username"], self.test_user2["password"], self.test_user2["socket"])
        success1, error1, uuid1 = self.db.get_user_uuid(self.test_user1["username"])
        success2, error2, uuid2 = self.db.get_user_uuid(self.test_user2["username"])

        # Store some messages
        self.db.store_message(uuid1, uuid2, "Message 1", True, "2025-02-10 10:00:00")
        self.db.store_message(uuid1, uuid2, "Message 2", True, "2025-02-10 10:01:00")

        # Get message IDs
        conn = self.db.connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT msgid FROM messages WHERE recipientuuid = ?", (uuid2,))
        messages = cursor.fetchall()
        msg_ids = [msg["msgid"] for msg in messages]

        # Test deleting messages
        num_deleted = self.db.delete_messages(msg_ids)
        self.assertEqual(num_deleted, len(msg_ids))

        # Verify messages are deleted
        cursor.execute("SELECT COUNT(*) FROM messages WHERE recipientuuid = ?", (uuid2,))
        count = cursor.fetchone()[0]
        self.assertEqual(count, 0)

    def test_load_undelivered(self):
        # Create test users first
        self.register_user(self.test_user1["username"], self.test_user1["password"], self.test_user1["socket"])
        self.register_user(self.test_user2["username"], self.test_user2["password"], self.test_user2["socket"])
        success1, error1, uuid1 = self.db.get_user_uuid(self.test_user1["username"])
        success2, error2, uuid2 = self.db.get_user_uuid(self.test_user2["username"])

        # Store messages with different statuses
        self.db.store_message(uuid1, uuid2, "Pending message", False, "2025-02-10 10:00:00")
        self.db.store_message(uuid1, uuid2, "Delivered message", True, "2025-02-10 10:01:00")

        # Test loading undelivered messages
        undelivered = self.db.load_undelivered(uuid2, 10)
        self.assertEqual(len(undelivered), 1)
        self.assertEqual(undelivered[0]["message"], "Pending message")

if __name__ == "__main__":
    unittest.main()