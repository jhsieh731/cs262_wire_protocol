import sys
import tkinter as tk
from gui import ClientGUI
from logger import set_logger
from grpc_client import ChatClient

logger = set_logger("client", "client.log")

def main():
    if len(sys.argv) != 3:
        logger.info(f"Usage: {sys.argv[0]} <host> <port>")
        sys.exit(1)
    
    host = sys.argv[1]
    try:
        port = int(sys.argv[2])
    except ValueError:
        logger.info(f"Error: Port must be a number")
        sys.exit(1)

    # Initialize gRPC client
    client = ChatClient(host, port)
    
    # Initialize GUI
    root = tk.Tk()
    gui = ClientGUI(root, client)
    
    try:
        root.mainloop()
    finally:
        client.close()

if __name__ == '__main__':
    main()