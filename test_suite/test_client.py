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

# to run: python3 -m pytest test_suite/test_client.py -v --cov=client --cov-report=term-missing

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
            test_protocol = 'json'
            sel = client.initialize_client(test_host, test_port, test_protocol)
            
            # Verify selector was created
            self.assertEqual(sel, mock_selector)
            
            # Verify global variables were set
            self.assertEqual(client.host, test_host)
            self.assertEqual(client.port, test_port)
            self.assertEqual(client.sel, mock_selector)

    def test_send_to_server(self):
        """Test sending message to server."""
        # Test sending with uninitialized client
        setattr(client, 'sel', None)
        client.send_to_server({"action": "test"})
        
        # Restore selector and test normal sending
        setattr(client, 'sel', self.mock_selector)
        
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
        
        # Test exception handling
        self.mock_selector.get_map.side_effect = Exception("Test error")
        client.send_to_server(request)  # Should handle exception gracefully
    
    def test_network_thread(self):
        """Test network thread event handling."""
        request = {"action": "test"}
        
        # Mock message and selector events
        mock_message = MagicMock()
        mock_key = MagicMock()
        mock_key.data = mock_message
        
        # Test normal event processing
        self.mock_selector.select.side_effect = [
            [(mock_key, selectors.EVENT_READ)],  # First call returns event
            []  # Second call returns no events
        ]
        self.mock_selector.get_map.side_effect = [{1: mock_key}, {}]  # First has key, then empty to exit
        client.network_thread(request)
        mock_message.process_events.assert_called_with(selectors.EVENT_READ)
        
        # Reset mocks
        self.mock_selector.select.reset_mock()
        self.mock_selector.get_map.reset_mock()
        mock_message.process_events.reset_mock()
        mock_message.close.reset_mock()
        
        # Test exception in process_events
        self.mock_selector.select.side_effect = [
            [(mock_key, selectors.EVENT_READ)],  # First call returns event
            []  # Second call returns no events
        ]
        self.mock_selector.get_map.side_effect = [{1: mock_key}, {}]
        mock_message.process_events.side_effect = Exception("Test error")
        client.network_thread(request)
        mock_message.close.assert_called_once()
        
        # Reset mocks
        self.mock_selector.select.reset_mock()
        self.mock_selector.get_map.reset_mock()
        mock_message.process_events.reset_mock()
        mock_message.close.reset_mock()
        
        # Test keyboard interrupt
        self.mock_selector.select.side_effect = KeyboardInterrupt()
        client.network_thread(request)
        
        # Verify selector was closed in all cases
        self.assertEqual(self.mock_selector.close.call_count, 3)

    def test_start_connection(self):
        """Test connection initialization."""
        request = {"action": "test"}
        
        # Test normal connection
        client.start_connection(self.gui, request)
        
        # Verify socket setup
        self.mock_socket.setblocking.assert_called_once_with(False)
        self.mock_socket.connect_ex.assert_called_once_with(('test_host', 12345))
        
        # Verify selector registration
        self.mock_selector.register.assert_called_once()
        register_args = self.mock_selector.register.call_args
        self.assertEqual(register_args[0][0], self.mock_socket)
        self.assertEqual(register_args[0][1], selectors.EVENT_READ | selectors.EVENT_WRITE)
        
        # Verify Message instance was created with correct parameters
        self.mock_message_class.assert_called_once_with(
            self.mock_selector,
            self.mock_socket,
            ('test_host', 12345),
            self.gui,
            request,
            'json'
        )
        
    def test_main_error_cases(self):
        """Test main function error cases."""
        # Test with incorrect number of arguments
        test_args = ['client.py']
        with patch('sys.argv', test_args):
            with patch('sys.exit') as mock_exit:
                with patch('client.logger') as mock_logger:
                    with patch('client.initialize_client') as mock_init:
                        try:
                            client.main()
                        except (SystemExit, IndexError):
                            pass
                        mock_logger.info.assert_called_with(f"Usage: {test_args[0]} <host> <port> <protocol>")
                        mock_exit.assert_called_once_with(1)
                        mock_init.assert_not_called()
        
        # Test with invalid port
        test_args = ['client.py', 'localhost', 'invalid', 'json']
        with patch('sys.argv', test_args):
            with patch('sys.exit') as mock_exit:
                with patch('client.logger') as mock_logger:
                    with patch('client.initialize_client') as mock_init:
                        # Reset mock_exit and mock_logger
                        mock_exit.reset_mock()
                        mock_logger.reset_mock()
                        try:
                            client.main()
                        except SystemExit:
                            pass
                        mock_logger.info.assert_called_with("Error: Port must be a number")
                        mock_exit.assert_called_once_with(1)
                        mock_init.assert_not_called()
    
    def test_main_success(self):
        """Test main function successful execution."""
        # Test normal execution
        test_args = ['client.py', 'localhost', '65432', 'json']
        with patch('sys.argv', test_args):
            with patch('tkinter.Tk.mainloop') as mock_mainloop:
                with patch('client.initialize_client', return_value=self.mock_selector) as mock_init:
                    with patch('tkinter.Tk') as mock_tk:
                        with patch('client.ClientGUI') as mock_gui:
                            try:
                                client.main()
                            except Exception:
                                pass
                            mock_init.assert_called_once_with('localhost', 65432, 'json')
                            mock_mainloop.assert_called_once()

if __name__ == '__main__':
    unittest.main()
