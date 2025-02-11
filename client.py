import sys
import socket
import selectors
import tkinter as tk
import msg_client
from gui import ClientGUI


# Networking Setup
sel = None
host = None
port = None

def initialize_client(server_host, server_port):
    """Initialize the client with the given host and port."""
    global sel, host, port
    sel = selectors.DefaultSelector()
    host = server_host
    port = server_port
    return sel

# Send message to the server
def send_to_server(request):
     for key in list(sel.get_map().values()):
        msg_obj = key.data  # This is the Message instance
        
        # Set the request and queue it
        msg_obj.request = request
        msg_obj.queue_request()          # Queue the message for sending
        
        # # Set selector to listen for write events
        msg_obj._set_selector_events_mask("w")

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
        logger.info("Caught keyboard interrupt, exiting")
    finally:
        print("selectors closed")
        sel.close()


# Main GUI Application
root = tk.Tk()
gui = ClientGUI(root, send_to_server, network_thread)

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




if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <host> <port>")
        sys.exit(1)
    try:
        server_host = sys.argv[1]
        server_port = int(sys.argv[2])
    except ValueError:
        print(f"Error: Port must be a number")
        sys.exit(1)
    
    # Initialize client
    initialize_client(server_host, server_port)
    
    # Run the Tkinter main loop
    root.mainloop()