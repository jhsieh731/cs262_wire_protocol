import unittest
import selectors
import socket
import json
import struct
from unittest.mock import Mock, patch, MagicMock
from msg_server import Message, MessageDatabase, CustomProtocol

class TestMessage(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.selector = selectors.DefaultSelector()
        self.sock = Mock(spec=socket.socket)
        self.addr = ('127.0.0.1', 65432)
        self.message = Message(
            selector=self.selector,
            sock=self.sock,
            addr=self.addr
        )
        # Mock the database
        self.db_patcher = patch('msg_server.db')
        self.mock_db = self.db_patcher.start()

    def tearDown(self):
        """Clean up after each test method."""
        self.selector.close()
        self.db_patcher.stop()

    def test_init(self):
        """Test Message initialization."""
        self.assertEqual(self.message.addr, self.addr)
        self.assertEqual(self.message._recv_buffer, b"")
        self.assertEqual(self.message._send_buffer, b"")
        self.assertFalse(self.message.response_created)
        self.assertIsNone(self.message._header_len)
        self.assertIsNone(self.message.header)
        self.assertIsNone(self.message.request)
        self.assertEqual(self.message.protocol_mode, "custom")
        self.assertIsInstance(self.message.custom_protocol, CustomProtocol)

    def test_json_encode_decode(self):
        """Test JSON encoding and decoding."""
        test_data = {"key": "value", "number": 42}
        encoded = self.message._json_encode(test_data, "utf-8")
        decoded = self.message._json_decode(encoded, "utf-8")
        self.assertEqual(test_data, decoded)

    def test_create_message_json_mode(self):
        """Test message creation in JSON mode."""
        self.message.protocol_mode = "json"
        content = b'{"test": "data"}'
        action = "test_action"
        message = self.message._create_message(
            content_bytes=content,
            action=action,
            content_length=len(content)
        )
        # First 2 bytes are header length
        header_len = struct.unpack(">H", message[:2])[0]
        self.assertTrue(len(message) > header_len + 2)

    def test_create_message_custom_mode(self):
        """Test message creation in custom protocol mode."""
        content = b'{"test": "data"}'
        action = "test_action"
        message = self.message._create_message(
            content_bytes=content,
            action=action,
            content_length=len(content)
        )
        # First 2 bytes are header length
        header_len = struct.unpack(">H", message[:2])[0]
        self.assertTrue(len(message) > header_len + 2)

    def test_create_response_login_register(self):
        """Test creating response for login/register action."""
        self.message.protocol_mode = "json"  # Switch to JSON mode for testing
        self.message.header = {"action": "login_register"}
        self.message.request = self.message._json_encode({
            "username": "testuser",
            "password": "testpass"
        }, "utf-8")
        
        # Mock database response
        self.mock_db.login_or_create_account.return_value = [{
            "userid": "test-uuid"
        }]
        
        response = self.message._create_response_content()
        self.assertIn("content_bytes", response)
        self.assertEqual(response["action"], "response")
        
        # Decode response content
        content = self.message._json_decode(response["content_bytes"], "utf-8")
        self.assertEqual(content["uuid"], "test-uuid")
        self.assertEqual(content["response_type"], "login_register")

    def test_create_response_load_page_data(self):
        """Test creating response for load_page_data action."""
        self.message.protocol_mode = "json"  # Switch to JSON mode for testing
        self.message.header = {"action": "load_page_data"}
        self.message.request = self.message._json_encode({
            "uuid": "test-uuid"
        }, "utf-8")
        
        # Mock database response
        self.mock_db.load_page_data.return_value = (
            ["message1", "message2"],  # messages
            5,                         # num_pending
            ["account1", "account2"],  # accounts
            10                         # total_count
        )
        
        response = self.message._create_response_content()
        content = self.message._json_decode(response["content_bytes"], "utf-8")
        
        self.assertEqual(content["messages"], ["message1", "message2"])
        self.assertEqual(content["num_pending"], 5)
        self.assertEqual(content["accounts"], ["account1", "account2"])
        self.assertEqual(content["total_count"], 10)
        self.assertEqual(content["response_type"], "load_page_data")

    def test_create_response_send_message(self):
        """Test creating response for send_message action."""
        self.message.protocol_mode = "json"  # Switch to JSON mode for testing
        self.message.header = {"action": "send_message"}
        self.message.request = self.message._json_encode({
            "uuid": "sender-uuid",
            "recipient_username": "recipient",
            "message": "Hello!",
            "timestamp": "2025-02-10T12:00:00"
        }, "utf-8")
        
        # Mock database responses
        self.mock_db.get_user_uuid.return_value = (True, "", "recipient-uuid")
        self.mock_db.get_associated_socket.return_value = "recipient-socket"
        self.mock_db.get_user_username.return_value = "sender"
        self.mock_db.store_message.return_value = (True, "")
        
        # Mock selector for recipient lookup
        mock_recipient = MagicMock()
        mock_recipient.data = Message(self.selector, Mock(), "recipient-socket")
        self.selector._fd_to_key = {1: mock_recipient}
        
        response = self.message._create_response_content()
        content = self.message._json_decode(response["content_bytes"], "utf-8")
        
        self.assertTrue(content["success"])
        self.assertEqual(content["response_type"], "send_message")
        self.assertTrue(content["delivered"])

    def test_process_events(self):
        """Test processing of read and write events."""
        # Test read event
        with patch.object(self.message, 'read') as mock_read:
            self.message.process_events(selectors.EVENT_READ)
            mock_read.assert_called_once()

        # Test write event
        with patch.object(self.message, 'write') as mock_write:
            self.message.process_events(selectors.EVENT_WRITE)
            mock_write.assert_called_once()

    @patch('selectors.DefaultSelector.modify')
    def test_read_write_flow(self, mock_modify):
        """Test the complete read-write flow."""
        self.message.protocol_mode = "json"  # Switch to JSON mode for testing
        
        # Setup test data
        test_request = {
            "username": "testuser",
            "password": "testpass"
        }
        encoded_request = self.message._json_encode(test_request, "utf-8")
        header = {
            "content-length": len(encoded_request),
            "action": "login_register"
        }
        encoded_header = self.message._json_encode(header, "utf-8")
        header_len = struct.pack(">H", len(encoded_header))
        
        # Mock socket receive
        self.sock.recv.return_value = header_len + encoded_header + encoded_request
        
        # Mock database response
        self.mock_db.login_or_create_account.return_value = [{
            "userid": "test-uuid"
        }]
        
        # Mock socket send
        self.sock.send.return_value = 0  # Simulate no bytes sent yet
        
        # Process the request
        with patch.object(self.message, '_set_selector_events_mask') as mock_set_mask:
            # Process read
            self.message.read()
            self.assertEqual(self.message.header["action"], "login_register")
            self.assertEqual(self.message.request, encoded_request)
            
            # Create response
            self.message.create_response()
            self.assertTrue(self.message.response_created)
            
            # Store the response buffer
            response_buffer = self.message._send_buffer
            
            # Write response
            self.message.write()
            self.assertEqual(self.message._send_buffer, response_buffer)

    def test_close(self):
        """Test connection closing."""
        self.message.close()
        self.sock.close.assert_called_once()
        self.assertIsNone(self.message.sock)

    def test_process_header_missing_fields(self):
        """Test processing header with missing required fields."""
        self.message.protocol_mode = "json"  # Switch to JSON mode for testing
        # Create a header without required fields
        header_data = {"version": 1}
        encoded_header = json.dumps(header_data).encode('utf-8')
        self.message._header_len = len(encoded_header)
        self.message._recv_buffer = encoded_header
        self.message.process_header()
        self.assertEqual(self.message.header["action"], "error")

    def test_process_protoheader_complete(self):
        """Test processing protoheader with complete data."""
        # Create a header length of 50 bytes (\x00\x32 in big-endian format)
        header_len_bytes = struct.pack(">H", 50)
        self.message._recv_buffer = header_len_bytes + b"remaining_data"
        
        self.message.process_protoheader()
        
        # Check that header length was correctly unpacked
        self.assertEqual(self.message._header_len, 50)
        # Check that header length bytes were removed from buffer
        self.assertEqual(self.message._recv_buffer, b"remaining_data")
    
    def test_process_protoheader_incomplete(self):
        """Test processing protoheader with incomplete data."""
        # Only provide 1 byte, not enough for header length
        self.message._recv_buffer = b"\x00"
        
        self.message.process_protoheader()
        
        # Check that nothing was processed
        self.assertIsNone(self.message._header_len)
        self.assertEqual(self.message._recv_buffer, b"\x00")
    
    def test_process_header_json_complete(self):
        """Test processing header in JSON mode with complete data."""
        self.message.protocol_mode = "json"
        
        # Create a valid header with required fields
        header = {
            "content-length": 100,
            "action": "login_register"
        }
        header_bytes = json.dumps(header).encode('utf-8')
        self.message._header_len = len(header_bytes)
        self.message._recv_buffer = header_bytes + b"remaining_data"
        
        self.message.process_header()
        
        # Check that header was correctly parsed
        self.assertEqual(self.message.header["content-length"], 100)
        self.assertEqual(self.message.header["action"], "login_register")
        # Check that remaining data is still in buffer
        self.assertEqual(self.message._recv_buffer, b"remaining_data")
    
    def test_process_header_custom_complete(self):
        """Test processing header in custom mode with complete data."""
        self.message.protocol_mode = "custom"
        header_data = b"header_data"
        self.message._header_len = len(header_data)
        
        # Setup mock custom protocol
        mock_header = {"content-length": 100, "action": "login_register"}
        self.message.custom_protocol = Mock()
        self.message.custom_protocol.deserialize = Mock(return_value=mock_header)
        
        self.message._recv_buffer = header_data + b"remaining_data"
        
        self.message.process_header()
        
        # Check that custom protocol deserialize was called
        self.message.custom_protocol.deserialize.assert_called_once_with(header_data)
        # Check that header was correctly set
        self.assertEqual(self.message.header, mock_header)
        # Check that remaining data is still in buffer
        self.assertEqual(self.message._recv_buffer, b"remaining_data")
    
    def test_process_header_invalid_mode(self):
        """Test processing header with invalid protocol mode."""
        self.message.protocol_mode = "invalid"
        self.message._header_len = 10
        self.message._recv_buffer = b"header_data"
        
        # Process header with invalid mode should raise ValueError
        with self.assertRaises(ValueError) as cm:
            self.message.process_header()
        
        # Check the error message
        self.assertEqual(str(cm.exception), "Invalid protocol mode 'invalid'")
        # Buffer should remain unchanged
        self.assertEqual(self.message._recv_buffer, b"header_data")
    
    def test_process_request_complete(self):
        """Test processing request with complete data."""
        # Setup header with content length
        self.message.header = {"content-length": 10, "action": "login_register"}
        # Setup request data
        request_data = b"0123456789remaining_data"
        self.message._recv_buffer = request_data
        
        with patch.object(self.message, '_set_selector_events_mask') as mock_set_mask:
            self.message.process_request()
            
            # Check that correct amount of data was extracted
            self.assertEqual(self.message.request, b"0123456789")
            # Check that remaining data is still in buffer
            self.assertEqual(self.message._recv_buffer, b"remaining_data")
            # Check that selector was set to write mode
            mock_set_mask.assert_called_once_with("w")
    
    def test_process_request_incomplete(self):
        """Test processing request with incomplete data."""
        # Setup header with content length
        self.message.header = {"content-length": 20, "action": "login_register"}
        # Setup request data (less than content-length)
        request_data = b"0123456789"
        self.message._recv_buffer = request_data
        
        with patch.object(self.message, '_set_selector_events_mask') as mock_set_mask:
            self.message.process_request()
            
            # Check that nothing was processed
            self.assertIsNone(self.message.request)
            # Check that buffer wasn't modified
            self.assertEqual(self.message._recv_buffer, request_data)
            # Check that selector wasn't modified
            mock_set_mask.assert_not_called()

    def test_create_response_error(self):
        """Test creating response for error action."""
        self.message.protocol_mode = "json"  # Switch to JSON mode for testing
        self.message.header = {"action": "error"}
        self.message.request = self.message._json_encode({}, "utf-8")  # Empty request
        response = self.message._create_response_content()
        content = self.message._json_decode(response["content_bytes"], "utf-8")
        self.assertEqual(content["response_type"], "error")
        self.assertIn("error", content)

if __name__ == '__main__':
    unittest.main()
