import sys
import socket
import selectors
import types
import threading
import tkinter as tk
from tkinter import scrolledtext
import msg_client
from database import MessageDatabase
import queue

# Create a queue for thread-safe message passing
message_queue = queue.Queue()

# Networking Setup
sel = selectors.DefaultSelector()
messages = [b"Message 1 from client.", b"Message 2 from client."]
host, port = sys.argv[1], int(sys.argv[2])
db = MessageDatabase()

# GUI Setup
class ClientGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Client Application")

        # Add List All Contacts button at the top
        self.list_contacts_button = tk.Button(master, text="List All Contacts", command=self.list_contacts)
        self.list_contacts_button.pack(side=tk.TOP, anchor=tk.W, padx=10, pady=5)

        self.text_area = scrolledtext.ScrolledText(master, wrap=tk.WORD, width=50, height=20)
        self.text_area.pack(padx=10, pady=10)
        self.text_area.config(state=tk.DISABLED)

        self.entry = tk.Entry(master, width=40)
        self.entry.pack(side=tk.LEFT, padx=(10, 0))

        self.send_button = tk.Button(master, text="Send", command=self.send_message)
        self.send_button.pack(side=tk.LEFT, padx=10)
        
        # Start checking for messages
        self.check_message_queue()

    def check_message_queue(self):
        try:
            while True:  # Process all available messages
                message = message_queue.get_nowait()
                self.display_message(message)
        except queue.Empty:
            pass
        finally:
            # Schedule the next check
            self.master.after(100, self.check_message_queue)
    
    def display_message(self, message):
        self.text_area.config(state=tk.NORMAL)
        
        # Try to parse the message as JSON to check if it's a contacts list
        try:
            data = json.loads(message)
            if isinstance(data, dict) and 'content' in data:
                content = data['content']
                if 'contacts' in content:
                    # Clear the text area first
                    self.text_area.delete('1.0', tk.END)
                    # Display contacts in a formatted way
                    self.text_area.insert(tk.END, "=== Contacts List ===\n\n")
                    for name in content['contacts']:
                        self.text_area.insert(tk.END, f"{name}\n")
                    return
        except json.JSONDecodeError:
            pass
        
        # Default behavior for regular messages
        self.text_area.insert(tk.END, message + '\n')
        self.text_area.yview(tk.END)
        self.text_area.config(state=tk.DISABLED)

    def send_message(self):
        msg = self.entry.get()
        if msg:
            self.entry.delete(0, tk.END)
            send_to_server(msg)

    def list_contacts(self):
        send_to_server("list_contacts")

# Networking Functions
def start_connection(host, port):
    addr = (host, port)
    print(f"Starting connection to {addr}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    sock.connect_ex(addr)
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    content = dict()
    # json header
    init_request = {
        "action": "start_connection",
        "content": content,
    }
    message = msg_client.Message(sel, sock, addr, init_request)
    sel.register(sock, events, data=message)


# def service_connection(key, mask):
#     sock = key.fileobj
#     data = key.data
#     if mask & selectors.EVENT_READ:
#         recv_data = sock.recv(1024)
#         if recv_data:
#             data.outb += recv_data
#         else:
#             print(f"Closing connection to {data.addr}")
#             sel.unregister(sock)
#             sock.close()
#     if mask & selectors.EVENT_WRITE:
#         if data.outb:
#             # return_data = trans_to_pig_latin(data.outb.decode("utf-8")) do things here
#             return_data = return_data.encode("utf-8")
#             sent = sock.send(return_data)
#             data.outb = data.outb[sent:]

# Thread for handling server communication
def network_thread():
    start_connection(host, port)
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
def send_to_server(message):
    # for key in sel.get_map().values():
    #     key.data.outb += message
    for key in list(sel.get_map().values()):
        msg_obj = key.data  # This is the Message instance
        
        # Prepare the new request
        if message == "list_contacts":
            request = {
                "action": "list_contacts",
                "content": {},
            }
        else:
            request = {
                "action": "send",
                "content": {"message": message},
            }
        
        # Set the request and queue it
        msg_obj.request = request
        msg_obj._request_queued = False  # Ensure we can queue the new message
        msg_obj.queue_request()          # Queue the message for sending
        
        # Set selector to listen for write events
        msg_obj._set_selector_events_mask("w")
        if message != "list_contacts":
            db.store_message("server1", "server2", message)

# Main GUI Application
root = tk.Tk()
gui = ClientGUI(root)

# Start the network thread
threading.Thread(target=network_thread, daemon=True).start()

# Run the Tkinter main loop
root.mainloop()
