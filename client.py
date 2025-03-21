# import sys
# import socket
# import selectors
# import json
# import tkinter as tk
# import threading
# import msg_client
# from gui import ClientGUI
# from logger import set_logger

# logger = set_logger("client", "client.log")

# # Networking Setup
# sel = None
# host = None
# port = None
# protocol = None
# # leader = None  # Stores (leader_host, leader_port)


# def initialize_client(server_host, server_port, input_protocol):
#     """Initialize the client with the given host and port."""
#     global sel, host, port, protocol
#     sel = selectors.DefaultSelector()
#     host = server_host
#     port = server_port
#     protocol = input_protocol
#     return sel


# # def find_leader():
# #     """Query cluster nodes to find the current leader."""
# #     global leader
# #     cluster_nodes = [(host, port)]  # Could add other known nodes

# #     for node in cluster_nodes:
# #         try:
# #             logger.info(f"Client: Sending find_leader to {node}")
# #             response = send_direct_request(node, {"type": "find_leader"})
# #             if response:
# #                 leader = (response["host"], response["port"])
# #                 logger.info(f"Client: Found leader at {leader}")
# #                 return leader
# #         except Exception as e:
# #             logger.error(f"Error contacting node {node}: {e}")
    
# #     logger.error("Client: Could not determine leader. Retrying...")
# #     return None


# # def send_direct_request(node, request):
# #     """Send a JSON request directly to a Raft node."""
# #     try:
# #         with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
# #             sock.connect(node)
# #             sock.sendall(json.dumps(request).encode())
# #             data = sock.recv(1024)
# #             return json.loads(data.decode())
# #     except Exception as e:
# #         logger.error(f"Error contacting {node}: {e}")
# #         return None

# def send_to_server(request):
#     """Send a request to the leader."""
#     global leader
#     if sel is None:
#         logger.error("Client not initialized. Call initialize_client first.")
#         return

#     # Ensure we have a leader
#     # if not leader:
#     #     leader = find_leader()
#     #     if not leader:
#     #         logger.error("Client: No leader available, request failed.")
#     #         return
#     #     # Start network_thread in a separate thread so it doesn't block the main (GUI) thread.
#     #     threading.Thread(target=network_thread, args=(request,), daemon=True).start()
#     #     return

#     try:
#         for key in list(sel.get_map().values()):
#             msg_obj = key.data  # This is the Message instance

#             # Set the request and queue it
#             msg_obj.request = request
#             msg_obj.queue_request()          # Queue the message for sending

#             # Set selector to listen for write events
#             msg_obj._set_selector_events_mask("w")
#     except Exception as e:
#         logger.error(f"Error sending to server: {e}")


# def network_thread(request):
#     """Handles sending requests and maintaining communication."""
#     logger.info(request)
#     start_connection(gui, request)
#     try:
#         while True:
#             events = sel.select(timeout=1)
#             for key, mask in events:
#                 message = key.data
#                 try:
#                     message.process_events(mask)
#                 except Exception:
#                     logger.info(f"Main: Error: Exception for {message.addr}")
#                     message.close()
#             # The thread continues running as a daemon thread
#     except KeyboardInterrupt:
#         logger.info("Caught keyboard interrupt, exiting")
#     finally:
#         logger.info("Network thread finished")

# # GUI Setup
# root = tk.Tk()
# gui = ClientGUI(root, send_to_server, network_thread)


# # Networking Functions
# def start_connection(gui, request):
#     """Start a connection to the leader."""
#     global host, port, protocol
#     # global leader
#     # if not leader:
#     #     leader = find_leader()
#     #     if not leader:
#     #         logger.error("Client: No leader available, cannot start connection.")
#     #         return
    
#     addr = (host, port)
#     logger.info(f"Starting connection to leader at {addr}")
#     sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     sock.setblocking(False)
#     sock.connect_ex(addr)
#     events = selectors.EVENT_READ | selectors.EVENT_WRITE
#     message = msg_client.Message(sel, sock, addr, gui, request, protocol)
#     sel.register(sock, events, data=message)


# def main():
#     """Entry point for client application."""
#     if len(sys.argv) != 4:
#         logger.info(f"Usage: {sys.argv[0]} <host> <port> <protocol>")
#         sys.exit(1)
    
#     server_host = sys.argv[1]
#     input_protocol = sys.argv[3]
#     server_port = None
    
#     try:
#         server_port = int(sys.argv[2])
#     except ValueError:
#         logger.info(f"Error: Port must be a number")
#         sys.exit(1)
    
#     # Initialize client
#     if server_port is not None:
#         initialize_client(server_host, server_port, input_protocol)
#         # find_leader()  # Find the leader before starting GUI
#         root.mainloop()


# if __name__ == '__main__':
#     main()


import sys
import socket
import selectors
import tkinter as tk
import msg_client
from gui import ClientGUI
from logger import set_logger

logger = set_logger("client", "client.log")

# Networking Setup
sel = None
host = None
port = None
protocol = None

def initialize_client(server_host, server_port, input_protocol):
    """Initialize the client with the given host and port."""
    global sel, host, port, protocol
    sel = selectors.DefaultSelector()
    host = server_host
    port = server_port
    protocol = input_protocol
    return sel

# Send message to the server
def send_to_server(request):
    if sel is None:
        logger.error("Client not initialized. Call initialize_client first.")
        return
        
    try:
        for key in list(sel.get_map().values()):
            msg_obj = key.data  # This is the Message instance
            
            # Set the request and queue it
            msg_obj.request = request
            msg_obj.queue_request()          # Queue the message for sending
            
            # # Set selector to listen for write events
            msg_obj._set_selector_events_mask("w")
    except Exception as e:
        logger.error(f"Error sending to server: {e}")

# Thread for handling server communication
def network_thread(request):
    logger.info(request)
    start_connection(gui, request)
    try:
        while True:
            events = sel.select(timeout=1)
            for key, mask in events:
                message = key.data
                try:
                    message.process_events(mask)
                except Exception:
                    logger.info(
                        f"Main: Error: Exception for {message.addr}"
                    )
                    message.close()
            # Check for a socket being monitored to continue.
            if not sel.get_map():
                break
    except KeyboardInterrupt:
        logger.info("Caught keyboard interrupt, exiting")
    finally:
        logger.info("selectors closed")
        sel.close()


# Main GUI Application
root = tk.Tk()
gui = ClientGUI(root, send_to_server, network_thread)

# Networking Functions
def start_connection(gui, request):
    addr = (host, port)
    logger.info(f"Starting connection to {addr}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    sock.connect_ex(addr)
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    message = msg_client.Message(sel, sock, addr, gui, request, protocol)
    sel.register(sock, events, data=message)


def main():
    if len(sys.argv) != 4:
        logger.info(f"Usage: {sys.argv[0]} <host> <port> <protocol>")
        sys.exit(1)
    
    server_host = sys.argv[1]
    input_protocol = sys.argv[3]
    server_port = None
    
    try:
        server_port = int(sys.argv[2])
    except ValueError:
        logger.info(f"Error: Port must be a number")
        sys.exit(1)
    
    # Initialize client
    if server_port is not None:
        initialize_client(server_host, server_port, input_protocol)
        # Run the Tkinter main loop
        root.mainloop()

if __name__ == '__main__':
    main()