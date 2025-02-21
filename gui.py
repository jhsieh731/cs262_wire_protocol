import datetime
import hashlib
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox
from logger import set_logger
import chat_pb2

logger = set_logger("gui", "gui.log")

# GUI Setup
class ClientGUI:
    def __init__(self, master, client):
        self.master = master
        self.master.title("Chat Application")
        self.client = client
        self.client.set_update_callback(self.handle_server_update)
        
        self.user_uuid = None
        self.selected_account = None
        self.username = ""
        self.current_page = 0
        self.max_accounts_page = 0
        self.num_messages = 10
        self.num_undelivered = 0
        self.msgid_map = {}

        self.login_frame = tk.Frame(master)
        self.chat_frame = tk.Frame(master)
        self.create_account_frame = tk.Frame(master)
        self.register_frame = tk.Frame(master)
        self.error_frame = tk.Frame(master)
        self.is_threading = False
        self.duplicated_password = False

        self.create_login_page()

    def clear_frame(self, frame):
        for widget in frame.winfo_children():
            widget.destroy()
        frame.pack_forget()
    
    # ===================================================================
    # ===================================================================
    # GUI PAGES
    # ===================================================================
    # ===================================================================

    def create_error_page(self, error_message):
        self.clear_frame(self.login_frame)
        self.clear_frame(self.chat_frame)
        self.clear_frame(self.create_account_frame)
        self.clear_frame(self.register_frame)
        self.error_frame.pack()

        self.error_label = tk.Label(self.error_frame, text="Error", fg="red", font=("Helvetica", 16))
        self.error_label.pack(padx=10, pady=10)

        self.error_message_label = tk.Label(self.error_frame, text=error_message, wraplength=400)
        self.error_message_label.pack(padx=10, pady=10)

        self.back_button = tk.Button(self.error_frame, text="Back", command=self.create_login_page)
        self.back_button.pack(padx=10, pady=10)

    def create_account_page(self):
        self.clear_frame(self.chat_frame)
        self.clear_frame(self.login_frame)
        self.clear_frame(self.error_frame)
        self.clear_frame(self.register_frame)

        self.create_account_frame.pack()

        self.create_account_label = tk.Label(self.create_account_frame, text="Create Account", font=("Helvetica", 16))
        self.create_account_label.pack(padx=10, pady=10)

        self.username_label = tk.Label(self.create_account_frame, text="Username:")
        self.username_label.pack(padx=10, pady=5)
        self.username_entry = tk.Entry(self.create_account_frame)
        self.username_entry.pack(padx=10, pady=5)


        self.create_button = tk.Button(self.create_account_frame, text="Check Username", command=self.check_username)
        self.create_button.pack(padx=10, pady=5)

        self.back_button = tk.Button(self.create_account_frame, text="Back", command=self.create_login_page)
        self.back_button.pack(padx=10, pady=5)

    def create_register_page(self):
        self.clear_frame(self.chat_frame)
        self.clear_frame(self.login_frame)
        self.clear_frame(self.error_frame)
        self.clear_frame(self.create_account_frame)

        self.register_frame.pack()

        self.create_account_label = tk.Label(self.register_frame, text="Create Account", font=("Helvetica", 16))
        self.create_account_label.pack(padx=10, pady=10)

        self.register_username_label = tk.Label(self.register_frame, text="Username:")
        self.register_username_label.pack(padx=10, pady=5)
        self.register_username_entry = tk.Entry(self.register_frame)
        self.register_username_entry.pack(padx=10, pady=5)
        # self.register_username_entry.config(state=tk.DISABLED)

        self.register_password_label = tk.Label(self.register_frame, text="Password:")
        self.register_password_label.pack(padx=10, pady=5)
        self.register_password_entry = tk.Entry(self.register_frame, show="*")
        self.register_password_entry.pack(padx=10, pady=5)


        self.register_button = tk.Button(self.register_frame, text="Register", command=self.register)
        self.register_button.pack(padx=10, pady=5)

        self.back_button = tk.Button(self.register_frame, text="Back", command=self.create_login_page)
        self.back_button.pack(padx=10, pady=5)

    def create_login_page(self):
        self.clear_frame(self.chat_frame)
        self.clear_frame(self.error_frame)
        self.clear_frame(self.create_account_frame)
        self.clear_frame(self.register_frame)

        self.login_frame.pack()

        self.username_label = tk.Label(self.login_frame, text="Username:")
        self.username_label.pack(padx=10, pady=5)
        self.username_entry = tk.Entry(self.login_frame)
        self.username_entry.pack(padx=10, pady=5)

        self.password_label = tk.Label(self.login_frame, text="Password:")
        self.password_label.pack(padx=10, pady=5)
        self.password_entry = tk.Entry(self.login_frame, show="*")
        self.password_entry.pack(padx=10, pady=5)

        self.login_button = tk.Button(self.login_frame, text="Login", command=self.login)
        self.login_button.pack(padx=10, pady=5)

        # add a line and a "don't have an account? create one" button
        self.line = tk.Label(self.login_frame, text="-------------------")
        self.line.pack(padx=10, pady=5)
        self.add_account_label = tk.Label(self.login_frame, text="Don't have an account?")
        self.add_account_label.pack(padx=10, pady=5)

        self.create_account_button = tk.Button(self.login_frame, text="Create Account", command=self.create_account_page)
        self.create_account_button.pack(padx=10, pady=5)

    def create_chat_page(self):
        """Create the main chat page."""
        self.clear_frame(self.login_frame)
        self.clear_frame(self.register_frame)
        self.clear_frame(self.error_frame)
        self.chat_frame.pack(fill=tk.BOTH, expand=True)

        # Configure grid weights for the main chat frame
        self.chat_frame.grid_columnconfigure(0, weight=1)  # Messages list
        self.chat_frame.grid_columnconfigure(1, weight=1)  # Accounts list
        self.chat_frame.grid_columnconfigure(2, weight=1)  # Message display
        self.chat_frame.grid_rowconfigure(0, weight=1)

        # Left column - Messages list
        messages_frame = tk.Frame(self.chat_frame)
        messages_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Messages header
        self.messages_label = tk.Label(messages_frame, text=f"{self.username}'s messages")
        self.messages_label.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        # Undelivered messages section
        self.undelivered_label = tk.Label(messages_frame, text="No undelivered messages")
        self.undelivered_label.grid(row=1, column=0, sticky="w", padx=5)
        
        undelivered_frame = tk.Frame(messages_frame)
        undelivered_frame.grid(row=2, column=0, sticky="w", padx=5, pady=2)
        
        tk.Label(undelivered_frame, text="See").pack(side=tk.LEFT)
        self.num_messages_entry = tk.Entry(undelivered_frame, width=5)
        self.num_messages_entry.pack(side=tk.LEFT, padx=2)
        tk.Label(undelivered_frame, text="undelivered messages").pack(side=tk.LEFT)
        self.go_button = tk.Button(undelivered_frame, text="Go", command=self.load_undelivered_messages)
        self.go_button.pack(side=tk.LEFT, padx=2)
        
        # Messages list with scrollbar
        messages_frame.grid_columnconfigure(0, weight=1)
        messages_frame.grid_rowconfigure(3, weight=1)
        
        self.messages_listbox = tk.Listbox(
            messages_frame,
            selectmode=tk.EXTENDED,
            exportselection=0
        )
        self.messages_listbox.grid(row=3, column=0, sticky="nsew", padx=5, pady=5)
        
        messages_scroll = tk.Scrollbar(messages_frame, command=self.messages_listbox.yview)
        messages_scroll.grid(row=3, column=1, sticky="ns")
        self.messages_listbox.config(yscrollcommand=messages_scroll.set)
        
        # Messages buttons
        button_frame = tk.Frame(messages_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=5)
        
        tk.Button(button_frame, text="Load more", command=self.load_more_messages).pack(side=tk.LEFT, padx=2)
        tk.Button(button_frame, text="Delete messages", command=self.delete_messages).pack(side=tk.LEFT, padx=2)

        # Middle column - Accounts list
        accounts_frame = tk.Frame(self.chat_frame)
        accounts_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        accounts_frame.grid_columnconfigure(0, weight=1)
        accounts_frame.grid_rowconfigure(2, weight=1)
        
        # Search bar
        search_frame = tk.Frame(accounts_frame)
        search_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=5)
        
        self.search_bar = tk.Entry(search_frame)
        self.search_bar.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        tk.Button(search_frame, text="Search", command=self.search_accounts).pack(side=tk.LEFT)
        
        # Delete account button
        tk.Button(accounts_frame, text="Delete my account", command=self.create_confirm_delete_account_page, 
                 fg="red").grid(row=1, column=0, pady=5)
        
        # Accounts list with scrollbar
        self.accounts_listbox = tk.Listbox(accounts_frame, exportselection=0)
        self.accounts_listbox.grid(row=2, column=0, sticky="nsew", padx=5)
        self.accounts_listbox.bind('<<ListboxSelect>>', self.on_account_select)
        
        accounts_scroll = tk.Scrollbar(accounts_frame, command=self.accounts_listbox.yview)
        accounts_scroll.grid(row=2, column=1, sticky="ns")
        self.accounts_listbox.config(yscrollcommand=accounts_scroll.set)
        
        # Pagination
        pagination_frame = tk.Frame(accounts_frame)
        pagination_frame.grid(row=3, column=0, columnspan=2, pady=5)
        
        self.prev_button = tk.Button(pagination_frame, text="Prev", command=self.prev_page)
        self.prev_button.pack(side=tk.LEFT, padx=2)
        self.next_button = tk.Button(pagination_frame, text="Next", command=self.next_page)
        self.next_button.pack(side=tk.LEFT, padx=2)

        # Right column - Message display and input
        chat_frame = tk.Frame(self.chat_frame)
        chat_frame.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)
        chat_frame.grid_columnconfigure(0, weight=1)
        chat_frame.grid_rowconfigure(0, weight=1)
        
        self.message_display = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD)
        self.message_display.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 5))
        self.message_display.config(state=tk.DISABLED)
        
        self.entry = tk.Entry(chat_frame)
        self.entry.grid(row=1, column=0, sticky="ew", padx=(0, 5))
        
        tk.Button(chat_frame, text="Send", command=self.send_message).grid(row=1, column=1)

        # Load initial data
        self.load_page_data()
    
    def create_confirm_delete_account_page(self):
        # Create a dialog window
        self.dialog = tk.Toplevel(self.master)
        self.dialog.title("Confirm Account Deletion")
        self.dialog.geometry("300x250")  # Increased height
        self.dialog.transient(self.master)  # Make dialog modal
        self.dialog.grab_set()  # Make the dialog modal

        # Add warning message
        warning_label = tk.Label(self.dialog, text="Are you sure you want to delete your account?\nThis action cannot be undone.", wraplength=250)
        warning_label.pack(padx=10, pady=10)

        # Password entry
        password_label = tk.Label(self.dialog, text="Enter your password to confirm:")
        password_label.pack(padx=10, pady=5)
        self.dialog_password_entry = tk.Entry(self.dialog, show="*")
        self.dialog_password_entry.pack(padx=10, pady=5)

        # Buttons
        delete_button = tk.Button(self.dialog, text="Delete account", command=self.delete_account, fg="red")
        delete_button.pack(pady=10)
        
        cancel_button = tk.Button(self.dialog, text="Cancel", command=self.dialog.destroy)
        cancel_button.pack(pady=5)

    # ===================================================================
    # ===================================================================
    # Helper/User event functions
    # ===================================================================
    # ===================================================================

    def hash_password(self, password):
        """Hash password using SHA-256."""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.search_accounts()

    def next_page(self):
        if self.current_page < self.max_accounts_page:
            self.current_page += 1
            self.search_accounts()

    def on_account_select(self, event):
        selection = event.widget.curselection()
        if selection:
            index = selection[0]
            self.selected_account = event.widget.get(index)
            self.update_message_input_area()
    
    def load_more_messages(self):
        self.num_messages += 10
        self.load_messages()


    def update_message_input_area(self):
        """Update the message input area with the current chat."""
        if not self.selected_account:
            return
            
        response = self.client.load_private_chat(self.user_uuid, self.selected_account)
        self.message_display.config(state=tk.NORMAL)
        self.message_display.delete("1.0", tk.END)
        
        # Add header
        self.message_display.insert(tk.END, f"Your chat with {self.selected_account}\n\n\n")
        
        # Add messages
        for msg in response.messages:
            if msg.status == chat_pb2.MessageStatus.PENDING and msg.recipient_username == self.username:
                continue
            self.message_display.insert(
                tk.END, 
                f"[{msg.timestamp}] {msg.sender_username}: {msg.message}\n"
            )
        
        self.message_display.config(state=tk.DISABLED)
        self.message_display.see(tk.END)

    def update_accounts_list(self, accounts):
        self.accounts_listbox.delete(0, tk.END)
        for account in accounts:
            # Display username in the listbox
            self.accounts_listbox.insert(tk.END, account[1])

    def update_messages_list(self, messages, total_undelivered):
        """Update the messages listbox with the given messages."""
        self.messages_listbox.delete(0, tk.END)
        self.msgid_map.clear()
        
        for i, msg in enumerate(messages):
            msg_id = msg[0] if isinstance(msg, (list, tuple)) else msg.message_id
            sender = msg[1] if isinstance(msg, (list, tuple)) else msg.sender_username
            recipient = msg[2] if isinstance(msg, (list, tuple)) else msg.recipient_username
            message = msg[3] if isinstance(msg, (list, tuple)) else msg.message
            timestamp = msg[4] if isinstance(msg, (list, tuple)) else msg.timestamp
            
            display_text = f"[{timestamp}] {sender} -> {recipient}: {message}"
            self.messages_listbox.insert(tk.END, display_text)
            self.msgid_map[i] = msg_id
        
        # Update undelivered count
        self.num_undelivered = total_undelivered
        if total_undelivered > 0:
            self.undelivered_label.config(
                text=f"You have {total_undelivered} undelivered messages"
            )
            self.go_button.config(state=tk.NORMAL)
            self.num_messages_entry.config(state=tk.NORMAL)
        else:
            self.undelivered_label.config(text="No undelivered messages")
            self.go_button.config(state=tk.DISABLED)
            self.num_messages_entry.config(state=tk.DISABLED)

    
    # ===================================================================
    # ===================================================================
    # Network functions (send requests to server)
    # ===================================================================
    # ===================================================================

    def check_username(self):
        logger.info(f"F {self.username}: Check username")
        username = self.username_entry.get()
        if username:
            response = self.client.check_username(username)
            if response.is_available:
                self.create_register_page()
                self.register_username_entry.insert(0, username)
                self.register_username_entry.config(state=tk.DISABLED)
            else:
                self.create_login_page()
                self.username_entry.insert(0, username)

    def register(self):
        logger.info(f"F {self.username}: Register")
        username = self.register_username_entry.get()
        password = self.register_password_entry.get()
        if username and password:
            response = self.client.register(username, self.hash_password(password))
            if response.success:
                self.username = username
                self.user_uuid = response.uuid
                self.client.start_update_stream(self.user_uuid)
                self.create_chat_page()
                self.master.after(500, self.search_accounts)
            else:
                self.create_error_page(response.error)

    def load_page_data(self):
        """Load initial page data."""
        try:
            # Load messages
            messages_response = self.client.load_messages(self.user_uuid, self.num_messages)
            
            # Convert messages to the format expected by update_messages_list
            messages = [
                [msg.message_id, msg.sender_username, msg.recipient_username, 
                 msg.message, msg.timestamp, msg.status]
                for msg in messages_response.messages
            ]
            
            # Load accounts
            accounts_response = self.client.search_accounts("", 0)
            accounts = [
                (acc.uuid, acc.username)
                for acc in accounts_response.accounts
                if acc.username != self.username
            ]
            
            # Update the GUI
            self.update_messages_list(messages, messages_response.total_undelivered)
            self.update_accounts_list(accounts)
            
            # Update pagination
            self.max_accounts_page = (accounts_response.total_count // 10)
            self.prev_button["state"] = tk.NORMAL if self.current_page > 0 else tk.DISABLED
            self.next_button["state"] = tk.NORMAL if self.current_page < self.max_accounts_page else tk.DISABLED
            
        except Exception as e:
            logger.error(f"Error loading page data: {e}")
            messagebox.showerror("Error", f"Failed to load page data: {e}")

    def search_accounts(self):
        logger.info(f"F {self.username}: Searching accounts")
        search_term = self.search_bar.get().lower()
        response = self.client.search_accounts(search_term, self.current_page * 10)
        
        accounts = [(acc.uuid, acc.username) for acc in response.accounts 
                   if acc.username != self.username]
        total_count = response.total_count
        
        self.update_accounts_list(accounts)
        self.max_accounts_page = (total_count // 10)
        self.prev_button["state"] = tk.NORMAL if self.current_page > 0 else tk.DISABLED
        self.next_button["state"] = tk.NORMAL if self.current_page < self.max_accounts_page else tk.DISABLED

    def delete_messages(self):
        logger.info(f"F {self.username}: Delete messages")
        selected_indices = self.messages_listbox.curselection()
        message_ids = [self.msgid_map[i] for i in selected_indices if i in self.msgid_map]
        if message_ids:
            response = self.client.delete_messages(message_ids, self.user_uuid)
            if response.success:
                self.num_messages -= response.total_deleted
                self.load_messages()
                self.master.after(500, self.update_message_input_area)

    def load_undelivered_messages(self):
        logger.info(f"F {self.username}: Load undelivered messages")
        num_messages = int(self.num_messages_entry.get())
        if num_messages < 1 or num_messages > self.num_undelivered:
            messagebox.showwarning(
                "Invalid Input", 
                f"Please enter a number between 1 and {self.num_undelivered}"
            )
            return

        response = self.client.load_undelivered_messages(self.user_uuid, num_messages)
        self.num_undelivered -= len(response.messages)
        self.num_messages += len(response.messages)
        self.load_messages()
        self.master.after(500, self.update_message_input_area)

    def load_messages(self):
        logger.info(f"F {self.username}: Load messages")
        num_messages = self.num_messages
        logger.info(f"Loading {num_messages} messages")
        response = self.client.load_messages(self.user_uuid, num_messages)
        messages = [
            [msg.message_id, msg.sender_username, msg.recipient_username, 
             msg.message, msg.timestamp]
            for msg in response.messages
        ]
        self.update_messages_list(messages, response.total_undelivered)

    def send_message(self):
        logger.info(f"F {self.username}: Send message")
        msg = self.entry.get()
        if msg and self.selected_account:
            logger.info(f"Selected account: {self.selected_account}, Message: {msg}")
            self.entry.delete(0, tk.END)
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            response = self.client.send_message(
                self.user_uuid,
                self.selected_account,
                msg,
                timestamp
            )
            if response.success:
                self.num_messages += 1
                self.load_messages()
                self.master.after(500, self.update_message_input_area)
            else:
                messagebox.showerror("Error", response.error)

    def login(self):
        logger.info(f"F {self.username}: Login")
        username = self.username_entry.get()
        password = self.password_entry.get()
        if username and password:
            response = self.client.login(username, self.hash_password(password))
            if response.success:
                self.username = username
                self.user_uuid = response.uuid
                self.client.start_update_stream(self.user_uuid)
                self.create_chat_page()
            else:
                self.create_error_page(response.error)

    def delete_account(self):
        logger.info(f"F {self.username}: Delete account")
        password = self.dialog_password_entry.get()
        response = self.client.delete_account(self.user_uuid, self.hash_password(password))
        if response.success:
            self.dialog.destroy()
            messagebox.showinfo("Success", "Account deleted successfully")
            self.master.quit()
        else:
            messagebox.showerror("Error", response.error)

    def handle_server_update(self, update):
        """Handle real-time updates from server."""
        # def handle_on_main_thread():
        print(f"Received update: {update}")
        if update.HasField('new_message'):
            msg = update.new_message
            self.handle_new_message(msg)
        elif update.HasField('account_update'):
            self.handle_account_update(update.account_update)
        elif update.HasField('message_deletion'):
            self.handle_message_deletion(update.message_deletion)

        # # Schedule update handling on the main thread
        # self.master.after(0, handle_on_main_thread)

    def handle_new_message(self, message):
        """Handle new message update."""
        if (message.sender_username == self.selected_account or 
            message.recipient_username == self.selected_account):
            # Update the private chat view if we're currently viewing it
            self.update_message_input_area()
        
        # Always update the messages list
        self.num_messages += 1
        self.load_messages()

    def handle_account_update(self, update):
        """Handle account update."""
        self.search_accounts()

    def handle_message_deletion(self, deletion):
        """Handle message deletion update."""
        self.num_messages -= deletion.total_count
        self.load_messages()
        self.update_message_input_area()

    def load_private_chat(self):
        if not self.selected_account:
            return
            
        response = self.client.load_private_chat(self.user_uuid, self.selected_account)
        self.message_display.config(state=tk.NORMAL)
        self.message_display.delete("3.0", tk.END)
        
        for msg in response.messages:
            if msg.status == chat_pb2.MessageStatus.PENDING and msg.recipient_username == self.username:
                continue
            self.message_display.insert(
                tk.END, 
                f"[{msg.timestamp}] {msg.sender_username}: {msg.message}\n"
            )
        
        self.message_display.config(state=tk.DISABLED)
        self.message_display.see(tk.END)

    # ===================================================================
    # ===================================================================
    # Server response handling
    # ===================================================================
    # ===================================================================
    def handle_server_response(self, response, response_type):
        # response_type = response["response_type"]
        logger.info(f"Action: {response_type}, Response: {response}")
        
        if response_type == "delete_account_r":
            if response["success"]:
                self.dialog.destroy()
                self.dialog = None
                messagebox.showinfo("Account deleted", "Your account was successfully deleted")
                
                # Only quit if we're not in a test environment
                import sys
                if not any('unittest' in arg for arg in sys.argv):
                    self.master.quit()
                    self.master.destroy()
            else:
                messagebox.showerror("Error", response["error"])

        elif response_type == "login_r":
            self.user_uuid = response.get("uuid", None)
            self.create_chat_page()

        elif response_type == "load_page_data_r":
            accounts = response.get("accounts", [])
            accounts = [acc for acc in accounts if acc[1] != self.username]
            messages = response.get("messages", [])
            total_undelivered = response.get("num_pending", 0)
            total_count = response.get("total_count", 0)
            
            self.num_messages = len(messages)
            self.num_undelivered = total_undelivered
            
            # Update pagination state. Start index from 0
            self.max_accounts_page = (total_count // 10)
            
            # Enable/disable pagination buttons
            self.prev_button["state"] = tk.NORMAL if self.current_page > 0 else tk.DISABLED
            self.next_button["state"] = tk.NORMAL if self.current_page < self.max_accounts_page else tk.DISABLED


            self.update_accounts_list(accounts)
            self.update_messages_list(messages, total_undelivered)

        elif response_type == "refresh_accounts_r":
            # Server notified us to refresh the accounts list
            self.search_accounts()

        elif response_type == "search_accounts_r":
            accounts = response.get("accounts", [])
            total_count = response.get("total_count", 0)
            logger.info(f"Received {len(accounts)} accounts (total: {total_count}) accounts: {accounts}")
            accounts = [acc for acc in accounts if acc[1] != self.username]
            logger.info(f"Accounts without self: {accounts}")
            
            # Update the accounts list
            self.update_accounts_list(accounts)
            
            # Update pagination state. Start index from 0
            self.max_accounts_page = (total_count // 10)
            
            # Enable/disable pagination buttons
            self.prev_button["state"] = tk.NORMAL if self.current_page > 0 else tk.DISABLED
            self.next_button["state"] = tk.NORMAL if self.current_page < self.max_accounts_page else tk.DISABLED
            
        elif response_type == "receive_message_r":            
            sender = response.get("sender_username", "Unknown")
            message = response.get("message", "")
            logger.info(f"{self.username} received message from {sender}: {message}")
            self.num_messages += 1

            # update the messagelist box
            self.master.after(500, self.load_messages())
            if sender == self.selected_account:
                self.master.after(1000, self.update_message_input_area)
        
        elif response_type == "send_message_r":
            logger.info(f"send message status: {response.get('status', 'error')}")
            success = response.get("success", "error")
            if success:
                logger.info("Message sent successfully")
                self.num_messages += 1
                self.load_messages()
                self.master.after(500, self.update_message_input_area)

        elif response_type == "delete_messages_r":
            logger.info("Messages deleted successfully")
            num_deleted = response.get("total_count", 0)
            self.num_messages -= num_deleted
            self.load_messages()
            self.master.after(500, self.update_message_input_area)
        
        elif response_type == "load_messages_r":
            messages = response.get("messages", [])
            total_undelivered = response.get("total_count", 0)
            self.num_messages = len(messages)
            self.num_undelivered = total_undelivered
            logger.info(f"Received {len(messages)} messages")
            self.update_messages_list(messages, total_undelivered)

        elif response_type == "load_undelivered_r":
            messages = response.get("messages", [])
            self.num_undelivered -= len(messages)
            self.num_messages += len(messages)
            logger.info(f"Received {len(messages)} undelivered messages")
            self.load_messages()
            self.master.after(500, self.update_message_input_area)

        elif response_type == "login_error":
            logger.error(f"Error: {response.get('message', 'An error occurred')}")
            self.create_error_page(response.get("message", "An error occurred"))

        elif response_type == "check_username_r":
            is_in_use = response.get("message", True)
            entered_username = self.username_entry.get()
            if is_in_use:
                self.create_login_page()
                # set username to the entry
                self.username_entry.insert(0, entered_username)

            else:
                self.create_register_page()
                self.register_username_entry.insert(0, entered_username)
                # disable it
                self.register_username_entry.config(state=tk.DISABLED)

        elif response_type == "register_r":
            if response.get("error", None):
                self.create_error_page(response.get("error", "An error occurred"))
            else:
                self.username = self.register_username_entry.get()
                self.user_uuid = response.get("uuid", None)
                self.create_chat_page()
                logger.info(f"Registered user: {self.username} with UUID: {self.user_uuid} and refreshing search_accounts")
                # Create chat page first, then search accounts after a delay
                self.master.after(500, self.search_accounts)

        elif response_type == "delete_account_refresh_r":
            if response["success"]:
                self.selected_account = None
                num_deleted = response.get("total_count", 0)
                self.num_messages -= num_deleted
                self.load_messages()
                logger.info("Loaded messages after deleting account")
                # Search accounts after messages are loaded
                self.master.after(500, self.search_accounts)
                self.master.after(500, self.update_message_input_area)

        elif response_type == "load_private_chat_r":
            messages = response.get("messages", [])
            self.message_display.config(state=tk.NORMAL)
            
            # Clear everything after the header
            header_end = "3.0"  # After "Your chat with username\n\n\n"
            self.message_display.delete(header_end, tk.END)
            
            # Display messages
            for msg in messages:
                if msg["status"] == "pending" and msg["recipient_username"] == self.username:
                    logger.info(f"Skipping pending message from {msg['sender_username']}: {msg['message']}")
                    continue
                timestamp = msg["timestamp"]
                sender = msg["sender_username"]
                message = msg["message"]
                
                # Format: [timestamp] sender: message
                self.message_display.insert(tk.END, f"[{timestamp}] {sender}: {message}\n")
            
            self.message_display.config(state=tk.DISABLED)
            # Scroll to bottom
            self.message_display.see(tk.END)
            
        elif response_type == "error": # Handle error response
            logger.error(f"Error: {response.get('error', 'An error occurred')}")
            messagebox.showerror("Error", response.get("error", "An error occurred"), icon="warning")
    