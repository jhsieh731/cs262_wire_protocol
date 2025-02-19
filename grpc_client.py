import grpc
import chat_pb2
import chat_pb2_grpc
from logger import set_logger
import threading

logger = set_logger("grpc_client", "grpc_client.log")

class ChatClient:
    def __init__(self, host='localhost', port=50051):
        self.channel = grpc.insecure_channel(f'{host}:{port}')
        self.stub = chat_pb2_grpc.ChatServiceStub(self.channel)
        self.update_stream = None
        self.update_thread = None
        self.callback = None

    def set_update_callback(self, callback):
        """Set callback function for handling server updates."""
        self.callback = callback

    def start_update_stream(self, uuid):
        """Start listening for updates from the server."""
        def stream_updates():
            try:
                request = chat_pb2.StreamUpdatesRequest(uuid=uuid)
                for update in self.stub.StreamUpdates(request):
                    if self.callback:
                        self.callback(update)
            except Exception as e:
                logger.error(f"Stream updates error: {e}")

        self.update_thread = threading.Thread(target=stream_updates, daemon=True)
        self.update_thread.start()

    def login(self, username, hashed_password):
        """Login to the server."""
        try:
            request = chat_pb2.LoginRequest(
                username=username,
                hashed_password=hashed_password
            )
            response = self.stub.Login(request)
            return response
        except Exception as e:
            logger.error(f"Login error: {e}")
            return chat_pb2.LoginResponse(success=False, error=str(e))

    def register(self, username, hashed_password):
        """Register a new user."""
        try:
            request = chat_pb2.RegisterRequest(
                username=username,
                hashed_password=hashed_password
            )
            response = self.stub.Register(request)
            return response
        except Exception as e:
            logger.error(f"Register error: {e}")
            return chat_pb2.RegisterResponse(success=False, error=str(e))

    def check_username(self, username):
        """Check if a username is available."""
        try:
            request = chat_pb2.CheckUsernameRequest(username=username)
            response = self.stub.CheckUsername(request)
            return response
        except Exception as e:
            logger.error(f"Check username error: {e}")
            return chat_pb2.CheckUsernameResponse(is_available=False)

    def delete_account(self, uuid, hashed_password):
        """Delete user account."""
        try:
            request = chat_pb2.DeleteAccountRequest(
                uuid=uuid,
                hashed_password=hashed_password
            )
            response = self.stub.DeleteAccount(request)
            return response
        except Exception as e:
            logger.error(f"Delete account error: {e}")
            return chat_pb2.DeleteAccountResponse(success=False, error=str(e))

    def search_accounts(self, search_term, offset):
        """Search for user accounts."""
        try:
            request = chat_pb2.SearchAccountsRequest(
                search_term=search_term,
                offset=offset
            )
            response = self.stub.SearchAccounts(request)
            return response
        except Exception as e:
            logger.error(f"Search accounts error: {e}")
            return chat_pb2.SearchAccountsResponse()

    def send_message(self, sender_uuid, recipient_username, message, timestamp):
        """Send a message to another user."""
        try:
            request = chat_pb2.SendMessageRequest(
                sender_uuid=sender_uuid,
                recipient_username=recipient_username,
                message=message,
                timestamp=timestamp
            )
            response = self.stub.SendMessage(request)
            return response
        except Exception as e:
            logger.error(f"Send message error: {e}")
            return chat_pb2.SendMessageResponse(success=False, error=str(e))

    def load_messages(self, uuid, num_messages):
        """Load messages for a user."""
        try:
            request = chat_pb2.LoadMessagesRequest(
                uuid=uuid,
                num_messages=num_messages
            )
            response = self.stub.LoadMessages(request)
            return response
        except Exception as e:
            logger.error(f"Load messages error: {e}")
            return chat_pb2.LoadMessagesResponse()

    def load_undelivered_messages(self, uuid, num_messages):
        """Load undelivered messages for a user."""
        try:
            request = chat_pb2.LoadUndeliveredRequest(
                uuid=uuid,
                num_messages=num_messages
            )
            response = self.stub.LoadUndeliveredMessages(request)
            return response
        except Exception as e:
            logger.error(f"Load undelivered messages error: {e}")
            return chat_pb2.LoadUndeliveredResponse()

    def delete_messages(self, message_ids, deleter_uuid):
        """Delete messages."""
        try:
            request = chat_pb2.DeleteMessagesRequest(
                message_ids=message_ids,
                deleter_uuid=deleter_uuid
            )
            response = self.stub.DeleteMessages(request)
            return response
        except Exception as e:
            logger.error(f"Delete messages error: {e}")
            return chat_pb2.DeleteMessagesResponse(success=False, total_deleted=0)

    def load_private_chat(self, current_uuid, other_username):
        """Load private chat messages."""
        try:
            request = chat_pb2.LoadPrivateChatRequest(
                current_uuid=current_uuid,
                other_username=other_username
            )
            response = self.stub.LoadPrivateChat(request)
            return response
        except Exception as e:
            logger.error(f"Load private chat error: {e}")
            return chat_pb2.LoadPrivateChatResponse()

    def close(self):
        """Close the gRPC channel."""
        self.channel.close() 