import unittest
import sys
import os
import json
import socket
import threading
import time
from unittest.mock import patch, MagicMock, call

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from raft_node import RaftNode
from database import MessageDatabase

class TestRaftNode(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Mock configuration for testing
        self.node_id = "0"
        self.nodes = {
            "0": {"host": "127.0.0.1", "port": 51215},
            "1": {"host": "127.0.0.1", "port": 51216},
            "2": {"host": "127.0.0.1", "port": 51217}
        }
        self.client_host = "127.0.0.1"
        self.client_port = 65433

        # Create a temporary database file for testing
        self.db_file = f"test_db_{self.node_id}.db"
        
        # Patch socket to prevent actual network connections
        self.socket_patcher = patch('socket.socket')
        self.mock_socket = self.socket_patcher.start()
        
        # Patch threading to prevent actual thread creation
        self.thread_patcher = patch('threading.Thread')
        self.mock_thread = self.thread_patcher.start()
        
        # Patch MessageDatabase
        self.db_patcher = patch('raft_node.MessageDatabase')
        self.mock_db = self.db_patcher.start()
        self.mock_db_instance = MagicMock()
        self.mock_db.return_value = self.mock_db_instance
        
        # Patch selectors
        self.selector_patcher = patch('selectors.DefaultSelector')
        self.mock_selector = self.selector_patcher.start()
        self.mock_selector_instance = MagicMock()
        self.mock_selector.return_value = self.mock_selector_instance
        
    def tearDown(self):
        """Tear down test fixtures after each test method."""
        self.socket_patcher.stop()
        self.thread_patcher.stop()
        self.db_patcher.stop()
        self.selector_patcher.stop()
        
        # Remove test database if it exists
        if os.path.exists(self.db_file):
            os.remove(self.db_file)

    def test_init(self):
        """Test RaftNode initialization."""
        node = RaftNode(self.node_id, self.nodes, self.client_host, self.client_port)
        
        # Check if properties are correctly initialized
        self.assertEqual(node.node_id, self.node_id)
        self.assertEqual(node.nodes, self.nodes)
        self.assertEqual(node.raft_host, self.nodes[self.node_id]["host"])
        self.assertEqual(node.raft_port, self.nodes[self.node_id]["port"])
        self.assertEqual(node.client_host, self.client_host)
        self.assertEqual(node.client_port, self.client_port)
        
        # Check initial Raft state
        self.assertEqual(node.current_term, 0)
        self.assertIsNone(node.voted_for)
        self.assertEqual(node.state, "follower")
        self.assertIsNone(node.leader_id)
        
        # Check if peer server was started
        self.mock_thread.assert_called()

    @patch('json.dumps')
    def test_send_message(self, mock_dumps):
        """Test sending a message to a peer."""
        # Configure mocks
        mock_dumps.return_value = '{"type": "test"}'
        mock_socket_instance = MagicMock()
        self.mock_socket.return_value = mock_socket_instance
        
        # Create node and test sending message
        node = RaftNode(self.node_id, self.nodes, self.client_host, self.client_port)
        message = {"type": "test"}
        peer_host = "127.0.0.1"
        peer_port = 51216
        
        node.send_message(peer_host, peer_port, message)
        
        # Verify socket operations
        mock_socket_instance.connect.assert_called_with((peer_host, peer_port))
        mock_socket_instance.sendall.assert_called()
        mock_socket_instance.close.assert_called()
        mock_dumps.assert_called_with(message, ensure_ascii=False)

    def test_broadcast(self):
        """Test broadcasting a message to all peers."""
        node = RaftNode(self.node_id, self.nodes, self.client_host, self.client_port)
        
        # Mock send_message method
        node.send_message = MagicMock()
        
        # Test regular message broadcast
        message = {"type": "test"}
        node.broadcast(message)
        
        # Verify send_message was called for each peer
        expected_calls = [
            call(self.nodes["1"]["host"], self.nodes["1"]["port"], message),
            call(self.nodes["2"]["host"], self.nodes["2"]["port"], message)
        ]
        node.send_message.assert_has_calls(expected_calls, any_order=True)
        
        # Test db_update message broadcast
        db_message = {"type": "db_update", "action": "test"}
        node.broadcast(db_message)
        
        # Verify commit index was incremented
        self.assertEqual(node.last_applied, 1)
        
        # Verify message was modified with commit index
        modified_message = {"type": "db_update", "action": "test", "commit_index": 1}
        expected_db_calls = [
            call(self.nodes["1"]["host"], self.nodes["1"]["port"], modified_message),
            call(self.nodes["2"]["host"], self.nodes["2"]["port"], modified_message)
        ]
        node.send_message.assert_has_calls(expected_db_calls, any_order=True)

    def test_process_peer_message_heartbeat(self):
        """Test processing a heartbeat message."""
        node = RaftNode(self.node_id, self.nodes, self.client_host, self.client_port)
        
        # Set initial state
        node.current_term = 1
        node.state = "candidate"  # Should change to follower
        node.last_heartbeat = 0   # Should be updated
        
        # Create heartbeat message
        message = {
            "type": "heartbeat",
            "term": 2,
            "leader_id": "1"
        }
        
        # Process the message
        node.process_peer_message(message)
        
        # Verify state changes
        self.assertEqual(node.current_term, 2)
        self.assertEqual(node.state, "follower")
        self.assertEqual(node.leader_id, "1")
        self.assertGreater(node.last_heartbeat, 0)
        self.assertIsNone(node.voted_for)  # Should reset vote due to new term

    def test_process_peer_message_vote_request(self):
        """Test processing a vote request message."""
        node = RaftNode(self.node_id, self.nodes, self.client_host, self.client_port)
        
        # Mock send_message
        node.send_message = MagicMock()
        
        # Set initial state
        node.current_term = 1
        node.voted_for = None
        
        # Create vote request message
        message = {
            "type": "vote_request",
            "term": 2,
            "candidate_id": "1"
        }
        
        # Process the message
        node.process_peer_message(message)
        
        # Verify state changes
        self.assertEqual(node.current_term, 2)
        self.assertEqual(node.voted_for, "1")
        
        # Verify response was sent
        expected_response = {
            "type": "vote_grant",
            "term": 2,
            "vote_granted": True
        }
        node.send_message.assert_called_with(
            self.nodes["1"]["host"], 
            self.nodes["1"]["port"], 
            expected_response
        )

    def test_process_peer_message_vote_grant(self):
        """Test processing a vote grant message."""
        node = RaftNode(self.node_id, self.nodes, self.client_host, self.client_port)
        
        # Set initial state
        node.state = "candidate"
        node.votes_received = 1  # Already voted for self
        
        # Create vote grant message
        message = {
            "type": "vote_grant",
            "term": 1,
            "vote_granted": True
        }
        
        # Process the message
        node.process_peer_message(message)
        
        # Verify state changes
        self.assertEqual(node.votes_received, 2)

    def test_process_peer_message_db_update(self):
        """Test processing a database update message."""
        node = RaftNode(self.node_id, self.nodes, self.client_host, self.client_port)
        
        # Set initial state
        node.last_applied = 0
        
        # Create db_update message for login
        message = {
            "type": "db_update",
            "action": "login",
            "content": {
                "username": "testuser",
                "password": "testpass",
                "addr": ("127.0.0.1", 12345)
            },
            "commit_index": 1
        }
        
        # Process the message
        node.process_peer_message(message)
        
        # Verify database was updated
        self.mock_db_instance.login.assert_called_with(
            "testuser", "testpass", ("127.0.0.1", 12345)
        )
        
        # Verify commit index was updated
        self.assertEqual(node.last_applied, 1)

    def test_check_peer_status(self):
        """Test checking peer status."""
        # Mock socket connection success
        mock_socket_instance = MagicMock()
        self.mock_socket.return_value = mock_socket_instance
        
        node = RaftNode(self.node_id, self.nodes, self.client_host, self.client_port)
        
        # Test successful connection
        peer = {"host": "127.0.0.1", "port": 51216}
        result = node.check_peer_status(peer)
        self.assertTrue(result)
        mock_socket_instance.connect.assert_called_with((peer["host"], peer["port"]))
        
        # Test connection failure
        mock_socket_instance.connect.side_effect = Exception("Connection failed")
        result = node.check_peer_status(peer)
        self.assertFalse(result)

    @patch('threading.Thread')
    def test_start_election(self, mock_thread):
        """Test starting an election."""
        node = RaftNode(self.node_id, self.nodes, self.client_host, self.client_port)
        
        # Mock broadcast method
        node.broadcast = MagicMock()
        
        # Initial state
        node.current_term = 1
        node.state = "follower"
        
        # Start election
        node.start_election()
        
        # Verify state changes
        self.assertEqual(node.current_term, 2)
        self.assertEqual(node.voted_for, node.node_id)
        self.assertEqual(node.votes_received, 1)
        
        # Verify election message was broadcast
        expected_message = {
            "type": "vote_request",
            "term": 2,
            "candidate_id": node.node_id
        }
        node.broadcast.assert_called_with(expected_message)

if __name__ == '__main__':
    unittest.main()
