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
        self.gui = client.ClientGUI(self.root)
        
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
    
    def test_gui_initialization(self):
        """Test GUI initialization."""
        self.assertIsNotNone(self.gui.login_frame)
        self.assertIsNotNone(self.gui.chat_frame)
        self.assertIsNotNone(self.gui.create_account_frame)
        self.assertIsNotNone(self.gui.error_frame)
        self.assertFalse(self.gui.is_threading)
    
    def test_login_register(self):
        """Test login/register functionality."""
        # Set test credentials
        self.gui.username_entry = tk.Entry(self.root)
        self.gui.password_entry = tk.Entry(self.root)
        self.gui.username_entry.insert(0, "testuser")
        self.gui.password_entry.insert(0, "testpass")
        
        # Mock threading
        with patch('threading.Thread') as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance
            
            # Trigger login
            self.gui.login_register()
            
            # Verify thread creation
            mock_thread.assert_called_once()
            thread_args = mock_thread.call_args[1]
            self.assertEqual(thread_args['daemon'], True)
            
            # Get the lambda function
            lambda_func = thread_args['target']
            # Call it to verify it calls network_thread with correct request
            with patch('client.network_thread') as mock_network_thread:
                lambda_func()
                mock_network_thread.assert_called_once()
                request = mock_network_thread.call_args[0][0]
                self.assertEqual(request['action'], 'login_register')
                self.assertEqual(request['content']['username'], 'testuser')
                self.assertEqual(request['content']['password'], self.gui.hash_password('testpass'))
            
            # Verify thread was started
            mock_thread_instance.start.assert_called_once()
            
            # Verify username was set
            self.assertEqual(self.gui.username, "testuser")
    
    def test_send_message(self):
        """Test message sending functionality."""
        # Setup test data
        self.gui.user_uuid = "test-uuid"
        self.gui.selected_account = "recipient"
        self.gui.entry.insert(0, "Hello, world!")
        
        # Mock thread_send and datetime
        self.gui.thread_send = MagicMock()
        mock_now = datetime.datetime(2025, 2, 10, 12, 0, 0)
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = mock_now
            
            # Send message
            self.gui.send_message()
        
        # Verify request
        expected_request = {
            "action": "send_message",
            "content": {
                "uuid": "test-uuid",
                "recipient_username": "recipient",
                "message": "Hello, world!",
                "timestamp": "2025-02-10 12:00:00"
            }
        }
        self.gui.thread_send.assert_called_once_with(expected_request)
        self.assertEqual(self.gui.entry.get(), "")  # Entry should be cleared
    
    def test_handle_server_response_login(self):
        """Test handling of login response."""
        response = {
            "response_type": "login_register",
            "uuid": "test-uuid"
        }
        
        # Mock create_chat_page
        self.gui.create_chat_page = MagicMock()
        
        # Handle response
        self.gui.handle_server_response(response)
        
        # Verify handling
        self.assertEqual(self.gui.user_uuid, "test-uuid")
        self.gui.create_chat_page.assert_called_once()
    
    def test_handle_server_response_error(self):
        """Test handling of error response."""
        response = {
            "response_type": "error",
            "error": "Test error"
        }
        
        with patch('tkinter.messagebox.showerror') as mock_error:
            self.gui.handle_server_response(response)
            mock_error.assert_called_once_with("Error", "Test error", icon="warning")
    
    def test_load_page_data(self):
        """Test loading page data."""
        self.gui.user_uuid = "test-uuid"
        self.gui.thread_send = MagicMock()
        
        self.gui.load_page_data()
        
        expected_request = {
            "action": "load_page_data",
            "content": {"uuid": "test-uuid"}
        }
        self.gui.thread_send.assert_called_once_with(expected_request)
    
    def test_delete_messages(self):
        """Test message deletion."""
        # Setup test data
        self.gui.msgid_map = {0: "msg1", 1: "msg2"}
        self.gui.messages_listbox = MagicMock()
        self.gui.messages_listbox.curselection.return_value = [0, 1]
        self.gui.thread_send = MagicMock()
        
        # Delete messages
        self.gui.delete_messages()
        
        # Verify request
        expected_request = {
            "action": "delete_messages",
            "content": {"msgids": ["msg1", "msg2"]}
        }
        self.gui.thread_send.assert_called_once_with(expected_request)

if __name__ == '__main__':
    unittest.main()
