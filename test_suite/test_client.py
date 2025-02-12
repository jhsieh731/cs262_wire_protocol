import unittest
from unittest.mock import Mock, MagicMock, patch
import socket
import selectors
import sys
import tkinter as tk
import threading
import datetime
import client
from msg_client import Message

# to run: python3 -m unittest test_suite/test_client.py -v

class TestClient(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Mock selectors
        self.mock_selector = MagicMock()
        self.sel_patcher = patch('selectors.DefaultSelector', return_value=self.mock_selector)
        self.sel_patcher.start()
        
        # Mock socket
        self.mock_socket = MagicMock()
        self.socket_patcher = patch('socket.socket', return_value=self.mock_socket)
        self.socket_patcher.start()
        
        # Mock sys.argv
        self.argv_patcher = patch.object(sys, 'argv', ['client.py', 'localhost', '65432'])
        self.argv_patcher.start()
        
        # Mock Message class
        self.message_patcher = patch('msg_client.Message')
        self.mock_message_class = self.message_patcher.start()
        
        # Create root window and GUI
        self.root = tk.Tk()
        
        # Mock send_to_server and network_thread functions
        self.mock_send_to_server = MagicMock()
        self.mock_network_thread = MagicMock()
        
        # Create GUI with mock functions
        self.gui = client.ClientGUI(self.root, self.mock_send_to_server, self.mock_network_thread)
        
        # Initialize GUI components that would normally be created in create_chat_page
        self.gui.entry = tk.Entry(self.root)
        self.gui.messages_listbox = tk.Listbox(self.root)
        
        # Store original module attributes
        self.original_sel = getattr(client, 'sel', None)
        
        # Set mocked selector in client module
        setattr(client, 'sel', self.mock_selector)
    
    def tearDown(self):
        """Clean up test fixtures after each test method."""
        # Restore original module attributes
        if self.original_sel is not None:
            setattr(client, 'sel', self.original_sel)
        
        # Stop all patches
        self.sel_patcher.stop()
        self.socket_patcher.stop()
        self.argv_patcher.stop()
        self.message_patcher.stop()
        
        # Destroy root window
        self.root.destroy()
    
    def test_initialize_client(self):
        """Test client initialization."""
        # Mock selectors.DefaultSelector
        mock_selector = MagicMock()
        with patch('selectors.DefaultSelector', return_value=mock_selector):
            # Call initialize_client
            test_host = 'test_host'
            test_port = 12345
            sel = client.initialize_client(test_host, test_port)
            
            # Verify selector was created
            self.assertEqual(sel, mock_selector)
            
            # Verify global variables were set
            self.assertEqual(client.host, test_host)
            self.assertEqual(client.port, test_port)
            self.assertEqual(client.sel, mock_selector)

    def test_send_to_server(self):
        """Test sending message to server."""
        # Mock Message object
        mock_message = MagicMock()
        mock_key = MagicMock()
        mock_key.data = mock_message
        
        # Setup selector mock
        self.mock_selector.get_map.return_value = {'mock_key': mock_key}
        
        # Send test request
        request = {"action": "test_action"}
        client.send_to_server(request)
        
        # Verify message handling
        self.assertEqual(mock_message.request, request)
        mock_message.queue_request.assert_called_once()
        mock_message._set_selector_events_mask.assert_called_once_with("w")
    
    def test_network_thread(self):
        """Test network thread event handling."""
        request = {"action": "test"}
        
        # Mock message and selector events
        mock_message = MagicMock()
        mock_key = MagicMock()
        mock_key.data = mock_message
        
        # Setup selector behavior
        self.mock_selector.select.return_value = [(mock_key, selectors.EVENT_READ)]
        # Return empty map immediately to exit loop
        self.mock_selector.get_map.return_value = {}
        
        # Run network thread
        client.network_thread(request)
        
        # Verify selector was closed
        self.mock_selector.close.assert_called_once()

    def test_start_connection(self):
        """Test connection initialization."""
        request = {"action": "test"}
        client.start_connection('localhost', 65432, self.gui, request)
        
        # Verify socket setup
        self.mock_socket.setblocking.assert_called_once_with(False)
        self.mock_socket.connect_ex.assert_called_once_with(('localhost', 65432))
        
        # Verify selector registration
        self.mock_selector.register.assert_called_once()
        register_args = self.mock_selector.register.call_args
        self.assertEqual(register_args[0][0], self.mock_socket)
        self.assertEqual(register_args[0][1], selectors.EVENT_READ | selectors.EVENT_WRITE)
        # Verify Message instance was created with correct parameters
        self.mock_message_class.assert_called_once_with(
            self.mock_selector,
            self.mock_socket,
            ('localhost', 65432),
            self.gui,
            request
        )

if __name__ == '__main__':
    unittest.main()
