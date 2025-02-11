import io
import json
import selectors
import struct
import sys
from database import MessageDatabase
from custom_protocol_2 import CustomProtocol

db = MessageDatabase()

class Message:
    def __init__(self, selector, sock, addr, accepted_versions):
        self.selector = selector
        self.sock = sock
        self.addr = addr
        self._recv_buffer = b""
        self._send_buffer = b""
        self._header_len = None
        self.header = None
        self.request = None
        self.response_created = False
        self.protocol_mode = "custom"
        self.custom_protocol = CustomProtocol()
        self.accepted_versions = accepted_versions

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
                    self._header_len = None
                    self.header = None
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

    def _create_message(
        self, *, content_bytes, action, content_length
    ):
        header = {
            "content-length": content_length,
            "action": action,
        }
        if self.protocol_mode == "json":
            header_bytes = self._json_encode(header, "utf-8")
        elif self.protocol_mode == "custom":
            checksum = self.custom_protocol.compute_checksum(content_bytes)
            header["checksum"] = checksum
            header_bytes = self.custom_protocol.serialize(header)
        else:
            raise ValueError(f"Invalid protocol mode {self.protocol_mode!r}")
        # Pack version (1 byte) and header length (2 bytes)
        message_hdr = struct.pack(">BH", 1, len(header_bytes))
        message = message_hdr + header_bytes + content_bytes
        return message
    
    def check_fields(self, action, request):
        fields = self.custom_protocol.dict_reconstruction.get(action)
        if not fields:
            return False
        for field in fields:
            if field not in request:
                return False
            if request.get(field) is None:
                return False
        return True

    def _create_response_content(self):
        # First decode the request content
        if self.protocol_mode == "json":
            request_content = self._json_decode(self.request, "utf-8")
        elif self.protocol_mode == "custom":
            request_content = self.custom_protocol.deserialize(self.request, self.header["action"])
            computed_checksum = self.custom_protocol.compute_checksum(self.request)
            if computed_checksum != self.header.get("checksum") or not request_content:
                self.header["action"] = "error"

        # Check fields in request are there
        if not self.check_fields(self.header["action"], request_content):
            self.header["action"] = "error"

        response_content = {}
        action = "error"
        print("action: ", self.header["action"])
        # Create response content and encode it
        if self.header["action"] == "login_register":
            # try to login
            accounts = db.login_or_create_account(request_content.get("username"), request_content.get("password"), str(self.addr))
            print("account: ", accounts)
            if (len(accounts) != 1):
                response_content = {
                    "message": "Invalid username or password",
                }
                action = "login_error"
            else:
                response_content = {
                    "uuid": accounts[0]["userid"],
                }
                action = "login_register_r"
        elif self.header["action"] == "load_page_data":
            user_uuid = request_content.get("uuid")

            # Load page data
            messages, num_pending, accounts, total_count = db.load_page_data(user_uuid)
            print(f"Loaded page data from db")
            
            response_content = {
                "messages": messages,
                "num_pending": num_pending,
                "accounts": accounts,
                "total_count": total_count,
            }
            action = "load_page_data_r"

        elif self.header["action"] == "search_accounts":
            search_term = request_content.get("search_term", "")
            offset = request_content.get("offset", 0)
            
            # Search for accounts with pagination
            accounts, total_count = db.search_accounts(search_term, offset)
            print(f"Found {len(accounts)} accounts (total: {total_count})")
            
            response_content = {
                "accounts": accounts,
                "total_count": total_count,
            }
            action = "search_accounts_r"
        elif self.header["action"] == "load_messages":
            user_uuid = request_content.get("uuid")
            num_messages = request_content.get("num_messages")
            print(f"Loading messages for user {user_uuid} and num_messages {num_messages}")
            
            messages, total_undelivered = db.load_messages(user_uuid, num_messages)
            print(f"Found {len(messages)} messages (total: {total_undelivered})")
            
            response_content = {
                "messages": messages,
                "total_count": total_undelivered,
            }
            action = "load_messages_r"
        elif self.header["action"] == "send_message":
            # Extract message details
            sender_uuid = request_content.get("uuid")
            recipient_username = request_content.get("recipient_username")
            message_text = request_content.get("message")
            timestamp = request_content.get("timestamp")

            print("message details: ", sender_uuid, recipient_username, message_text, timestamp)
            
            # Get recipient's UUID
            success_status, error_msg, recipient_uuid = db.get_user_uuid(recipient_username)
            if success_status:
                # Get recipient's associated socket
                recipient_socket = db.get_associated_socket(recipient_uuid)
                sender_username = db.get_user_username(sender_uuid)
                print(sender_username)
                
                # ensure all fields are there
                if recipient_socket and sender_username:
                    # recipient online?
                    status = False

                    # Create message content for recipient
                    relay_content = {
                        "message": message_text,
                        "sender_uuid": sender_uuid,
                        "sender_username": sender_username,
                    }
                    
                    # Convert content to bytes for sending
                    if self.protocol_mode == "json":
                        relay_content_bytes = self._json_encode(relay_content, "utf-8")
                    elif self.protocol_mode == "custom":
                        relay_content_bytes = self.custom_protocol.serialize(relay_content)
                    else:
                        raise ValueError(f"Invalid protocol mode {self.protocol_mode!r}")
                    relay_message = self._create_message(
                        content_bytes=relay_content_bytes,
                        action="receive_message",
                        content_length=len(relay_content_bytes)
                    )
                    
                    # Send message to recipient's socket
                    try:
                        # Find the socket object associated with the recipient
                        for key, data in self.selector.get_map().items():
                            if data.data and isinstance(data.data, Message) and str(data.data.addr) == recipient_socket:
                                print(f"Relaying message to {recipient_socket}")
                                status = True
                                data.data._send_buffer += relay_message
                                data.data._set_selector_events_mask("w")
                                break
                        else:
                            print(f"Error: Could not find recipient socket {recipient_socket}")
                            status = False
                    except Exception as e:
                        print(f"Error relaying message: {e}")

                # Store the message
                success_status, error_msg = db.store_message(sender_uuid, recipient_uuid, message_text, status, timestamp)
                    
            # Create response for sender
            response_content = {
                "success": success_status,
                "error": error_msg,
            }
            action = "send_message_r"
        elif self.header["action"] == "load_undelivered":
            user_uuid = request_content.get("uuid", None)
            num_messages = request_content.get("num_messages", 0)
            print(f"Loading undelivered messages for user {user_uuid}")
            
            # Load undelivered messages
            messages = db.load_undelivered(user_uuid, num_messages)
            print(f"Found {len(messages)} undelivered messages")
            
            response_content = {
                "messages": messages,
            }
            action = "load_undelivered_r"
        elif self.header["action"] == "delete_messages":
            print("Deleting messages")
            msg_ids = request_content.get("msgids", [])
            num_deleted = db.delete_messages(msg_ids)
            print(f"db delete_messages ran")
            response_content = {
                "total_count": num_deleted,
            }
            action = "delete_messages_r"
        elif self.header["action"] == "delete_account":
            user_uuid = request_content.get("uuid")
            password = request_content.get("password")
            
            # Get the stored password from database
            stored_password = db.get_user_password(user_uuid)
            print(f"Retrieved stored password: {'Found' if stored_password else 'Not found'}")
            success = False
            error_message = ""
            if stored_password == password:
                # Password matches, delete the account
                if db.delete_user(user_uuid):
                    success = True
                else:
                    error_message = "Failed to delete account"
            else:
                error_message = "Incorrect password"
            response_content = {
                "success": success,
                "error": error_message,
            }
            action = "delete_account_r"
        elif self.header["action"] == "error":
            response_content = {
                "error": f"An error occurred. Please try again."
            }
            action = "error"
        else:
            response_content = {
                "error": f"Invalid action: {self.header['action']}"
            }
            action = "error"
            
        if self.protocol_mode == "json":
            content_bytes = self._json_encode(response_content, "utf-8")
        elif self.protocol_mode == "custom":
            content_bytes = self.custom_protocol.serialize(response_content)
            
        response = {
            "content_bytes": content_bytes,
            "action": action,
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

        if self._header_len is None:
            self.process_protoheader()

        if self._header_len is not None:
            if self.header is None:
                self.process_header()

        if self.header:
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
        version_len = 1  # 1 byte for version
        hdrlen = 2  # fixed length for header length
        
        # First check version
        if len(self._recv_buffer) >= version_len:
            version = struct.unpack(">B", self._recv_buffer[:version_len])[0]
            if version not in self.accepted_versions:
                raise ValueError(f"Cannot handle protocol version {version}")
            self._recv_buffer = self._recv_buffer[version_len:]
        else:
            return
            
        # Then process header length
        if len(self._recv_buffer) >= hdrlen:
            self._header_len = struct.unpack(
                ">H", self._recv_buffer[:hdrlen]
            )[0]
            self._recv_buffer = self._recv_buffer[hdrlen:]

    def process_header(self):
        hdrlen = self._header_len
        if len(self._recv_buffer) >= hdrlen:
            if self.protocol_mode == "json":
                self.header = self._json_decode(
                    self._recv_buffer[:hdrlen], "utf-8"
                )
            elif self.protocol_mode == "custom":
                self.header = self.custom_protocol.deserialize(self._recv_buffer[:hdrlen], "header")
            else:
                raise ValueError(f"Invalid protocol mode {self.protocol_mode!r}")
            self._recv_buffer = self._recv_buffer[hdrlen:]
            for reqhdr in (
                "content-length",
                "action",
            ):
                if reqhdr not in self.header:
                    self.header["action"] = "error"

    def process_request(self):
        content_len = self.header["content-length"]
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
        response = self._create_response_content()
        message = self._create_message(**response)
        self.response_created = True
        self._send_buffer += message