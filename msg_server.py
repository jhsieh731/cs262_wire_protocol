import io
import json
import selectors
import struct
import sys
from database import MessageDatabase

db = MessageDatabase()

request_search = {
    "morpheus": "Follow the white rabbit. \U0001f430",
    "ring": "In the caves beneath the Misty Mountains. \U0001f48d",
    "\U0001f436": "\U0001f43e Playing ball! \U0001f3d0",
}

class Message:
    def __init__(self, selector, sock, addr):
        self.selector = selector
        self.sock = sock
        self.addr = addr
        self._recv_buffer = b""
        self._send_buffer = b""
        self._jsonheader_len = None
        self.jsonheader = None
        self.request = None
        self.response_created = False

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
                # After sending, reset state and switch back to read mode
                if sent and not self._send_buffer:
                    self._jsonheader_len = None
                    self.jsonheader = None
                    self.request = None
                    self.response_created = False
                    self._set_selector_events_mask("r")

    def _json_encode(self, obj, encoding):
        return json.dumps(obj, ensure_ascii=False).encode(encoding)

    def _json_decode(self, json_bytes, encoding):
        tiow = io.TextIOWrapper(
            io.BytesIO(json_bytes), encoding=encoding, newline=""
        )
        obj = json.load(tiow)
        tiow.close()
        return obj
    
    # TODO: implement custom encode/decodes according to our protocol

    def _create_message(
        self, *, content_bytes, action, content_length
    ):
        jsonheader = {
            "content-length": content_length,
            "action": action,
        }
        jsonheader_bytes = self._json_encode(jsonheader, "utf-8")
        message_hdr = struct.pack(">H", len(jsonheader_bytes))
        message = message_hdr + jsonheader_bytes + content_bytes
        return message

    def _create_response_json_content(self):
        # First decode the request content
        request_content = self._json_decode(self.request, "utf-8")
        response_content = {}
        print("action: ", self.jsonheader["action"])
        # TODO: switch statements here
        # Create response content and encode it
        if self.jsonheader["action"] == "login_register":
            # try to login
            accounts = db.login_or_create_account(request_content["username"], request_content["password"], str(self.addr))
            print("account: ", accounts)
            if (len(accounts) != 1):
                response_content = {
                    "response": "Invalid username or password",
                    "response_type": "error"
                }
                response_content["response"] = "Invalid username or password"
            else:
                response_content = {
                    "uuid": accounts[0]["userid"],
                    "response_type": "login_register"
                }
        elif self.jsonheader["action"] == "search_accounts":
            print("searching accounts")
            # Decode the request content
            request_content = self._json_decode(self.request, "utf-8")
            print("Request content:", request_content)

            search_term = request_content.get("search_term", "")
            print("search term: ", search_term)
            
            # Search for accounts
            accounts = db.search_accounts(search_term)
            print(f"Found accounts: {accounts}")
            
            response_content = {
                "accounts": accounts,
                "response_type": "search_accounts"
            }
        elif self.jsonheader["action"] == "show_messages":
            pass
        elif self.jsonheader["action"] == "send_message":
            # Decode the request content
            request_content = self._json_decode(self.request, "utf-8")
            print("Send message request:", request_content)
            
            # Extract message details
            sender_uuid = request_content.get("sender_uuid")
            recipient_username = request_content.get("recipient_username")
            message_text = request_content.get("message")

            print("message details: ", sender_uuid, recipient_username, message_text)
            
            if not all([sender_uuid, recipient_username, message_text]):
                response_content = {
                    "success": False,
                    "error": "Missing required fields",
                    "response_type": "send_message"
                }
            else:
                # Get recipient's UUID
                success, error, recipient_uuid = db.get_user_uuid(recipient_username)
                if not success:
                    response_content = {
                        "success": False,
                        "error": error,
                        "response_type": "send_message"
                    }
                else:
                    # Store the message
                    success, error = db.store_message(sender_uuid, recipient_uuid, message_text)
                    response_content = {
                        "success": success,
                        "error": error,
                        "response_type": "send_message"
                    }
        elif self.jsonheader["action"] == "mark_read":
            pass
        elif self.jsonheader["action"] == "delete_messages":
            pass
        elif self.jsonheader["action"] == "delete_account":
            pass
        else:
            response_content = {
                "content": request_content,
                "response_type": "echo"
            }
            
        content_bytes = self._json_encode(response_content, "utf-8")
        response = {
            "content_bytes": content_bytes,
            "action": "response",
            "content_length": len(content_bytes)
        }
        return response

    def process_events(self, mask):
        if mask & selectors.EVENT_READ:
            print("read")
            self.read()
        if mask & selectors.EVENT_WRITE:
            print("write")
            self.write()

    def read(self):
        self._read()

        if self._jsonheader_len is None:
            self.process_protoheader()

        if self._jsonheader_len is not None:
            if self.jsonheader is None:
                self.process_jsonheader()

        if self.jsonheader:
            if self.request is None:
                self.process_request()

    def write(self):
        if self.request:
            if not self.response_created:
                self.create_response()

        self._write()

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


    # TODO: rethink these two based on how we form our custom messages
    def process_protoheader(self):
        hdrlen = 2
        if len(self._recv_buffer) >= hdrlen:
            self._jsonheader_len = struct.unpack(
                ">H", self._recv_buffer[:hdrlen]
            )[0]
            self._recv_buffer = self._recv_buffer[hdrlen:]

    def process_jsonheader(self):
        hdrlen = self._jsonheader_len
        if len(self._recv_buffer) >= hdrlen:
            self.jsonheader = self._json_decode(
                self._recv_buffer[:hdrlen], "utf-8"
            )
            self._recv_buffer = self._recv_buffer[hdrlen:]
            for reqhdr in (
                "content-length",
                "action",
            ):
                if reqhdr not in self.jsonheader:
                    raise ValueError(f"Missing required header '{reqhdr}'.")

    def process_request(self):
        content_len = self.jsonheader["content-length"]
        if not len(self._recv_buffer) >= content_len:
            return
        data = self._recv_buffer[:content_len]
        self._recv_buffer = self._recv_buffer[content_len:]
        # The data is already JSON encoded, store it as is
        self.request = data
        print(f"Stored request data: {self.request!r}")
        # Set selector to listen for write events, we're ready to respond
        self._set_selector_events_mask("w")

    def create_response(self):
        response = self._create_response_json_content()
        message = self._create_message(**response)
        self.response_created = True
        self._send_buffer += message