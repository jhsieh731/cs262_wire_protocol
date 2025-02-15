import unittest
from unittest.mock import Mock, patch, MagicMock
import selectors
import sys
import json
import server
from msg_server import Message

# To run: python3 -m unittest test_suite/test_server.py -v

class TestServer(unittest.TestCase):
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
        self.argv_patcher = patch.object(sys, 'argv', ['server.py', 'localhost', '65432'])
        self.argv_patcher.start()
        
        # Store original module attributes
        self.original_sel = getattr(server, 'sel', None)
        self.original_lsock = getattr(server, 'lsock', None)
        
        # Set mocked selector in server module
        setattr(server, 'sel', self.mock_selector)
    
    def tearDown(self):
        """Clean up test fixtures after each test method."""
        # Restore original module attributes
        if self.original_sel is not None:
            setattr(server, 'sel', self.original_sel)
        if self.original_lsock is not None:
            setattr(server, 'lsock', self.original_lsock)
        
        # Stop all patches
        self.sel_patcher.stop()
        self.socket_patcher.stop()
        self.argv_patcher.stop()
    
    def test_server_initialization(self):
        """Test server socket initialization and setup."""
        # Initialize server with specific host and port
        lsock = server.initialize_server('localhost', 65432)
        
        # Check socket setup
        self.mock_socket.bind.assert_called_once_with(('localhost', 65432))
        self.mock_socket.listen.assert_called_once()
        self.mock_socket.setblocking.assert_called_once_with(False)
        
        # Check selector registration
        self.mock_selector.register.assert_called_once_with(
            self.mock_socket, 
            selectors.EVENT_READ, 
            data=None
        )
        
        # Check return value
        self.assertEqual(lsock, self.mock_socket)
        
    def test_server_initialization_bind_error(self):
        """Test server initialization with bind error."""
        self.mock_socket.bind.side_effect = OSError("Address already in use")
        
        with self.assertRaises(SystemExit) as cm:
            server.initialize_server('localhost', 65432)
        self.assertEqual(cm.exception.code, 1)
        self.mock_socket.close.assert_called_once()
        
    def test_server_initialization_general_error(self):
        """Test server initialization with general error."""
        self.mock_socket.bind.side_effect = Exception("Unknown error")
        
        with self.assertRaises(SystemExit) as cm:
            server.initialize_server('localhost', 65432)
        self.assertEqual(cm.exception.code, 1)
    
    def test_accept_wrapper(self):
        """Test accepting new connections."""
        # Mock new connection
        mock_client_socket = MagicMock()
        mock_addr = ('127.0.0.1', 12345)
        self.mock_socket.accept.return_value = (mock_client_socket, mock_addr)
        
        # Call accept_wrapper with accepted_versions
        server.accept_wrapper(self.mock_socket, accepted_versions=[1], protocol="custom")
        
        # Verify connection handling
        self.mock_socket.accept.assert_called_once()
        mock_client_socket.setblocking.assert_called_once_with(False)
        
        # Verify selector registration
        register_call = self.mock_selector.register.call_args
        self.assertEqual(register_call[0][0], mock_client_socket)
        self.assertEqual(register_call[0][1], selectors.EVENT_READ)
        self.assertIsInstance(register_call[1]['data'], Message)
    
    def test_run_server_new_connection(self):
        """Test run_server handling of new connections"""
        # Mock a new connection event
        mock_key = Mock()
        mock_key.data = None
        mock_key.fileobj = self.mock_socket
        
        # Run server until KeyboardInterrupt
        self.mock_selector.select.side_effect = [[(mock_key, selectors.EVENT_READ)], KeyboardInterrupt()]
        
        # Run the server
        server.run_server(accepted_versions=[1], protocol="custom")
        
    def test_run_server_existing_connection(self):
        """Test run_server handling of existing connections"""
        # Mock an existing connection event
        mock_message = Mock()
        mock_key = Mock()
        mock_key.data = mock_message
        mock_key.fileobj = self.mock_socket
        
        # Run server until KeyboardInterrupt
        self.mock_selector.select.side_effect = [[(mock_key, selectors.EVENT_READ)], KeyboardInterrupt()]
        
        # Run the server
        server.run_server(accepted_versions=[1], protocol="custom")
        
        # Verify message processing
        mock_message.process_events.assert_called_once()
        
    def test_run_server_connection_error(self):
        """Test run_server handling of connection errors"""
        # Mock an existing connection with error
        mock_message = Mock()
        mock_message.process_events.side_effect = Exception("Connection error")
        mock_key = Mock()
        mock_key.data = mock_message
        mock_key.fileobj = self.mock_socket
        
        # Run server until KeyboardInterrupt
        self.mock_selector.select.side_effect = [[(mock_key, selectors.EVENT_READ)], KeyboardInterrupt()]
        
        # Run the server
        server.run_server(accepted_versions=[1], protocol="custom")
        
        # Verify error handling
        mock_message.close.assert_called_once()
        
    def test_run_server_general_error(self):
        """Test run_server handling of general errors"""
        # Mock a general error
        self.mock_selector.select.side_effect = Exception("Unknown error")
        
        # Run the server
        server.run_server(accepted_versions=[1], protocol="custom")
        
        # Verify cleanup
        self.mock_selector.close.assert_called_once()
        
        # Verify cleanup was performed
        self.mock_selector.close.assert_called_once()
    
    def test_run_server_existing_connection(self):
        """Test run_server handling of existing connections"""
        # Mock an existing connection
        mock_message = Mock(spec=Message)
        mock_message.addr = ('127.0.0.1', 12345)
        mock_key = Mock()
        mock_key.data = mock_message
        mock_key.fileobj = self.mock_socket
        
        # Set up selector to return the connection event then raise KeyboardInterrupt
        self.mock_selector.select.side_effect = [[(mock_key, selectors.EVENT_READ)], KeyboardInterrupt()]
        
        # Mock get_map for cleanup
        self.mock_selector.get_map.return_value = {1: mock_key}
        
        # Run the server
        server.run_server(accepted_versions=[1], protocol="custom")
        
        # Verify message was processed and cleanup was performed
        mock_message.process_events.assert_called_once_with(selectors.EVENT_READ)
        self.mock_selector.close.assert_called_once()
    
    def test_run_server_error_handling(self):
        """Test run_server error handling"""
        # Mock a message that raises an exception
        mock_message = Mock(spec=Message)
        mock_message.process_events.side_effect = Exception("Test error")
        mock_message.addr = ('127.0.0.1', 12345)
        mock_key = Mock()
        mock_key.data = mock_message
        mock_key.fileobj = self.mock_socket
        
        # Set up selector to return the error event then raise KeyboardInterrupt
        self.mock_selector.select.side_effect = [[(mock_key, selectors.EVENT_READ)], KeyboardInterrupt()]
        
        # Mock get_map for cleanup
        self.mock_selector.get_map.return_value = {1: mock_key}
        
        # Run the server
        server.run_server(accepted_versions=[1], protocol="custom")
        
        # Verify error handling and cleanup
        mock_message.process_events.assert_called_once_with(selectors.EVENT_READ)
        mock_message.close.assert_called_once()
        self.mock_selector.close.assert_called_once()

    def test_main_with_invalid_port(self):
        """Test main script with invalid port number"""
        with patch('json.load') as mock_load:
            mock_load.return_value = {
                'host': 'localhost',
                'port': 80,  # privileged port
                'protocol': 'custom',
                'accepted_versions': [1]
            }
            with patch('builtins.print') as mock_print:
                with self.assertRaises(SystemExit) as cm:
                    server.main()
                self.assertEqual(cm.exception.code, 1)
                mock_print.assert_called_once_with("Error: Please use a port number >= 1024")
                
    def test_main_with_config_error(self):
        """Test main script with config file error"""
        with patch('json.load') as mock_load:
            mock_load.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
            with self.assertRaises(SystemExit) as cm:
                server.main()
            self.assertEqual(cm.exception.code, 1)
            
    def test_main_with_value_error(self):
        """Test main script with invalid port format"""
        with patch('json.load') as mock_load:
            mock_load.return_value = {
                'host': 'localhost',
                'port': 'invalid',  # invalid port format
                'protocol': 'custom',
                'accepted_versions': [1]
            }
            with patch('builtins.print') as mock_print:
                with self.assertRaises(SystemExit) as cm:
                    server.main()
                self.assertEqual(cm.exception.code, 1)
                mock_print.assert_called_once_with("Error: Port must be a number")


if __name__ == '__main__':
    unittest.main()
