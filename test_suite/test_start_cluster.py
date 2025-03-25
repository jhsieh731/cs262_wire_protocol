import unittest
import sys
import os
import json
from unittest.mock import patch, MagicMock

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import start_cluster

class TestStartCluster(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Mock configuration for testing
        self.node_id = "0"
        self.raft_nodes = {
            "0": {"host": "127.0.0.1", "port": 51215},
            "1": {"host": "127.0.0.1", "port": 51216},
            "2": {"host": "127.0.0.1", "port": 51217}
        }
        self.client_nodes = {
            "0": {"host": "127.0.0.1", "port": 65433},
            "1": {"host": "127.0.0.1", "port": 65434},
            "2": {"host": "127.0.0.1", "port": 65435}
        }
        self.accepted_versions = ["1.0"]
        self.protocol = "json"
        
        # Prepare mock config file
        self.config = {
            "accepted_versions": self.accepted_versions,
            "protocol": self.protocol,
            "raft_nodes": self.raft_nodes,
            "client_nodes": self.client_nodes
        }
    
    @patch('start_cluster.RaftNode')
    def test_start_node(self, mock_raft_node):
        """Test the start_node function."""
        # Configure mock
        mock_node_instance = MagicMock()
        mock_raft_node.return_value = mock_node_instance
        
        # Call start_node function
        start_cluster.start_node(
            self.node_id,
            self.raft_nodes,
            self.client_nodes,
            self.accepted_versions,
            self.protocol
        )
        
        # Verify RaftNode was initialized correctly
        mock_raft_node.assert_called_with(
            self.node_id,
            self.raft_nodes,
            self.client_nodes[self.node_id]['host'],
            self.client_nodes[self.node_id]['port']
        )
        
        # Verify methods were called
        mock_node_instance.initialize_client_server.assert_called_once()
        mock_node_instance.run.assert_called_with(self.accepted_versions, self.protocol)
        
if __name__ == '__main__':
    unittest.main()
