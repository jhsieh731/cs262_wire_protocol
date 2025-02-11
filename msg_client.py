import io
import json
import selectors
import struct
from custom_protocol_2 import CustomProtocol


# TODO: link this with client/server...
class Message:
    def __init__(self, selector, sock, addr, gui, request):
        self.selector = selector
        self.sock = sock
        self.addr = addr
        self.request = request
        self.gui = gui
        self._recv_buffer = b""
        self._send_buffer = b""
        self._request_queued = False
        self._header_len = None
        self.header = None
        self.response = None
        self.protocol_mode = "custom" # "json" or "custom"
        self.custom_protocol = CustomProtocol()

        # validate protocol_mode: if unknown protocol, do not assume
        if self.protocol_mode not in ["json", "custom"]:
            return ValueError(f"Invalid protocol mode {self.protocol_mode!r}.")

    def _set_selector_events_mask(self, mode):
        """Set selector to listen for events: mode is 'r', 'w', or 'rw'."""
        if mode == "r":
            events = selectors.EVENT_READ
        elif mode == "w":
            events = selectors.EVENT_WRITE
        elif mode == "rw":
            events = selectors.EVENT_READ | selectors.EVENT_WRITE
        else:
            raise ValueError(f"Invalid events mask mode {mode!r}.")
        self.selector.modify(self.sock, events, data=self)

    def _read(self):
        """Read from the socket."""
        try:
            # Should be ready to read
            data = self.sock.recv(4096)
        except BlockingIOError:
            # Resource temporarily unavailable (errno EWOULDBLOCK)
            pass
        else:
            if data:
                self._recv_buffer += data
            else:
                raise RuntimeError("Peer closed.")

    def _write(self):
        """Write to the socket."""
        print("_write")
        if self._send_buffer:
            print(f"Sending {self._send_buffer!r} to {self.addr}")
            try:
                # Should be ready to write
                sent = self.sock.send(self._send_buffer)
            except BlockingIOError:
                # Resource temporarily unavailable (errno EWOULDBLOCK)
                pass
            else:
                self._send_buffer = self._send_buffer[sent:]
                if sent and not self._send_buffer:
                    self._header_len = None
                    self.header = None
                    self.request = None
                    self.response_created = False

    def _json_encode(self, obj, encoding):
        """Encode a Python object as JSON and encode to bytes."""
        return json.dumps(obj, ensure_ascii=False).encode(encoding)

    def _json_decode(self, json_bytes, encoding):
        """Decode JSON bytes to a Python object."""
        tiow = io.TextIOWrapper(
            io.BytesIO(json_bytes), encoding=encoding, newline=""
        )
        obj = json.load(tiow)
        tiow.close()
        return obj


    def _create_message(
        self, *, content_bytes, action, content_length
    ):
        """Create a message with header and content."""
        header = {
            "content-length": content_length,
            "action": action,
        }
        # Serialize the header
        if self.protocol_mode == "json":
            header_bytes = self._json_encode(header, "utf-8")
        elif self.protocol_mode == "custom":
            checksum = self.custom_protocol.compute_checksum(content_bytes)
            header["checksum"] = checksum
            header_bytes = self.custom_protocol.serialize(header)

        # Pack version (1 byte) and header length (2 bytes)
        message_hdr = struct.pack(">BH", 1, len(header_bytes))
        message = message_hdr + header_bytes + content_bytes
        print(f"Created message: {message!r}")
        return message

    def process_events(self, mask):
        """Process selector events (step 1 of processing)"""
        if mask & selectors.EVENT_READ:
            print("read")
            self.read()
        if mask & selectors.EVENT_WRITE:
            print("write")
            self.write()

    def read(self):
        """Read response pipeline"""
        self._read()
        print(f"Read data from {self.addr}: {self._recv_buffer!r}")

        if self._header_len is None:
            self.process_protoheader()
            print(f"Read protoheader, new data: {self._recv_buffer!r}")

        if self._header_len is not None:
            if self.header is None:
                self.process_header()
                print(f"Read header, new data: {self._recv_buffer!r}")

        if self.header:
            if self.response is None:
                self.process_response()

    def write(self):
        """Write request pipeline"""
        if not self._request_queued:
            self.queue_request()

        self._write()

        if self._request_queued:
            if not self._send_buffer:
                # Set selector to listen for read events, we're done writing.
                self._set_selector_events_mask("r")

    def close(self):
        """Close the socket connection."""
        print(f"Closing connection to {self.addr}")
        try:
            self.selector.unregister(self.sock)
        except Exception as e:
            print(
                f"Error: selector.unregister() exception for "
                f"{self.addr}: {e!r}"
            )

        try:
            self.sock.close()
        except OSError as e:
            print(f"Error: socket.close() exception for {self.addr}: {e!r}")
        finally:
            # Delete reference to socket object for garbage collection
            self.sock = None

    def queue_request(self):
        """Prepare a request to be sent to the server."""
        print("queue_request")
        # Reset state before queuing a new request
        self.reset_state()
        
        # Serialize the content
        if self.protocol_mode == "json":
            content = self._json_encode(self.request["content"], "utf-8")
        elif self.protocol_mode == "custom":
            print(166, self.request["content"])
            content = self.custom_protocol.serialize(self.request["content"])
        
        # Create the message
        action = self.request["action"]
        req = {
            "content_bytes": content,
            "action": action,
            "content_length": len(content),
        }
        print(f"Request: {req!r}")
        message = self._create_message(**req)
        self._send_buffer += message
        self._request_queued = True

    def process_protoheader(self):
        """Process the protocol header (read pipeline step 1)."""
        print("process_protoheader")
        version_len = 1  # 1 byte for version
        hdrlen = 2  # fixed length for header length
        
        # First check version
        if len(self._recv_buffer) >= version_len:
            version = struct.unpack(">B", self._recv_buffer[:version_len])[0]
            if version != 1:
                raise ValueError(f"Cannot handle protocol version {version}")
            self._recv_buffer = self._recv_buffer[version_len:]
        else:
            return
            
        # Then process header length
        if len(self._recv_buffer) >= hdrlen:
            print("len of buffer: ", len(self._recv_buffer))
            self._header_len = struct.unpack(
                ">H", self._recv_buffer[:hdrlen]
            )[0]
            print(f"header length: {self._header_len}")
            self._recv_buffer = self._recv_buffer[hdrlen:]

    def process_header(self):
        """Process the header (read pipeline step 2)."""
        hdrlen = self._header_len
        # deserialize header
        if len(self._recv_buffer) >= hdrlen:
            if self.protocol_mode == "json":
                self.header = self._json_decode(
                    self._recv_buffer[:hdrlen], "utf-8"
                )
            elif self.protocol_mode == "custom":
                self.header = self.custom_protocol.deserialize(
                    self._recv_buffer[:hdrlen], "header"
                )
            
            # verify header
            print(f"JSON header: {self.header!r}")
            self._recv_buffer = self._recv_buffer[hdrlen:]
            for reqhdr in (
                "content-length",
                "action",
            ):
                if reqhdr not in self.header:
                    self.header["action"] = "error"

    def reset_state(self):
        """Reset the message state to handle new requests/responses"""
        print("Resetting message state")
        self._header_len = None
        self.header = None
        self.response = None
        self._recv_buffer = b""

    def process_response(self):
        """Process the response (read pipeline step 3)."""
        content_len = self.header["content-length"]
        print(f"len of buffer: {len(self._recv_buffer)}; Content length: {content_len}")
        # Check if the full response is in the buffer
        if not len(self._recv_buffer) >= content_len:
            return
        data = self._recv_buffer[:content_len]
        print(f"Response content: {data!r}")
        self._recv_buffer = self._recv_buffer[content_len:]
        action = self.header["action"]
        
        try:
            # Decode the response
            if self.protocol_mode == "json":
                decoded_response = self._json_decode(data, "utf-8")
            elif self.protocol_mode == "custom":
                decoded_response = self.custom_protocol.deserialize(data, action)
                # verify checksum
                computed_checksum = self.custom_protocol.compute_checksum(data)
                if computed_checksum != self.header["checksum"]:
                    action = "error"
            print(f"Decoded response: {decoded_response}")
            self.response = decoded_response
            # Server response in gui
            self.gui.handle_server_response(decoded_response, action)
            # Done reading, reset Message class for next message
            self.reset_state()
        except Exception as e:
            print(f"Error decoding response: {e}")
            print(f"Raw data: {data}")

        