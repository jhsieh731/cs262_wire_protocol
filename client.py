import sys
import socket
import selectors
import types
import threading
import tkinter as tk
from tkinter import scrolledtext
from database import MessageDatabase

# Networking Setup
sel = selectors.DefaultSelector()
messages = [b"Message 1 from client.", b"Message 2 from client."]
host, port, num_conns = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
db = MessageDatabase()

# GUI Setup
class ClientGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Client Application")

        self.text_area = scrolledtext.ScrolledText(master, wrap=tk.WORD, width=50, height=20)
        self.text_area.pack(padx=10, pady=10)
        self.text_area.config(state=tk.DISABLED)

        self.entry = tk.Entry(master, width=40)
        self.entry.pack(side=tk.LEFT, padx=(10, 0))

        self.send_button = tk.Button(master, text="Send", command=self.send_message)
        self.send_button.pack(side=tk.LEFT, padx=10)

    def display_message(self, message):
        self.text_area.config(state=tk.NORMAL)
        self.text_area.insert(tk.END, message + '\n')
        self.text_area.yview(tk.END)
        self.text_area.config(state=tk.DISABLED)

    def send_message(self):
        msg = self.entry.get()
        if msg:
            self.entry.delete(0, tk.END)
            send_to_server(msg.encode())

# Networking Functions
def start_connections(host, port, num_conns):
    server_addr = (host, port)
    for i in range(num_conns):
        connid = i + 1
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        sock.connect_ex(server_addr)
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        data = types.SimpleNamespace(connid=connid, outb=b"")
        sel.register(sock, events, data=data)

def service_connection(key, mask):
    sock = key.fileobj
    data = key.data
    if mask & selectors.EVENT_READ:
        recv_data = sock.recv(1024)
        if recv_data:
            gui.display_message(f"Received from server: {recv_data.decode()}")
        else:
            sel.unregister(sock)
            sock.close()
    if mask & selectors.EVENT_WRITE:
        if data.outb:
            sock.send(data.outb)
            data.outb = b""

# Thread for handling server communication
def network_thread():
    start_connections(host, port, num_conns)
    while True:
        events = sel.select(timeout=1)
        for key, mask in events:
            service_connection(key, mask)

# Send message to the server
def send_to_server(message):
    for key in sel.get_map().values():
        key.data.outb += message
        db.store_message("server1", "server2", message)

# Main GUI Application
root = tk.Tk()
gui = ClientGUI(root)

# Start the network thread
threading.Thread(target=network_thread, daemon=True).start()

# Run the Tkinter main loop
root.mainloop()
