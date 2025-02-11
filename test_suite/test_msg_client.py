import unittest
import selectors
import socket
import json
import struct
from unittest.mock import Mock, patch
from msg_client import Message
from custom_protocol import CustomProtocol

class TestMessage(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.selector = selectors.DefaultSelector()
        self.sock = Mock(spec=socket.socket)
        self.addr = ('127.0.0.1', 65432)
        self.gui = Mock()
        self.request = {
            "action": "login",
            "content": {"username": "testuser", "password": "testpass"}
        }
        self.message = Message(
            selector=self.selector,
            sock=self.sock,
            addr=self.addr,
            gui=self.gui,
            request=self.request
        )

    def tearDown(self):
        """Clean up after each test method."""
        self.selector.close()

    def test_init(self):
        """Test Message initialization."""
        self.assertEqual(self.message.addr, self.addr)
        self.assertEqual(self.message.request, self.request)
        self.assertEqual(self.message._recv_buffer, b"")
        self.assertEqual(self.message._send_buffer, b"")
        self.assertFalse(self.message._request_queued)
        self.assertIsNone(self.message._header_len)
        self.assertIsNone(self.message.header)
        self.assertIsNone(self.message.response)
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

    def test_queue_request(self):
        """Test queuing a request."""
        self.message.queue_request()
        self.assertTrue(self.message._request_queued)
        self.assertTrue(len(self.message._send_buffer) > 0)

    def test_process_protoheader(self):
        """Test processing protocol header."""
        # Create a mock header length of 10 (encoded as 2 bytes)
        self.message._recv_buffer = struct.pack(">H", 10) + b"extra_data"
        self.message.process_protoheader()
        self.assertEqual(self.message._header_len, 10)
        self.assertEqual(self.message._recv_buffer, b"extra_data")

    def test_reset_state(self):
        """Test resetting message state."""
        self.message._header_len = 10
        self.message.header = {"some": "header"}
        self.message.response = {"some": "response"}
        self.message._recv_buffer = b"some_data"

        self.message.reset_state()

        self.assertIsNone(self.message._header_len)
        self.assertIsNone(self.message.header)
        self.assertIsNone(self.message.response)
        self.assertEqual(self.message._recv_buffer, b"")

    def test_close(self):
        """Test connection closing."""
        self.message.close()
        self.sock.close.assert_called_once()
        self.assertIsNone(self.message.sock)

    @patch('selectors.DefaultSelector.modify')
    def test_set_selector_events_mask(self, mock_modify):
        """Test setting selector events mask."""
        self.message._set_selector_events_mask("r")
        mock_modify.assert_called_once_with(
            self.sock, 
            selectors.EVENT_READ, 
            data=self.message
        )

        with self.assertRaises(ValueError):
            self.message._set_selector_events_mask("invalid")

    def test_process_response_json_mode(self):
        """Test processing response in JSON mode."""
        self.message.protocol_mode = "json"
        test_response = {"status": "success"}
        encoded_response = json.dumps(test_response).encode("utf-8")
        
        self.message.header = {
            "content-length": len(encoded_response),
            "action": "response"
        }
        self.message._recv_buffer = encoded_response

        self.message.process_response()
        
        # Verify GUI was called with decoded response
        self.gui.handle_server_response.assert_called_once_with(test_response)

    def test_process_response_custom_mode(self):
        """Test processing response in custom protocol mode."""
        test_response = {"status": "success"}
        encoded_response = self.message.custom_protocol.serialize(test_response)
        checksum = self.message.custom_protocol.compute_checksum(encoded_response)
        
        self.message.header = {
            "content-length": len(encoded_response),
            "action": "response",
            "checksum": checksum
        }
        self.message._recv_buffer = encoded_response

        self.message.process_response()
        
        # Verify GUI was called with decoded response
        self.gui.handle_server_response.assert_called_once()

    def test_read(self):
        """Test the _read method for successful and blocking cases."""
        # Test successful read
        self.sock.recv.return_value = b"test data"
        self.message._read()
        self.assertEqual(self.message._recv_buffer, b"test data")
        self.sock.recv.assert_called_once_with(4096)

        # Test BlockingIOError
        self.sock.recv.reset_mock()
        self.sock.recv.side_effect = BlockingIOError()
        self.message._read()  # Should not raise exception
        self.sock.recv.assert_called_once_with(4096)

        # Test peer closed connection
        self.sock.recv.reset_mock()
        self.sock.recv.side_effect = None  # Reset side_effect
        self.sock.recv.return_value = b""
        with self.assertRaises(RuntimeError):
            self.message._read()

    def test_write(self):
        """Test the _write method for various scenarios."""
        # Test successful write
        self.message._send_buffer = b"test data"
        self.sock.send.return_value = 9  # Length of "test data"
        self.message._write()
        self.assertEqual(self.message._send_buffer, b"")
        self.sock.send.assert_called_once_with(b"test data")

        # Test partial write
        self.message._send_buffer = b"test data"
        self.sock.send.reset_mock()
        self.sock.send.return_value = 4  # Only write "test"
        self.message._write()
        self.assertEqual(self.message._send_buffer, b" data")

        # Test BlockingIOError
        self.message._send_buffer = b"test data"
        self.sock.send.reset_mock()
        self.sock.send.side_effect = BlockingIOError()
        self.message._write()  # Should not raise exception
        self.assertEqual(self.message._send_buffer, b"test data")

    @patch('selectors.DefaultSelector.modify')
    def test_process_events(self, mock_modify):
        """Test processing of read and write events."""
        # Test read event
        with patch.object(self.message, 'read') as mock_read:
            self.message.process_events(selectors.EVENT_READ)
            mock_read.assert_called_once()

        # Test write event
        with patch.object(self.message, 'write') as mock_write:
            self.message.process_events(selectors.EVENT_WRITE)
            mock_write.assert_called_once()

        # Test both events
        with patch.object(self.message, 'read') as mock_read, \
             patch.object(self.message, 'write') as mock_write:
            self.message.process_events(selectors.EVENT_READ | selectors.EVENT_WRITE)
            mock_read.assert_called_once()
            mock_write.assert_called_once()

    def test_read_method(self):
        """Test the read method's full workflow."""
        # Mock _read to simulate receiving data
        with patch.object(self.message, '_read') as mock_read, \
             patch.object(self.message, 'process_protoheader') as mock_process_protoheader, \
             patch.object(self.message, 'process_header') as mock_process_header, \
             patch.object(self.message, 'process_response') as mock_process_response:
            
            self.message.read()
            mock_read.assert_called_once()
            mock_process_protoheader.assert_called_once()

            # Simulate header length being set
            self.message._header_len = 10
            self.message.read()
            mock_process_header.assert_called_once()

            # Simulate header being set
            self.message.header = {"content-length": 20}
            self.message.read()
            mock_process_response.assert_called_once()

    def test_write_method(self):
        """Test the write method's full workflow."""
        # Test initial write when request is not queued
        with patch.object(self.message, 'queue_request') as mock_queue_request, \
             patch.object(self.message, '_write') as mock_write, \
             patch.object(self.message, '_set_selector_events_mask') as mock_set_mask:
            
            self.message.write()
            mock_queue_request.assert_called_once()
            mock_write.assert_called_once()

            # Simulate request being queued but buffer not empty
            self.message._request_queued = True
            self.message._send_buffer = b"remaining data"
            self.message.write()
            self.assertEqual(mock_write.call_count, 2)
            mock_set_mask.assert_not_called()

            # Simulate request being queued and buffer empty
            self.message._send_buffer = b""
            self.message.write()
            mock_set_mask.assert_called_once_with("r")

    def test_process_header(self):
        """Test processing headers in both JSON and custom protocol modes."""
        # Test JSON protocol mode
        self.message.protocol_mode = "json"
        test_header = {"content-length": 100, "action": "test"}
        encoded_header = json.dumps(test_header).encode("utf-8")
        self.message._recv_buffer = encoded_header
        self.message._header_len = len(encoded_header)

        self.message.process_header()
        self.assertEqual(self.message.header, test_header)
        self.assertEqual(self.message._recv_buffer, b"")

        # Test custom protocol mode
        self.message.protocol_mode = "custom"
        test_header = {"content-length": 100, "action": "test", "checksum": 123}
        encoded_header = self.message.custom_protocol.serialize(test_header)
        self.message._recv_buffer = encoded_header
        self.message._header_len = len(encoded_header)

        self.message.process_header()
        self.assertEqual(self.message.header["content-length"], test_header["content-length"])
        self.assertEqual(self.message.header["action"], test_header["action"])

        # Test missing required header fields
        self.message._recv_buffer = json.dumps({"version": 1}).encode("utf-8")
        self.message._header_len = len(self.message._recv_buffer)
        self.message.process_header()
        self.assertEqual(self.message.header["action"], "error")

        # Test invalid protocol mode
        self.message.protocol_mode = "invalid"
        self.message._recv_buffer = encoded_header
        with self.assertRaises(ValueError):
            self.message.process_header()

if __name__ == '__main__':
    unittest.main()
