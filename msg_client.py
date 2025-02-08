import io
import json
import selectors
import struct
import sys

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
        self._jsonheader_len = None
        self.jsonheader = None
        self.response = None

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
                    self._jsonheader_len = None
                    self.jsonheader = None
                    self.request = None
                    self.response_created = False

    # TODO: add fns for custom protocol
    def _json_encode(self, obj, encoding):
        return json.dumps(obj, ensure_ascii=False).encode(encoding)

    def _json_decode(self, json_bytes, encoding):
        tiow = io.TextIOWrapper(
            io.BytesIO(json_bytes), encoding=encoding, newline=""
        )
        obj = json.load(tiow)
        tiow.close()
        return obj

    def _create_message(
        self, *, content_bytes, action, content_length
    ):
        # TODO: rethink header
        jsonheader = {
            "version": 1,
            "content-length": content_length,
            "action": action,
        }
        jsonheader_bytes = self._json_encode(jsonheader, "utf-8")
        message_hdr = struct.pack(">H", len(jsonheader_bytes))
        message = message_hdr + jsonheader_bytes + content_bytes
        print(f"Created message: {message!r}")
        return message

    def _process_response_json_content(self):
        content = self.response
        result = content.get("result")
        print(f"Got result: {result}")

    def process_events(self, mask):
        if mask & selectors.EVENT_READ:
            print("read")
            self.read()
        if mask & selectors.EVENT_WRITE:
            print("write")
            self.write()

    def read(self):
        self._read()
        print(f"Read data from {self.addr}: {self._recv_buffer!r}")
        print(self._jsonheader_len is None)

        if self._jsonheader_len is None:
            self.process_protoheader()
            print(f"Read protoheader, new data: {self._recv_buffer!r}")

        if self._jsonheader_len is not None:
            if self.jsonheader is None:
                self.process_jsonheader()
                print(f"Read jsonheader, new data: {self._recv_buffer!r}")

        if self.jsonheader:
            if self.response is None:
                self.process_response()

    def write(self):
        if not self._request_queued:
            self.queue_request()

        self._write()

        if self._request_queued:
            if not self._send_buffer:
                # Set selector to listen for read events, we're done writing.
                self._set_selector_events_mask("r")

    def close(self):
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

    # TODO: change/add custom protocol
    def queue_request(self):
        print("queue_request")
        # Reset state before queuing a new request
        self.reset_state()
        
        content = self._json_encode(self.request["content"], "utf-8")
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
        print("process_protoheader")
        hdrlen = 2 # fixed length
        if len(self._recv_buffer) >= hdrlen:
            print("len of buffer: ", len(self._recv_buffer))
            self._jsonheader_len = struct.unpack(
                ">H", self._recv_buffer[:hdrlen]
            )[0]
            print(f"JSON header length: {self._jsonheader_len}")
            self._recv_buffer = self._recv_buffer[hdrlen:]

    def process_jsonheader(self):
        hdrlen = self._jsonheader_len
        if len(self._recv_buffer) >= hdrlen:
            self.jsonheader = self._json_decode(
                self._recv_buffer[:hdrlen], "utf-8"
            )
            print(f"JSON header: {self.jsonheader!r}")
            self._recv_buffer = self._recv_buffer[hdrlen:]
            for reqhdr in (
                "content-length",
                "action",
            ):
                if reqhdr not in self.jsonheader:
                    raise ValueError(f"Missing required header '{reqhdr}'.")

    def reset_state(self):
        """Reset the message state to handle new requests/responses"""
        print("Resetting message state")
        self._jsonheader_len = None
        self.jsonheader = None
        self.response = None
        self._recv_buffer = b""

    def process_response(self):
        content_len = self.jsonheader["content-length"]
        print(f"len of buffer: {len(self._recv_buffer)}; Content length: {content_len}")
        if not len(self._recv_buffer) >= content_len:
            return
        data = self._recv_buffer[:content_len]
        print(f"Response content: {data!r}")
        self._recv_buffer = self._recv_buffer[content_len:]
        
        try:
            decoded_response = self._json_decode(data, "utf-8")
            print(f"Decoded response: {decoded_response}")
            self.response = decoded_response
            self.gui.handle_server_response(decoded_response)
            # Reset state after successfully processing the response
            self.reset_state()
        except Exception as e:
            print(f"Error decoding response: {e}")
            print(f"Raw data: {data}")

        