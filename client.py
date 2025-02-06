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

        self.login_frame = tk.Frame(master)
        self.chat_frame = tk.Frame(master)
        self.create_account_frame = tk.Frame(master)
        self.error_frame = tk.Frame(master)
        self.is_threading = False

        self.create_login_page()
    
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
        self.chat_frame.pack()

        self.text_area = scrolledtext.ScrolledText(self.chat_frame, wrap=tk.WORD, width=50, height=20)
        self.text_area.pack(padx=10, pady=10)
        self.text_area.config(state=tk.DISABLED)

        self.entry = tk.Entry(self.chat_frame, width=40)
        self.entry.pack(side=tk.LEFT, padx=(10, 0))

        self.send_button = tk.Button(self.chat_frame, text="Send", command=self.send_message)
        self.send_button.pack(side=tk.LEFT, padx=10)

    def clear_frame(self, frame):
        for widget in frame.winfo_children():
            widget.destroy()
        frame.pack_forget()

    def display_message(self, message):
        self.text_area.config(state=tk.NORMAL)
        self.text_area.insert(tk.END, message + '\n')
        self.text_area.yview(tk.END)
        self.text_area.config(state=tk.DISABLED)

    def send_message(self):
        msg = self.entry.get()
        if msg:
            self.entry.delete(0, tk.END)
            send_to_server(msg)

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


    def handle_server_response(self, response):
        response_type = response["response_type"]
        print(f"Action: {response_type}, Response: {response}")
        if response_type == "login_register":
            self.user_uuid = response.get("response", None)
            self.create_chat_page()
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