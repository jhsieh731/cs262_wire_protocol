import datetime
import hashlib
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox
from logger import set_logger

logger = set_logger("gui", "gui.log")

# GUI Setup
class ClientGUI:
    def __init__(self, master, send_to_server, network_thread):
        self.master = master
        self.master.title("Client Application")
        self.send_to_server = send_to_server
        self.network_thread = network_thread

        self.user_uuid = None
        self.selected_accounts = None
        self.username = ""
        self.current_page = 0
        self.max_accounts_page = 0
        self.num_messages = 10
        self.num_undelivered = 0
        self.msgid_map = {}  # Dictionary to map listbox indices to msgid

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
        self.clear_frame(self.login_frame)
        self.clear_frame(self.error_frame)
        self.clear_frame(self.create_account_frame)
        self.clear_frame(self.register_frame)
        self.chat_frame.pack(fill=tk.BOTH, expand=True)

        # First column: Accounts list with search bar and pagination
        self.accounts_frame = tk.Frame(self.chat_frame)
        self.accounts_frame.grid(row=0, column=0, sticky="nsew")

        search_frame = tk.Frame(self.accounts_frame)
        search_frame.pack(padx=10, pady=5)
        
        self.search_bar = tk.Entry(search_frame)
        self.search_bar.pack(side=tk.LEFT, padx=(0, 5))
        
        self.search_button = tk.Button(search_frame, text="Search", command=self.search_accounts)
        self.search_button.pack(side=tk.LEFT)

        # Delete Account Button
        account_buttons_frame = tk.Frame(self.accounts_frame)
        account_buttons_frame.pack(pady=5)
        
        self.delete_account_button = tk.Button(account_buttons_frame, text="Delete my account", command=self.create_confirm_delete_account_page, fg="red")
        self.delete_account_button.pack(side=tk.LEFT, padx=5)

        self.accounts_listbox = tk.Listbox(self.accounts_frame)
        self.accounts_listbox.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        self.accounts_listbox.bind('<<ListboxSelect>>', self.on_account_select)

        self.pagination_frame = tk.Frame(self.accounts_frame)
        self.pagination_frame.pack(padx=10, pady=5)

        self.prev_button = tk.Button(self.pagination_frame, text="Prev", command=self.prev_page)
        self.prev_button.pack(side=tk.LEFT, padx=5)
        self.next_button = tk.Button(self.pagination_frame, text="Next", command=self.next_page)
        self.next_button.pack(side=tk.LEFT, padx=5)

        # Second column: Messages list with options
        self.messages_frame = tk.Frame(self.chat_frame)
        self.messages_frame.grid(row=0, column=1, sticky="nsew")

        self.messages_label = tk.Label(self.messages_frame, text=self.username + "'s messages")
        self.messages_label.pack(padx=10, pady=5)

        self.undelivered_label = tk.Label(self.messages_frame, text="Undelivered messages: 0")
        self.undelivered_label.pack(padx=10, pady=5)

        undelivered_frame = tk.Frame(self.messages_frame)
        undelivered_frame.pack(pady=5)
        
        see_label = tk.Label(undelivered_frame, text="See")
        see_label.pack(side=tk.LEFT, padx=2)
        
        self.num_messages_entry = tk.Entry(undelivered_frame, width=5)
        self.num_messages_entry.pack(side=tk.LEFT, padx=2)
        
        msg_label = tk.Label(undelivered_frame, text="undelivered messages")
        msg_label.pack(side=tk.LEFT, padx=2)
        
        self.go_button = tk.Button(undelivered_frame, text="Go", command=self.load_undelivered_messages, state=tk.DISABLED)
        self.go_button.pack(side=tk.LEFT, padx=2)

        self.messages_listbox = tk.Listbox(self.messages_frame, selectmode=tk.MULTIPLE)
        self.messages_listbox.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        # self.messages_listbox.bind('<<ListboxSelect>>', self.on_select)

        button_frame = tk.Frame(self.messages_frame)
        button_frame.pack(pady=5)

        self.load_more_button = tk.Button(button_frame, text="Load more", command=self.load_more_messages)
        self.load_more_button.pack(side=tk.LEFT, padx=5)

        self.delete_button = tk.Button(button_frame, text="Delete messages", command=self.delete_messages)
        self.delete_button.pack(side=tk.LEFT, padx=5)

        # Third column: Message display and input
        self.message_display_frame = tk.Frame(self.chat_frame)
        self.message_display_frame.grid(row=0, column=2, sticky="nsew")

        self.message_display = scrolledtext.ScrolledText(self.message_display_frame, wrap=tk.WORD, width=50, height=20)
        self.message_display.pack(padx=10, pady=10)
        self.message_display.config(state=tk.DISABLED)

        self.entry = tk.Entry(self.message_display_frame, width=40)
        self.entry.pack(side=tk.LEFT, padx=(10, 0))

        self.send_button = tk.Button(self.message_display_frame, text="Send", command=self.send_message)
        self.send_button.pack(side=tk.LEFT, padx=10)

        # Configure grid weights
        self.chat_frame.grid_columnconfigure(0, weight=1)
        self.chat_frame.grid_columnconfigure(1, weight=1)
        self.chat_frame.grid_columnconfigure(2, weight=1)
        self.chat_frame.grid_rowconfigure(0, weight=1)

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
        """Hashes a password using SHA-256."""
        password_bytes = password.encode('utf-8')
        sha_hash = hashlib.sha256(password_bytes)
        return sha_hash.hexdigest()

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
        self.message_display.config(state=tk.NORMAL)
        self.message_display.delete(1.0, tk.END)
        self.message_display.insert(tk.END, f"Send message to {self.selected_account}\n")
        self.message_display.config(state=tk.DISABLED)

    def update_accounts_list(self, accounts):
        self.accounts_listbox.delete(0, tk.END)
        for account in accounts:
            # Display username in the listbox
            self.accounts_listbox.insert(tk.END, account[1])

    def update_messages_list(self, messages, total_undelivered):
        logger.info(f"Updating messages list with {len(messages)} messages")
        self.messages_listbox.delete(0, tk.END)
        self.msgid_map.clear()  # Clear the previous mapping
        for index, message in enumerate(messages):
            sender = message[1]
            recipient = message[2]
            msg_content = message[3]
            timestamp = message[4]
            msgid = message[0]
            
            if recipient == self.username:
                display_text = f"From {sender}: {msg_content}"
                self.msgid_map[index] = msgid
            else:
                display_text = f"To {recipient}: {msg_content}"
            
            self.messages_listbox.insert(tk.END, display_text)
        self.undelivered_label.config(text=f"Undelivered messages: {total_undelivered}")
        self.go_button.config(state=tk.NORMAL if total_undelivered > 0 else tk.DISABLED)

    
    # ===================================================================
    # ===================================================================
    # Network functions (send requests to server)
    # ===================================================================
    # ===================================================================

    def thread_send(self, request):
        """Send a request to the server using a separate thread to reduce GUI lag."""
        thread = threading.Thread(target=self.send_to_server, args=(request,))
        thread.start()

    def check_username(self): 
        username = self.username_entry.get()
        if not username:
            return
        request = {
            "action": "check_username",
            "content": {"username": username},
        }
        if not self.is_threading:
            self.is_threading = True
            threading.Thread(target=lambda: self.network_thread(request), daemon=True).start()
        else:
            self.thread_send(request)

        self.thread_send(request)

    def register(self):
        username = self.register_username_entry.get()
        password = self.register_password_entry.get()
        if username and password:
            request = {
                "action": "register",
                "content": {"username": username, "password": self.hash_password(password)},
            }
            self.thread_send(request)

    def load_page_data(self):
        request = {
            "action": "load_page_data",
            "content": {"uuid": self.user_uuid},
        }
        self.thread_send(request)

    def search_accounts(self):
        search_term = self.search_bar.get().lower()
        request = {
            "action": "search_accounts",
            "content": {"search_term": search_term, "offset": self.current_page * 10},
        }
        self.thread_send(request)

    def delete_messages(self):
        selected_indices = self.messages_listbox.curselection()
        selected_msgids = [self.msgid_map[i] for i in selected_indices if i in self.msgid_map]
        request = {
            "action": "delete_messages",
            "content": {"msgids": selected_msgids, "deleter_uuid": self.user_uuid},
        }
        self.thread_send(request)

    def load_undelivered_messages(self):
        num_messages = int(self.num_messages_entry.get())
        if num_messages < 1 or num_messages > int(self.num_undelivered):
            tk.messagebox.showwarning("Invalid Input", f"Please enter a number between 1 and {self.num_undelivered} (your current number of undelivered messages).")
            return
        request = {
            "action": "load_undelivered",
            "content": {"num_messages": num_messages, "uuid": self.user_uuid},
        }
        self.thread_send(request)


    def load_messages(self):
        num_messages = self.num_messages
        logger.info(f"Loading {num_messages} messages")
        request = {
            "action": "load_messages",
            "content": {"num_messages": num_messages, "uuid": self.user_uuid},
        }
        self.thread_send(request)


    def send_message(self):
            msg = self.entry.get()
            if msg and self.selected_account:
                logger.info(f"Selected account: {self.selected_account}, Message: {msg}")
                self.entry.delete(0, tk.END)

                request = {
                    "action": "send_message",
                    "content": {"uuid": self.user_uuid, "recipient_username": self.selected_account, "message": msg, "timestamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')},
                }
                self.thread_send(request)

    def login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        if username and password:
            request = {
                "action": "login",
                "content": {"username": username, "password": self.hash_password(password)},
            }
            self.username = username
            if not self.is_threading:
                self.is_threading = True
                threading.Thread(target=lambda: self.network_thread(request), daemon=True).start()
            else:
                self.thread_send(request)


    def delete_account(self):
        password = self.dialog_password_entry.get()
        request = {
            "action": "delete_account",
            "content": {
                "uuid": self.user_uuid,
                "password": self.hash_password(password),
            }
        }
        self.thread_send(request)


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
                self.create_login_page()
            else:
                messagebox.showerror("Error", response["error"])

        elif response_type == "login_r":
            self.user_uuid = response.get("uuid", None)
            self.create_chat_page()

        elif response_type == "load_page_data_r":
            accounts = response.get("accounts", [])
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
            logger.info(f"Received {len(accounts)} accounts (total: {total_count})")
            
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
            logger.info(f"Received message from {sender}: {message}")
            self.num_messages += 1

            # update the messagelist box
            self.load_messages()
        
        elif response_type == "send_message_r":
            logger.info(f"send message status: {response.get('status', 'error')}")
            success = response.get("success", "error")
            if success:
                logger.info("Message sent successfully")
                self.num_messages += 1
                self.load_messages()

        elif response_type == "delete_messages_r":
            logger.info("Messages deleted successfully")
            num_deleted = response.get("total_count", 0)
            self.num_messages -= num_deleted
            self.load_messages()
        
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

        
        elif response_type == "error": # Handle error response
            logger.error(f"Error: {response.get('error', 'An error occurred')}")
            messagebox.showerror("Error", response.get("error", "An error occurred"), icon="warning")
    