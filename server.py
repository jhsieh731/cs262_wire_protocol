import sys
import socket
import selectors
from msg_server import Message

sel = selectors.DefaultSelector()

def initialize_server(host='localhost', port=65432):
    """Initialize the server with the given host and port."""
    lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lsock.bind((host, port))
    lsock.listen()
    print(f"Listening on {(host, port)}")
    lsock.setblocking(False)
    sel.register(lsock, selectors.EVENT_READ, data=None)
    return lsock

# Only run server initialization if script is run directly
if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <host> <port>")
        sys.exit(1)
    try:
        host, port = sys.argv[1], int(sys.argv[2])
        lsock = initialize_server(host, port)
    except ValueError:
        print(f"Error: Port must be a number")
        sys.exit(1)


# accept new connections and register them with the selector
def accept_wrapper(sock):
    conn, addr = sock.accept()  # Should be ready to read
    print(f"Accepted connection from {addr}")
    conn.setblocking(False)
    message = Message(sel, conn, addr)
    sel.register(conn, selectors.EVENT_READ, data=message)


def run_server():
    """Run the server event loop."""
    try:
        while True:
            events = sel.select(timeout=None)
            for key, mask in events:
                if key.data is None:
                    accept_wrapper(key.fileobj)
                else:
                    message = key.data
                    try:
                        message.process_events(mask)
                    except Exception:
                        print(
                            f"Main: Error: Exception for {message.addr}:\n"
                        )
                        message.close()
    except KeyboardInterrupt:
        print("Caught keyboard interrupt, exiting")
    finally:
        sel.close()

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <host> <port>")
        sys.exit(1)
    try:
        host, port = sys.argv[1], int(sys.argv[2])
        lsock = initialize_server(host, port)
        run_server()
    except ValueError:
        print(f"Error: Port must be a number")
        sys.exit(1)
