import io
import json
import selectors
import struct
import sys
from datetime import datetime
from database import MessageDatabase
from custom_protocol_2 import CustomProtocol
from logger import set_logger

logger = set_logger("msg_server", "msg_server.log")

db = MessageDatabase()

class Message:
    def __init__(self, selector, sock, addr, accepted_versions, protocol):
        self.selector = selector
        self.sock = sock
        self.addr = addr
        self._recv_buffer = b""
        self._send_buffer = b""
        self._header_len = None
        self.header = None
        self.request = None
        self.response_created = False
        self.protocol_mode = protocol
        self.custom_protocol = CustomProtocol()
        self.accepted_versions = accepted_versions

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
        """Read from the client socket"""
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
        """Write to the client socket"""
        if self._send_buffer:
            logger.info(f"Sending {self._send_buffer!r} to {self.addr}")
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
        """Encode a JSON object and return bytes"""
        return json.dumps(obj, ensure_ascii=False).encode(encoding)

    def _json_decode(self, json_bytes, encoding):
        """Decode JSON bytes and return a Python object"""
        tiow = io.TextIOWrapper(
            io.BytesIO(json_bytes), encoding=encoding, newline=""
        )
        obj = json.load(tiow)
        tiow.close()
        return obj

    def _create_message(
        self, *, content_bytes, action, content_length
    ):
        """Create a message with the given content"""
        header = {
            "version": 1,
            "content-length": content_length,
            "action": action,
        }
        if self.protocol_mode == "json":
            header_bytes = self._json_encode(header, "utf-8")
        elif self.protocol_mode == "custom":
            checksum = self.custom_protocol.compute_checksum(content_bytes)
            header["checksum"] = checksum
            header_bytes = self.custom_protocol.serialize(header)
        
        # Pack version (1 byte), protocol type, and header length (2 bytes)
        protocol_byte = 0 if self.protocol_mode == "json" else 2
        message_hdr = struct.pack(">BBH", 1, protocol_byte, len(header_bytes))
        message = message_hdr + header_bytes + content_bytes
        return message
    
    def check_fields(self, action, request):
        """Check if all required fields are present in the request"""
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
        """Create response content based on the request"""
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
        logger.info(f"action: {self.header['action']}")
        # Create response content and encode it
        if self.header["action"] == "login":
            # try to login
            accounts = db.login(request_content.get("username"), request_content.get("password"), str(self.addr))
            logger.info(f"Account lookup result: {accounts}")
            if (len(accounts) != 1):
                response_content = {
                    "message": "Please try again",
                }
                action = "login_error"
            else:
                response_content = {
                    "uuid": accounts[0]["userid"],
                }
                action = "login_r"

        elif self.header["action"] == "check_username":
            username = request_content.get("username")
            is_in_use, success_status = db.check_username(username)
            if not success_status:
                response_content = {
                    "message": "An error occurred. Please try again."
                }
                action = "login_error"
            else:
                response_content = {
                    "message": is_in_use,
                }
                action = "check_username_r"
        
        elif self.header["action"] == "register":
            username = request_content.get("username")
            password = request_content.get("password")
            uuid, error_msg = db.register(username, password, str(self.addr))
            if error_msg:
                response_content = {
                    "error": error_msg,
                }
                action = "error"
            else:

                # Notify all other clients to refresh their account lists
                refresh_content = {
                    "message": "Account created"
                }
                if self.protocol_mode == "json":
                    refresh_content_bytes = self._json_encode(refresh_content, "utf-8")
                else:
                    refresh_content_bytes = self.custom_protocol.serialize(refresh_content)
                
                refresh_message = self._create_message(
                    content_bytes=refresh_content_bytes,
                    action="refresh_accounts_r",
                    content_length=len(refresh_content_bytes)
                )
                
                # Collect sockets to notify first
                sockets_to_notify = []
                for _, data in self.selector.get_map().items():
                    if data.data and isinstance(data.data, Message) and data.data.sock != self.sock:
                        sockets_to_notify.append(data.data)
                
                # Then notify each socket
                for socket_data in sockets_to_notify:
                    socket_data._send_buffer += refresh_message
                    socket_data._set_selector_events_mask("w")
                

                response_content = {
                    "uuid": uuid,
                }
                action = "register_r"

        elif self.header["action"] == "load_page_data":
            user_uuid = request_content.get("uuid")

            # Load page data
            messages, num_pending, accounts, total_count = db.load_page_data(user_uuid)
            logger.info(f"Loaded page data from db")
            
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
            logger.info(f"Found {len(accounts)} accounts (total: {total_count})")
            
            response_content = {
                "accounts": accounts,
                "total_count": total_count,
            }
            action = "search_accounts_r"
        elif self.header["action"] == "load_messages":
            user_uuid = request_content.get("uuid")
            num_messages = request_content.get("num_messages")
            logger.info(f"Loading messages for user {user_uuid} and num_messages {num_messages}")
            
            messages, total_undelivered = db.load_messages(user_uuid, num_messages)
            logger.info(f"Found {len(messages)} messages (total: {total_undelivered})")
            
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

            logger.info(f"Message details - Sender: {sender_uuid}, Recipient: {recipient_username}, Message: {message_text}, Time: {timestamp}")
            
            # Get recipient's UUID
            success_status, error_msg, recipient_uuid = db.get_user_uuid(recipient_username)
            if success_status:
                # Get recipient's associated socket
                recipient_socket = db.get_associated_socket(recipient_uuid)
                sender_username = db.get_user_username(sender_uuid)
                logger.info(sender_username)
                
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
                    
                    relay_message = self._create_message(
                        content_bytes=relay_content_bytes,
                        action="receive_message_r",
                        content_length=len(relay_content_bytes)
                    )
                    
                    # Send message to recipient's socket
                    try:
                        # Find the socket object associated with the recipient
                        for key, data in self.selector.get_map().items():
                            if data.data and isinstance(data.data, Message) and str(data.data.addr) == recipient_socket:
                                logger.info(f"Relaying message to {recipient_socket}")
                                status = True
                                data.data._send_buffer += relay_message
                                data.data._set_selector_events_mask("w")
                                break
                        else:
                            logger.error(f"Error: Could not find recipient socket {recipient_socket}")
                            status = False
                    except Exception as e:
                        logger.error(f"Error relaying message: {e}")

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
            logger.info(f"Loading undelivered messages for user {user_uuid}")
            
            # Load undelivered messages from db
            messages = db.load_undelivered(user_uuid, num_messages)
            logger.info(f"Found {len(messages)} undelivered messages")
            
            response_content = {
                "messages": messages,
            }
            action = "load_undelivered_r"
        elif self.header["action"] == "delete_messages":
            msg_ids = request_content.get("msgids", [])
            num_deleted = db.delete_messages(msg_ids)
            response_content = {
                "total_count": num_deleted,
            }
            action = "delete_messages_r"
        elif self.header["action"] == "delete_account":
            user_uuid = request_content.get("uuid")
            password = request_content.get("password")
            
            # Get the stored password from database
            stored_password = db.get_user_password(user_uuid)
            logger.info(f"Retrieved stored password: {'Found' if stored_password else 'Not found'}")
            success = False
            error_message = ""
            if stored_password == password:
                # Password matches, delete the account
                if db.delete_user(user_uuid):
                    success = True
                    # Notify all other clients to refresh their account lists
                    response_content = {}
                    if self.protocol_mode == "json":
                        response_content_bytes = self._json_encode(response_content, "utf-8")
                    else:
                        response_content_bytes = self.custom_protocol.serialize(response_content)
                    
                    refresh_message = self._create_message(
                        content_bytes=response_content_bytes,
                        action="refresh_accounts_r",
                        content_length=len(response_content_bytes)
                    )
                    
                    # Collect sockets to notify first
                    sockets_to_notify = []
                    for key, data in self.selector.get_map().items():
                        if data.data and isinstance(data.data, Message) and data.data.sock != self.sock:
                            sockets_to_notify.append(data.data)
                    
                    # Then notify each socket
                    for socket_data in sockets_to_notify:
                        socket_data._send_buffer += refresh_message
                        socket_data._set_selector_events_mask("w")
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
        """Process selector events (first step)"""
        if mask & selectors.EVENT_READ:
            logger.debug("Read event received")
            self.read()
        if mask & selectors.EVENT_WRITE:
            logger.debug("Write event received")
            self.write()

    def read(self):
        """Read data pipeline from the client socket (step 2 if read)"""
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
        """Write data pipeline to the client socket (step 2 if write)"""
        if self.request:
            if not self.response_created:
                self.create_response()

        self._write()

    def close(self):
        """Close the connection to the client socket"""
        logger.info(f"Closing connection to {self.addr}")
        try:
            self.selector.unregister(self.sock)
        except Exception as e:
            logger.error(
                f"Error: selector.unregister() exception for "
                f"{self.addr}: {e!r}"
            )

        try:
            self.sock.close()
        except OSError as e:
            logger.error(f"Error: socket.close() exception for {self.addr}: {e!r}")
        finally:
            # Delete reference to socket object for garbage collection
            self.sock = None


    def process_protoheader(self):
        """Process the protocol header (step 1 of read pipeline)"""
        version_len = 1  # 1 byte for version
        protocol_len = 1  # 1 byte for protocol type
        hdrlen = 2  # fixed length for header length
        
        # First check version
        if len(self._recv_buffer) >= (version_len + protocol_len):
            version = struct.unpack(">B", self._recv_buffer[:version_len])[0]
            if version not in self.accepted_versions:
                raise ValueError(f"Cannot handle protocol version {version}")
            self._recv_buffer = self._recv_buffer[version_len:]
            client_protocol_num = struct.unpack(">B", self._recv_buffer[:protocol_len])[0]
            client_protocol = "json" if client_protocol_num == 0 else "custom"
            if self.protocol_mode != client_protocol:
                raise ValueError(f"Client protocol {client_protocol} does not match server protocol {self.protocol_mode}")
            self._recv_buffer = self._recv_buffer[protocol_len:]
        else:
            return
            
        # Then process header length
        if len(self._recv_buffer) >= hdrlen:
            self._header_len = struct.unpack(
                ">H", self._recv_buffer[:hdrlen]
            )[0]
            self._recv_buffer = self._recv_buffer[hdrlen:]

    def process_header(self):
        """Process the header (step 2 of read pipeline)"""
        hdrlen = self._header_len

        if len(self._recv_buffer) >= hdrlen:
            # Validate protocol mode
            if self.protocol_mode not in ["json", "custom"]:
                raise ValueError(f"Invalid protocol mode {self.protocol_mode!r}")

            # Decode the header based on the protocol mode
            if self.protocol_mode == "json":
                self.header = self._json_decode(
                    self._recv_buffer[:hdrlen], "utf-8"
                )
            elif self.protocol_mode == "custom":
                self.header = self.custom_protocol.deserialize(self._recv_buffer[:hdrlen], "header")
            
            self._recv_buffer = self._recv_buffer[hdrlen:]
            # check minimum required fields are present
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
        self.request = data
        logger.info(f"Stored request data: {self.request!r}")
        # Set selector to listen for write events, we're ready to respond
        self._set_selector_events_mask("w")

    def create_response(self):
        """Create a response based on the request"""
        response = self._create_response_content()
        message = self._create_message(**response)
        self.response_created = True
        self._send_buffer += message