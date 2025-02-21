import grpc
from concurrent import futures
import chat_pb2
import chat_pb2_grpc
from database import MessageDatabase
from logger import set_logger
import datetime
import json
import sys
import time

logger = set_logger("grpc_server", "grpc_server.log")

class ChatServicer(chat_pb2_grpc.ChatServiceServicer):
    def __init__(self):
        self.db = MessageDatabase()
        self.active_streams = {}  # UUID -> list of stream contexts

    def Login(self, request, context):
        try:
            result = self.db.login(request.username, request.hashed_password)
            if result:
                return chat_pb2.LoginResponse(
                    success=True,
                    uuid=result[0]["userid"]
                )
            return chat_pb2.LoginResponse(success=False, error="Invalid credentials")
        except Exception as e:
            logger.error(f"Login error: {e}")
            return chat_pb2.LoginResponse(success=False, error=str(e))

    def Register(self, request, context):
        try:
            uuid, error = self.db.register(request.username, request.hashed_password)
            if uuid:
                return chat_pb2.RegisterResponse(success=True, uuid=uuid)
            return chat_pb2.RegisterResponse(success=False, error=error)
        except Exception as e:
            logger.error(f"Register error: {e}")
            return chat_pb2.RegisterResponse(success=False, error=str(e))

    def CheckUsername(self, request, context):
        try:
            exists, success = self.db.check_username(request.username)
            if success:
                return chat_pb2.CheckUsernameResponse(is_available=not exists)
            return chat_pb2.CheckUsernameResponse(is_available=False)
        except Exception as e:
            logger.error(f"Check username error: {e}")
            return chat_pb2.CheckUsernameResponse(is_available=False)

    def DeleteAccount(self, request, context):
        try:
            stored_password = self.db.get_user_password(request.uuid)
            if stored_password != request.hashed_password:
                return chat_pb2.DeleteAccountResponse(success=False, error="Invalid password")
            
            # Delete messages first
            affected_users = self.db.delete_user_messages(request.uuid)


            # get username
            username = self.db.get_user_username(request.uuid)
            
            # Delete the account
            if username and self.db.delete_user(request.uuid):
                # Notify other users about message deletions
                self._notify_message_deletions(affected_users)
                # Notify user about account deletion
                self._notify_account_deletion(request.uuid, username)
                return chat_pb2.DeleteAccountResponse(success=True)
            return chat_pb2.DeleteAccountResponse(success=False, error="Failed to delete account")
        except Exception as e:
            logger.error(f"Delete account error: {e}")
            return chat_pb2.DeleteAccountResponse(success=False, error=str(e))

    def SearchAccounts(self, request, context):
        try:
            accounts, total_count = self.db.search_accounts(request.search_term, request.offset)
            account_protos = [
                chat_pb2.Account(uuid=acc[0], username=acc[1])
                for acc in accounts
            ]
            return chat_pb2.SearchAccountsResponse(
                accounts=account_protos,
                total_count=total_count
            )
        except Exception as e:
            logger.error(f"Search accounts error: {e}")
            return chat_pb2.SearchAccountsResponse()

    def SendMessage(self, request, context):
        try:
            success, error, msg_id = self.db.store_message(
                request.sender_uuid,
                request.recipient_username,
                request.message,
                True,  # status
                request.timestamp
            )
            if success:
                # Notify recipient with message ID
                self._notify_new_message(request, msg_id)
                return chat_pb2.SendMessageResponse(success=True)
            return chat_pb2.SendMessageResponse(success=False, error=error)
        except Exception as e:
            logger.error(f"Send message error: {e}")
            return chat_pb2.SendMessageResponse(success=False, error=str(e))

    def LoadMessages(self, request, context):
        """Load messages for a user."""
        try:
            messages, total_undelivered = self.db.load_messages(request.uuid, request.num_messages)
            
            # Convert tuple messages to Message protos
            message_protos = []
            for msg in messages:
                message_protos.append(chat_pb2.Message(
                    message_id=msg[0],
                    sender_username=msg[1],
                    recipient_username=msg[2],
                    message=msg[3],
                    timestamp=msg[4],
                    status=self._convert_status(msg[5])
                ))
            
            return chat_pb2.LoadMessagesResponse(
                messages=message_protos,
                total_undelivered=total_undelivered
            )
        except Exception as e:
            logger.error(f"Load messages error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return chat_pb2.LoadMessagesResponse()

    def _convert_status(self, status_str):
        """Convert status string to enum value."""
        status_map = {
            'pending': chat_pb2.MessageStatus.PENDING,
            'delivered': chat_pb2.MessageStatus.DELIVERED,
            'seen': chat_pb2.MessageStatus.SEEN
        }
        return status_map.get(status_str, chat_pb2.MessageStatus.PENDING)

    def LoadUndeliveredMessages(self, request, context):
        try:
            messages = self.db.load_undelivered(request.uuid, request.num_messages)
            message_protos = [self._convert_to_message_proto(msg) for msg in messages]
            return chat_pb2.LoadUndeliveredResponse(messages=message_protos)
        except Exception as e:
            logger.error(f"Load undelivered error: {e}")
            return chat_pb2.LoadUndeliveredResponse()

    def DeleteMessages(self, request, context):
        try:
            affected_users = self.db.delete_messages(request.message_ids)
            self._notify_message_deletions(affected_users)
            return chat_pb2.DeleteMessagesResponse(
                success=True,
                total_deleted=len(request.message_ids)
            )
        except Exception as e:
            logger.error(f"Delete messages error: {e}")
            return chat_pb2.DeleteMessagesResponse(success=False, total_deleted=0)

    def LoadPrivateChat(self, request, context):
        try:
            messages = self.db.load_private_chat(request.current_uuid, request.other_username)
            message_protos = [self._convert_to_message_proto(msg) for msg in messages]
            return chat_pb2.LoadPrivateChatResponse(messages=message_protos)
        except Exception as e:
            logger.error(f"Load private chat error: {e}")
            return chat_pb2.LoadPrivateChatResponse()

    def StreamUpdates(self, request, context):
        """Handle streaming updates to the client."""
        if request.uuid not in self.active_streams:
            self.active_streams[request.uuid] = []
        self.active_streams[request.uuid].append(context)

        try:
            # Keep the stream alive until the client disconnects
            while context.is_active():
                # Use time.sleep instead of context.sleep
                time.sleep(1)
                # Yield any pending updates one by one and remove them from the list
                if hasattr(context, 'pending_updates'):
                    while context.pending_updates:
                        update = context.pending_updates.pop(0)
                        yield update
        except Exception as e:
            logger.error(f"Stream error: {e}")
        finally:
            if request.uuid in self.active_streams:
                self.active_streams[request.uuid].remove(context)
                if not self.active_streams[request.uuid]:
                    del self.active_streams[request.uuid]

    def _notify_new_message(self, message, msg_id):
        """Notify recipient of new message through their active stream."""
        try:
            success, _, recipient_uuid = self.db.get_user_uuid(message.recipient_username)
            if success and recipient_uuid in self.active_streams:
                update = chat_pb2.UpdateResponse(
                    new_message=chat_pb2.Message(
                        message_id=msg_id,
                        sender_username=self.db.get_user_username(message.sender_uuid),
                        recipient_username=message.recipient_username,
                        message=message.message,
                        timestamp=message.timestamp,
                        status=chat_pb2.MessageStatus.DELIVERED
                    )
                )
                for stream in self.active_streams[recipient_uuid]:
                    try:
                        if not hasattr(stream, 'pending_updates'):
                            stream.pending_updates = []
                        stream.pending_updates.append(update)
                    except Exception as e:
                        logger.error(f"Failed to send update: {e}")
        except Exception as e:
            logger.error(f"Error in notify_new_message: {e}")

    def _notify_message_deletions(self, affected_users):
        """Notify users about deleted messages."""
        for uuid, count in affected_users:
            if uuid in self.active_streams:
                update = chat_pb2.UpdateResponse(
                    message_deletion=chat_pb2.MessageDeletion(
                        total_count=count
                    )
                )
                for stream in self.active_streams[uuid]:
                    try:
                        stream.send(update)
                    except Exception as e:
                        logger.error(f"Failed to send deletion update: {e}")

    def _notify_account_deletion(self, uuid, username):
        """Notify all users about account deletion."""
        update = chat_pb2.UpdateResponse(
            account_update=chat_pb2.AccountUpdate(
                type=chat_pb2.UpdateType.ACCOUNT_REMOVED,
                account=chat_pb2.Account(
                    uuid=uuid,
                    username=username
                )
            )
        )

        for user_uuid, streams in self.active_streams.items():
            for stream in streams:
                try:
                    if not hasattr(stream, 'pending_updates'):
                            stream.pending_updates = []
                    stream.pending_updates.append(update)
                except Exception as e:
                    logger.error(f"Failed to send account deletion update: {e}")

    def _convert_to_message_proto(self, msg_dict):
        """Convert a message dictionary to a Message proto."""
        status_map = {
            'pending': chat_pb2.MessageStatus.PENDING,
            'delivered': chat_pb2.MessageStatus.DELIVERED,
            'seen': chat_pb2.MessageStatus.SEEN
        }
        
        return chat_pb2.Message(
            message_id=msg_dict.get('msgid', 0),
            sender_username=msg_dict['sender_username'],
            recipient_username=msg_dict['recipient_username'],
            message=msg_dict['message'],
            timestamp=msg_dict['timestamp'],
            status=status_map.get(msg_dict.get('status', 'pending'), chat_pb2.MessageStatus.PENDING)
        )

def serve():
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            
        server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=config.get('max_workers', 10))
        )
        chat_pb2_grpc.add_ChatServiceServicer_to_server(
            ChatServicer(), 
            server
        )
        
        server.add_insecure_port(
            f"{config['host']}:{config['port']}"
        )
        
        logger.info(f"Starting server on {config['host']}:{config['port']}")
        server.start()
        server.wait_for_termination()
        
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        server.stop(0)
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    serve() 