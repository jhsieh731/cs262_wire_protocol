import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk
import hashlib
import datetime
from gui import ClientGUI

# to run: python3 -m unittest test_suite/test_gui.py -v

class TestClientGUI(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.send_to_server = MagicMock()
        self.network_thread = MagicMock()
        with patch('tkinter.messagebox.showerror'):
            self.gui = ClientGUI(self.root, self.send_to_server, self.network_thread)
        
    def tearDown(self):
        try:
            if hasattr(self.gui, 'dialog') and self.gui.dialog:
                self.gui.dialog.destroy()
        except tk.TclError:
            pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        
    def test_init(self):
        """Test initialization of GUI"""
        self.assertIsNone(self.gui.user_uuid)
        self.assertIsNone(self.gui.selected_account)
        self.assertEqual(self.gui.username, "")
        self.assertEqual(self.gui.current_page, 0)
        self.assertEqual(self.gui.max_accounts_page, 0)
        self.assertEqual(self.gui.num_messages, 10)
        self.assertEqual(self.gui.num_undelivered, 0)
        self.assertEqual(self.gui.msgid_map, {})

    def test_clear_frame(self):
        """Test frame clearing"""
        frame = tk.Frame(self.root)
        label = tk.Label(frame, text="test")
        label.pack()
        self.gui.clear_frame(frame)
        self.assertEqual(len(frame.winfo_children()), 0)

    def test_create_error_page(self):
        """Test error page creation"""
        error_msg = "Test error"
        self.gui.create_error_page(error_msg)
        self.root.update()
        error_widgets = self.gui.error_frame.winfo_children()
        self.assertTrue(any(widget.cget("text") == error_msg for widget in error_widgets))

    def test_create_login_page(self):
        """Test login page creation"""
        self.gui.create_login_page()
        self.root.update()
        self.assertTrue(hasattr(self.gui, 'username_entry'))
        self.assertTrue(hasattr(self.gui, 'password_entry'))

    def test_create_chat_page(self):
        """Test chat page creation"""
        self.gui.create_chat_page()
        self.root.update()
        self.assertTrue(hasattr(self.gui, 'accounts_listbox'))
        self.assertTrue(hasattr(self.gui, 'messages_listbox'))
        self.assertTrue(hasattr(self.gui, 'message_display'))

    def test_create_confirm_delete_account(self):
        """Test delete account confirmation dialog"""
        self.gui.create_confirm_delete_account_page()
        self.root.update()
        self.assertTrue(hasattr(self.gui, 'dialog'))
        self.assertTrue(hasattr(self.gui, 'dialog_password_entry'))

    def test_hash_password(self):
        """Test password hashing function"""
        password = "testpassword"
        expected_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        self.assertEqual(self.gui.hash_password(password), expected_hash)

    def test_prev_page(self):
        """Test previous page navigation"""
        self.gui.current_page = 1
        with patch.object(self.gui, 'search_accounts') as mock_search:
            self.gui.prev_page()
            self.assertEqual(self.gui.current_page, 0)
            mock_search.assert_called_once()

    def test_next_page(self):
        """Test next page navigation"""
        self.gui.current_page = 0
        self.gui.max_accounts_page = 1
        with patch.object(self.gui, 'search_accounts') as mock_search:
            self.gui.next_page()
            self.assertEqual(self.gui.current_page, 1)
            mock_search.assert_called_once()

    def test_on_account_select(self):
        """Test account selection"""
        self.gui.create_chat_page()  # Initialize required widgets
        self.root.update()
        mock_event = MagicMock()
        mock_event.widget = self.gui.accounts_listbox
        mock_event.widget.curselection = MagicMock(return_value=[0])
        mock_event.widget.get = MagicMock(return_value="test_user")
        self.gui.on_account_select(mock_event)
        self.assertEqual(self.gui.selected_account, "test_user")

    def test_load_more_messages(self):
        """Test loading more messages"""
        initial_num = self.gui.num_messages
        self.gui.load_more_messages()
        self.assertEqual(self.gui.num_messages, initial_num + 10)

    def test_update_message_input_area(self):
        """Test updating message input area"""
        self.gui.create_chat_page()
        self.root.update()
        self.gui.selected_account = "testuser"
        self.gui.update_message_input_area()
        self.gui.message_display.config(state=tk.NORMAL)
        content = self.gui.message_display.get("1.0", tk.END).strip()
        self.assertEqual(content, f"Your chat with testuser")

    def test_update_accounts_list(self):
        """Test updating accounts list"""
        self.gui.create_chat_page()
        self.root.update()
        test_accounts = [
            (1, "user1"),
            (2, "user2"),
            (3, "user3")
        ]
        self.gui.update_accounts_list(test_accounts)
        self.assertEqual(self.gui.accounts_listbox.size(), 3)
        self.assertEqual(self.gui.accounts_listbox.get(0), "user1")
        self.assertEqual(self.gui.accounts_listbox.get(1), "user2")
        self.assertEqual(self.gui.accounts_listbox.get(2), "user3")

    def test_update_messages_list(self):
        """Test updating messages list"""
        self.gui.create_chat_page()
        self.root.update()
        self.gui.username = "testuser"
        test_messages = [
            (1, "sender1", "testuser", "Hello", "2024-01-01"),
            (2, "testuser", "recipient1", "Hi", "2024-01-01")
        ]
        self.gui.update_messages_list(test_messages, 1)
        self.assertEqual(self.gui.messages_listbox.size(), 2)
        self.assertEqual(self.gui.messages_listbox.get(0), "From sender1: Hello")
        self.assertEqual(self.gui.messages_listbox.get(1), "To recipient1: Hi")

    @patch('threading.Thread')
    def test_thread_send(self, mock_thread):
        """Test thread sending function"""
        request = {"action": "test"}
        self.gui.thread_send(request)
        mock_thread.assert_called_once()

# test_load_page_data

# test_search_accounts

# test_delete_messages

# test_load_undelivered_messages

# test_load_messages

    def test_send_message(self):
        """Test message sending functionality"""
        self.gui.create_chat_page()
        self.root.update()
        self.gui.username = "testuser"
        self.gui.selected_account = "recipient"
        self.gui.entry.insert(0, "Hello!")
        
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "2024-01-01 12:00:00"
            self.gui.send_message()
            
            expected_request = {
                "action": "send_message",
                "content": {
                    "uuid": self.gui.user_uuid,
                    "recipient_username": "recipient",
                    "message": "Hello!",
                    "timestamp": "2024-01-01 12:00:00"
                }
            }
            self.send_to_server.assert_called_with(expected_request)

    def test_login_register(self):
        """Test login/register functionality"""
        self.gui.username_entry.insert(0, "testuser")
        self.gui.password_entry.insert(0, "testpass")
        self.gui.login()
        
        expected_password_hash = self.gui.hash_password("testpass")
        expected_request = {
            "action": "login",
            "content": {
                "username": "testuser",
                "password": expected_password_hash
            }
        }
        
        # Verify that either network_thread or send_to_server was called
        if self.network_thread.call_count > 0:
            self.network_thread.assert_called_with(expected_request)
        else:
            self.send_to_server.assert_called_with(expected_request)

    def test_delete_account(self):
        """Test account deletion"""
        self.gui.create_confirm_delete_account_page()
        self.root.update()
        self.gui.user_uuid = "test-uuid"
        self.gui.dialog_password_entry.insert(0, "password")
        self.gui.delete_account()
        expected_request = {
            "action": "delete_account",
            "content": {
                "uuid": "test-uuid",
                "password": self.gui.hash_password("password")
            }
        }
        self.send_to_server.assert_called_with(expected_request)

    def test_handle_server_response_delete_account_r(self):
        """Test handling delete account response"""
        self.gui.create_confirm_delete_account_page()
        self.root.update()
        response = {"success": True}
        with patch('tkinter.messagebox.showerror') as mock_error, \
             patch('tkinter.messagebox.showinfo') as mock_info:
            self.gui.handle_server_response(response, "delete_account_r")
            mock_error.assert_not_called()
            mock_info.assert_called_once_with("Account deleted", "Your account was successfully deleted")
            # After successful deletion, dialog should be None
            self.assertIsNone(self.gui.dialog)

    def test_handle_server_response_login_register_r(self):
        """Test handling server login response"""
        response = {"uuid": "test-uuid"}
        self.gui.handle_server_response(response, "login_r")
        self.assertEqual(self.gui.user_uuid, "test-uuid")

    def test_handle_server_response_load_page_data_r(self):
        """Test handling server load page response"""
        self.gui.create_chat_page()
        self.root.update()
        response = {
            "accounts": [(1, "user1")],
            "messages": [(1, "sender1", "recipient1", "Hello", "2024-01-01")],
            "num_pending": 1,
            "total_count": 1
        }
        with patch.object(self.gui, 'update_accounts_list') as mock_update_accounts, \
             patch.object(self.gui, 'update_messages_list') as mock_update_messages:
            self.gui.handle_server_response(response, "load_page_data_r")
            self.assertEqual(self.gui.num_undelivered, 1)
            self.assertEqual(self.gui.max_accounts_page, 0)
            mock_update_accounts.assert_called_with(response["accounts"])
            mock_update_messages.assert_called_with(response["messages"], response["num_pending"])

    def test_handle_server_response_refresh_accounts_r(self):
        """Test handling refresh accounts response"""
        with patch.object(self.gui, 'search_accounts') as mock_search:
            self.gui.handle_server_response({}, "refresh_accounts_r")
            mock_search.assert_called_once()

    def test_handle_server_response_search_accounts_r(self):
        """Test handling search accounts response"""
        self.gui.create_chat_page()
        self.root.update()
        response = {"accounts": [(1, "user1")], "total_count": 1}
        with patch.object(self.gui, 'update_accounts_list') as mock_update:
            self.gui.handle_server_response(response, "search_accounts_r")
            mock_update.assert_called_with([(1, "user1")])

    def test_handle_server_response_receive_message_r(self):
        """Test handling receive message response"""
        self.gui.create_chat_page()
        self.root.update()
        with patch.object(self.gui, 'load_messages') as mock_load:
            self.gui.handle_server_response({}, "receive_message_r")
            mock_load.assert_called_once()

    def test_handle_server_response_send_message_r(self):
        """Test handling send message response"""
        with patch.object(self.gui, 'load_messages') as mock_load:
            self.gui.handle_server_response({}, "send_message_r")
            mock_load.assert_called_once()

    def test_handle_server_response_delete_message_r(self):
        """Test handling delete message response"""
        self.gui.create_chat_page()
        self.root.update()
        with patch.object(self.gui, 'load_messages') as mock_load:
            response = {"success": True, "total_count": 1}
            self.gui.handle_server_response(response, "delete_messages_r")
            mock_load.assert_called_once()

    def test_handle_server_response_load_messages_r(self):
        """Test handling load messages response"""
        response = {"messages": [(1, "user1", "user2", "hello", "2024-01-01")]}
        with patch.object(self.gui, 'update_messages_list') as mock_update:
            self.gui.handle_server_response(response, "load_messages_r")
            mock_update.assert_called_with(response["messages"], self.gui.num_undelivered)

    def test_handle_server_response_load_undelivered_r(self):
        """Test handling load undelivered messages response"""
        response = {"messages": [(1, "user1", "user2", "hello", "2024-01-01")]}
        self.gui.create_chat_page()
        self.root.update()
        self.gui.handle_server_response(response, "load_undelivered_r")

    def test_handle_server_response_login_error(self):
        """Test handling login error response"""
        response = {"message": "Invalid credentials"}
        with patch.object(self.gui, 'create_error_page') as mock_error:
            self.gui.handle_server_response(response, "login_error")
            mock_error.assert_called_with(response["message"])

    def test_handle_server_response_error(self):
        """Test handling general error response"""
        response = {"error": "General error"}
        with patch('tkinter.messagebox.showerror') as mock_error:
            self.gui.handle_server_response(response, "error")
            mock_error.assert_called_with("Error", "General error", icon='warning')

    def test_load_page_data(self):
        """Test loading page data"""
        self.gui.user_uuid = "test-uuid"
        self.gui.load_page_data()
        expected_request = {
            "action": "load_page_data",
            "content": {"uuid": "test-uuid"}
        }
        self.send_to_server.assert_called_with(expected_request)

    def test_search_accounts(self):
        """Test account search"""
        self.gui.create_chat_page()  # Initialize required widgets
        self.gui.search_bar.insert(0, "test")
        self.gui.current_page = 0
        self.gui.search_accounts()
        expected_request = {
            "action": "search_accounts",
            "content": {"search_term": "test", "offset": 0}
        }
        self.send_to_server.assert_called_with(expected_request)

    def test_delete_messages(self):
        """Test message deletion"""
        self.gui.create_chat_page()  # Initialize required widgets
        self.root.update()
        self.gui.msgid_map = {0: "msg1", 1: "msg2"}
        self.gui.messages_listbox.curselection = MagicMock(return_value=[0])
        self.gui.delete_messages()
        expected_request = {
            "action": "delete_messages",
            "content": {"msgids": ["msg1"], "deleter_uuid": None}
        }
        self.send_to_server.assert_called_with(expected_request)

    def test_load_undelivered_messages(self):
        """Test loading undelivered messages"""
        self.gui.create_chat_page()  # Initialize required widgets
        self.gui.user_uuid = "test-uuid"
        self.gui.num_undelivered = 5
        self.gui.num_messages_entry.insert(0, "3")
        self.gui.load_undelivered_messages()
        expected_request = {
            "action": "load_undelivered",
            "content": {"num_messages": 3, "uuid": "test-uuid"}
        }
        self.send_to_server.assert_called_with(expected_request)

    def test_load_messages(self):
        """Test loading messages"""
        self.gui.user_uuid = "test-uuid"
        self.gui.num_messages = 5
        self.gui.load_messages()
        expected_request = {
            "action": "load_messages",
            "content": {"num_messages": 5, "uuid": "test-uuid"}
        }
        self.send_to_server.assert_called_with(expected_request)

if __name__ == '__main__':
    unittest.main()
