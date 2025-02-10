import sys
import socket
import selectors
from msg_server import Message

sel = selectors.DefaultSelector()

def initialize_server(host='localhost', port=65432):
    """Initialize the server with the given host and port."""
    try:
        lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Allow reuse of address
        lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            lsock.bind((host, port))
        except OSError as e:
            print(f"Error binding to {host}:{port} - {e}")
            print("Try using a different port number.")
            lsock.close()
            sys.exit(1)
        lsock.listen()
        print(f"Listening on {(host, port)}")
        lsock.setblocking(False)
        sel.register(lsock, selectors.EVENT_READ, data=None)
        return lsock
    except Exception as e:
        print(f"Error initializing server: {e}")
        sys.exit(1)

def accept_wrapper(sock):
    """Accept a new connection and register it with the selector."""
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
                    except Exception as e:
                        print(f"Error processing events for {message.addr}: {e}")
                        message.close()
    except KeyboardInterrupt:
        print("\nCaught keyboard interrupt, shutting down...")
    except Exception as e:
        print(f"\nError in server: {e}")
    finally:
        print("Closing all connections...")
        # Close all open sockets
        for key in list(sel.get_map().values()):
            sel.unregister(key.fileobj)
            key.fileobj.close()
        sel.close()


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <host> <port>")
        sys.exit(1)
    try:
        host, port = sys.argv[1], int(sys.argv[2])
        if port < 1024 and port != 0:  # Avoid privileged ports
            print("Error: Please use a port number >= 1024")
            sys.exit(1)
        lsock = initialize_server(host, port)
        run_server()
    except ValueError:
        print(f"Error: Port must be a number")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nShutting down server...")
        sys.exit(0)
    except ValueError:
        print(f"Error: Port must be a number")
        sys.exit(1)
