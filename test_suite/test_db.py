
import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import MessageDatabase

class TestDatabase(unittest.TestCase):
    def setUp(self):
        # Set up a temporary database for testing
        self.db_file = "test_database.db"
        self.db = MessageDatabase(self.db_file)
        self.db.connect()
        self.db.create_tables()

    def tearDown(self):
        # Close the database connection and remove the temporary database file
        self.db.close()
        os.remove(self.db_file)

    # TODO: Add test methods

if __name__ == "__main__":
    unittest.main()