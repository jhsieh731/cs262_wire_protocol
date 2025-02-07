import sys
import socket
import selectors
import threading
import tkinter as tk
from tkinter import scrolledtext
import msg_client


# Networking Setup
sel = selectors.DefaultSelector()
host, port = sys.argv[1], int(sys.argv[2])

# GUI Setup
class ClientGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Client Application")

        self.user_uuid = None
        self.selected_accounts = None
        self.current_page = 0
        self.accounts_per_page = 1
        self.max_accounts_page = 0

        self.login_frame = tk.Frame(master)
        self.chat_frame = tk.Frame(master)
        self.create_account_frame = tk.Frame(master)
        self.error_frame = tk.Frame(master)
        self.is_threading = False

        self.create_login_page()

    def clear_frame(self, frame):
        for widget in frame.winfo_children():
            widget.destroy()
        frame.pack_forget()
    
    def create_error_page(self, error_message):
        self.clear_frame(self.login_frame)
        self.clear_frame(self.chat_frame)
        self.error_frame.pack()

        self.error_label = tk.Label(self.error_frame, text="Error", fg="red", font=("Helvetica", 16))
        self.error_label.pack(padx=10, pady=10)

        self.error_message_label = tk.Label(self.error_frame, text=error_message, wraplength=400)
        self.error_message_label.pack(padx=10, pady=10)

        self.back_button = tk.Button(self.error_frame, text="Back", command=self.create_login_page)
        self.back_button.pack(padx=10, pady=10)

    def create_login_page(self):
        self.clear_frame(self.chat_frame)
        self.clear_frame(self.error_frame)

        self.login_frame.pack()

        self.username_label = tk.Label(self.login_frame, text="Username:")
        self.username_label.pack(padx=10, pady=5)
        self.username_entry = tk.Entry(self.login_frame)
        self.username_entry.pack(padx=10, pady=5)

        self.password_label = tk.Label(self.login_frame, text="Password:")
        self.password_label.pack(padx=10, pady=5)
        self.password_entry = tk.Entry(self.login_frame, show="*")
        self.password_entry.pack(padx=10, pady=5)

        self.login_button = tk.Button(self.login_frame, text="Login", command=self.login_register)
        self.login_button.pack(padx=10, pady=5)


    def create_chat_page(self):
        self.clear_frame(self.login_frame)
        self.clear_frame(self.error_frame)
        self.chat_frame.pack(fill=tk.BOTH, expand=True)

        # First column: Accounts list with search bar and pagination
        self.accounts_frame = tk.Frame(self.chat_frame)
        self.accounts_frame.grid(row=0, column=0, sticky="nsew")

        self.search_bar = tk.Entry(self.accounts_frame)
        self.search_bar.pack(padx=10, pady=5)
        self.search_button = tk.Button(self.accounts_frame, text="Search", command=self.search_accounts)
        self.search_button.pack(padx=10, pady=5)

        # Delete Account Button
        self.delete_account_button = tk.Button(self.accounts_frame, text="Delete My Account", command=self.confirm_delete_account)
        self.delete_account_button.pack(padx=10, pady=5)

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

        self.messages_label = tk.Label(self.messages_frame, text="Messages")
        self.messages_label.pack(padx=10, pady=5)

        self.read_button = tk.Button(self.messages_frame, text="Read", command=self.read_messages)
        self.read_button.pack(padx=10, pady=5)
        self.delete_button = tk.Button(self.messages_frame, text="Delete", command=self.delete_messages)
        self.delete_button.pack(padx=10, pady=5)

        self.undelivered_label = tk.Label(self.messages_frame, text="Undelivered messages: 0")
        self.undelivered_label.pack(padx=10, pady=5)

        self.num_messages_entry = tk.Entry(self.messages_frame)
        self.num_messages_entry.pack(padx=10, pady=5)
        self.go_button = tk.Button(self.messages_frame, text="Go", command=self.load_messages)
        self.go_button.pack(padx=10, pady=5)

        self.messages_listbox = tk.Listbox(self.messages_frame, selectmode=tk.MULTIPLE)
        self.messages_listbox.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

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
        # self.load_accounts()
        # self.load_messages()

    def search_accounts(self):
        search_term = self.search_bar.get()
        request = {
            "protocol-type": "json",
            "action": "search_accounts",
            "content": {"search_term": search_term, "current_page": self.current_page, "accounts_per_page": self.accounts_per_page},
        }
        send_to_server(request)

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

    def update_message_input_area(self):
        self.message_display.config(state=tk.NORMAL)
        self.message_display.delete(1.0, tk.END)
        self.message_display.insert(tk.END, f"Send message to {self.selected_account}\n")
        self.message_display.config(state=tk.DISABLED)

    def read_messages(self):
        selected_indices = self.messages_listbox.curselection()
        selected_messages = [self.messages_listbox.get(i) for i in selected_indices]
        request = {
            "protocol-type": "json",
            "action": "read_messages",
            "content": {"messages": selected_messages},
        }
        send_to_server(request)

    def delete_messages(self):
        selected_indices = self.messages_listbox.curselection()
        selected_messages = [self.messages_listbox.get(i) for i in selected_indices]
        request = {
            "protocol-type": "json",
            "action": "delete_messages",
            "content": {"messages": selected_messages},
        }
        send_to_server(request)

    def load_messages(self):
        num_messages = self.num_messages_entry.get()
        request = {
            "protocol-type": "json",
            "action": "load_messages",
            "content": {"num_messages": num_messages},
        }
        send_to_server(request)

    def update_accounts_list(self, accounts):
        self.accounts_listbox.delete(0, tk.END)
        for account in accounts:
            # Display username in the listbox
            self.accounts_listbox.insert(tk.END, account['username'])

    def update_messages_list(self, messages):
        self.messages_listbox.delete(0, tk.END)
        for message in messages:
            self.messages_listbox.insert(tk.END, message)

    def send_message(self):
            msg = self.entry.get()
            if msg and self.selected_account:
                print(f"Selected account: {self.selected_account}, Message: {msg}")
                self.entry.delete(0, tk.END)
                request = {
                    "protocol-type": "json",
                    "action": "send_message",
                    "content": {"sender_uuid": self.user_uuid, "recipient_username": self.selected_account, "message": msg},
                }
                send_to_server(request)

    def login_register(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        if username and password:
            self.send_login_register_request(username, password)

    def send_login_register_request(self, username, password):
        request = {
            "protocol-type": "json",
            "action": "login_register",
            "content": {"username": username, "password": password},
        }
        if not self.is_threading:
            self.is_threading = True
            threading.Thread(target=lambda: network_thread(request), daemon=True).start()
        else:
            send_to_server(request)


    def confirm_delete_account(self):
        # Create a dialog window
        dialog = tk.Toplevel(self.master)
        dialog.title("Confirm Account Deletion")
        dialog.geometry("300x250")  # Increased height
        dialog.transient(self.master)  # Make dialog modal
        dialog.grab_set()  # Make the dialog modal

        # Add warning message
        warning_label = tk.Label(dialog, text="Are you sure you want to delete your account?\nThis action cannot be undone.", wraplength=250)
        warning_label.pack(padx=10, pady=10)

        # Password entry
        password_label = tk.Label(dialog, text="Enter your password to confirm:")
        password_label.pack(padx=10, pady=5)
        password_entry = tk.Entry(dialog, show="*")
        password_entry.pack(padx=10, pady=5)

        def delete_account():
            password = password_entry.get()
            request = {
                "action": "delete_account",
                "content": {
                    "uuid": self.user_uuid,
                    "password": password
                }
            }
            send_to_server(request)
            dialog.destroy()
            # After server confirms deletion, return to login page
            self.clear_frame(self.chat_frame)
            self.create_login_page()

        # Buttons
        delete_button = tk.Button(dialog, text="Delete Account", command=delete_account, fg="red")
        delete_button.pack(pady=10)
        
        cancel_button = tk.Button(dialog, text="Cancel", command=dialog.destroy)
        cancel_button.pack(pady=5)

    def handle_server_response(self, response):
        response_type = response["response_type"]
        print(f"Action: {response_type}, Response: {response}")
        
        if response_type == "delete_account":
            if response["status"] != "success":
                messagebox.showerror("Error", response["message"])
        if response_type == "login_register":
            self.user_uuid = response.get("uuid", None)
            self.create_chat_page()
        elif response_type == "search_accounts":
            accounts = response.get("accounts", [])
            total_count = response.get("total_count", 0)
            print(f"Received {len(accounts)} accounts (total: {total_count})")
            
            # Update the accounts list
            self.update_accounts_list(accounts)
            
            # Update pagination state. Start index from 0
            self.max_accounts_page = (total_count // self.accounts_per_page) - 1
            
            # Enable/disable pagination buttons
            self.prev_button["state"] = tk.NORMAL if self.current_page > 0 else tk.DISABLED
            self.next_button["state"] = tk.NORMAL if self.current_page < self.max_accounts_page else tk.DISABLED
            
        elif response_type == "check_username":
            # Handle check username response
            pass
        elif response_type == "error": # Handle error response
            print("Error: ", response.get("response", "An error occurred"))
            self.create_error_page(response.get("response", "An error occurred"))



# Main GUI Application
root = tk.Tk()
gui = ClientGUI(root)

# Networking Functions
def start_connection(host, port, gui, request):
    addr = (host, port)
    print(f"Starting connection to {addr}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    sock.connect_ex(addr)
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    message = msg_client.Message(sel, sock, addr, gui, request)
    sel.register(sock, events, data=message)

# Thread for handling server communication
def network_thread(request):
    print(request)
    start_connection(host, port, gui, request)
    try:
        while True:
            events = sel.select(timeout=1)
            for key, mask in events:
                message = key.data
                try:
                    message.process_events(mask)
                except Exception:
                    print(
                        f"Main: Error: Exception for {message.addr}"
                    )
                    message.close()
            # Check for a socket being monitored to continue.
            if not sel.get_map():
                break
    except KeyboardInterrupt:
        print("Caught keyboard interrupt, exiting")
    finally:
        print("selectors closed")
        sel.close()

# Send message to the server
def send_to_server(request):
    for key in list(sel.get_map().values()):
        msg_obj = key.data  # This is the Message instance
        
        # Set the request and queue it
        msg_obj.request = request
        msg_obj._request_queued = False  # Ensure we can queue the new message
        msg_obj.queue_request()          # Queue the message for sending
        
        # Set selector to listen for write events
        msg_obj._set_selector_events_mask("w")


# Run the Tkinter main loop
root.mainloop()