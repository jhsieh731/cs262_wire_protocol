import sys
import socket
import selectors
import tkinter as tk
import threading
import json
import queue
import msg_client
from gui import ClientGUI
from logger import set_logger

logger = set_logger("client", "client.log")

# Networking Setup
sel = None
protocol = None

current_leader_host = None
current_leader_port = None

# These specify the client's listening address for receiving asynchronous responses.
client_listen_host = "127.0.0.1"
client_listen_port = 60001

# A queue to store leader responses received from raft nodes.
leader_response_queue = queue.Queue()


def initialize_client(input_protocol):
    global sel, protocol
    sel = selectors.DefaultSelector()
    protocol = input_protocol
    return sel


def leader_response_listener():
    """
    Runs as a separate thread.
    Listens on (client_listen_host, client_listen_port) for find_leader responses.
    """
    listener_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener_socket.bind((client_listen_host, client_listen_port))
    listener_socket.listen(5)
    logger.info(f"Client leader response listener running on {(client_listen_host, client_listen_port)}")
    while True:
        try:
            conn, addr = listener_socket.accept()
            data = conn.recv(1024)
            if data:
                response = json.loads(data.decode('utf-8'))
                logger.info(f"Leader response received from {addr}: {response}")
                # Put the response into the queue.
                leader_response_queue.put(response)
            conn.close()
        except Exception as e:
            logger.error(f"Error in leader response listener: {e}")


def find_leader():
    with open('config.json', 'r') as f:
        config = json.load(f)
    raft_nodes = config.get("raft_nodes", {})
    num_nodes = len(raft_nodes)
    
    # Send a find_leader request (including client's address) to every raft node.
    for node_id, node_info in raft_nodes.items():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.1)
            s.connect((node_info["host"], node_info["port"]))
            request = json.dumps({
                "type": "find_leader",
                "host": client_listen_host,
                "port": client_listen_port
            }).encode('utf-8')
            s.sendall(request)
            logger.info(f"Sent find_leader request to node {node_id}: {request!r}")
            s.close()
        except Exception as e:
            logger.error(f"Error contacting raft node {node_id} for leader info: {e}")
    
    responses = []
    # Wait for responses from all raft nodes (or until timeout for each)
    for _ in range(num_nodes):
        try:
            # Adjust timeout as we wait for response.
            response = leader_response_queue.get(timeout=0.1)
            logger.info(f"Leader response received: {response}")
            responses.append(response)
        except Exception as e:
            logger.error(f"Timeout waiting for a leader response: {e}")
            break

    # Check all collected responses for a valid leader.
    for resp in responses:
        if (resp.get("type") == "find_leader_response" and
            resp.get("node_id") is not None):
            logger.info(f"Using leader response: {resp}")
            client_nodes = config.get("client_nodes", {})
            client_node = client_nodes.get(resp["node_id"])
            # if client_node:
            return client_node["host"], client_node["port"]
            # return resp["host"], resp["port"]

    logger.error("No leader found among raft nodes.")
    return None, None

def send_to_server(request):
    global current_leader_host, current_leader_port
    leader_host, leader_port = find_leader()
    if not leader_host:
        logger.error("No leader found. Request aborted.")
        return
    logger.info(f"Leader found at {(leader_host, leader_port)}; current is {(current_leader_host, current_leader_port)}")
    if leader_host != current_leader_host or leader_port != current_leader_port:
        logger.info(f"Starting connection to leader at {(leader_host, leader_port)}")
        logger.info(f"Request: {request}")

        # Close all existing connections in the selector.
        for key in list(sel.get_map().values()):
            key.data.close()
        
        # Open a new connection to the leader using the already-defined start_connection function.
        start_connection(gui, request, leader_host, leader_port)
    else:
        logger.info(f"Reusing connection to leader at {(leader_host, leader_port)}")
        logger.info(f"Request: {request}")
        try:
            for key in list(sel.get_map().values()):
                msg_obj = key.data  # This is the Message instance
    
                # Set the request and queue it
                msg_obj.request = request
                msg_obj.queue_request()          # Queue the message for sending
    
                # Set selector to listen for write events
                msg_obj._set_selector_events_mask("w")
        except Exception as e:
            logger.error(f"Error sending to server: {e}")

# Thread for handling server communication
def network_thread(request):
    logger.info(request)
    leader_host, leader_port = find_leader()
    if not leader_host:
        logger.error("No leader found. Request aborted.")
        return

    start_connection(gui, request, leader_host, leader_port)
    try:
        while True:
            events = sel.select(timeout=1)
            for key, mask in events:
                message = key.data
                try:
                    message.process_events(mask)
                except Exception:
                    logger.info(f"Main: Error: Exception for {message.addr}")
                    message.close()
            if not sel.get_map():
                # break
                continue
    except KeyboardInterrupt:
        logger.info("Caught keyboard interrupt, exiting")
    finally:
        logger.info("Selectors closed")
        sel.close()


# Main GUI Application
root = tk.Tk()
gui = ClientGUI(root, send_to_server, network_thread)


# Networking Functions: Start a connection to the leader
def start_connection(gui, request, host, port):
    global current_leader_host, current_leader_port
    current_leader_host = host
    current_leader_port = port
    logger.info(f"Starting connection to leader at {(host, port)}")
    print(f"Starting connection to leader at {(host, port)}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    sock.connect_ex((host, port))
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    message = msg_client.Message(sel, sock, (host, port), gui, request, protocol)
    sel.register(sock, events, data=message)

# def update_leader(node_id):
#     global current_server_index, leader_query_pending
#     current_server_index = node_id
#     logger.info(f"Updated leader to server {server_addresses[current_server_index]}")
    
#     # Close all existing connections in the selector.
#     for key in list(sel.get_map().values()):
#         key.data.close()
    
#     # Clear the leader query flag before retrying.
#     leader_query_pending = False
    
#     # Retry the last request with the new leader.
#     if last_request:
#         start_connection(gui, last_request)
#     else:
#         start_connection(gui, {"action": "empty", "content": {}})


def main():
    if len(sys.argv) != 2:
        logger.info(f"Usage: {sys.argv[0]} <protocol>")
        sys.exit(1)

    input_protocol = sys.argv[1]
    initialize_client(input_protocol)
    # Start the leader response listener thread
    listener_thread = threading.Thread(target=leader_response_listener, daemon=True)
    listener_thread.start()
    # Start the GUI main loop (which will trigger send_to_server as needed)
    root.mainloop()

if __name__ == '__main__':
    main()