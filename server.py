import sys
import socket
import selectors
import logging
from msg_server import Message
import json
from logger import set_logger

logger = set_logger("server", "server.log")
sel = selectors.DefaultSelector()

def initialize_server(host, port):
    """Initialize the server with the given host and port."""
    try:
        lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Allow reuse of address
        lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            lsock.bind((host, port))
        except OSError as e:
            logger.error(f"Error binding to {host}:{port} - {e}")
            logger.error("Try using a different port number.")
            lsock.close()
            sys.exit(1)
        lsock.listen()
        logger.info(f"Listening on {(host, port)}")
        lsock.setblocking(False)
        sel.register(lsock, selectors.EVENT_READ, data=None)
        return lsock
    except Exception as e:
        logger.error(f"Error initializing server: {e}")
        sys.exit(1)

def accept_wrapper(sock, accepted_versions, protocol):
    """Accept a new connection and register it with the selector."""
    conn, addr = sock.accept()  # Should be ready to read
    logger.info(f"Accepted connection from {addr}")
    conn.setblocking(False)
    message = Message(sel, conn, addr, accepted_versions, protocol)
    sel.register(conn, selectors.EVENT_READ, data=message)


def run_server(accepted_versions, protocol):
    """Run the server event loop."""
    try:
        while True:
            events = sel.select(timeout=None)
            for key, mask in events:
                if key.data is None:
                    accept_wrapper(key.fileobj, accepted_versions, protocol)
                else:
                    message = key.data
                    try:
                        message.process_events(mask)
                    except Exception as e:
                        logger.error(f"Error processing events for {message.addr}: {e}")
                        message.close()
    except KeyboardInterrupt:
        logger.info("\nCaught keyboard interrupt, shutting down...")
    except Exception as e:
        logger.info(f"\nError in server: {e}")
    finally:
        logger.info("Closing all connections...")
        # Close all open sockets
        for key in list(sel.get_map().values()):
            sel.unregister(key.fileobj)
            key.fileobj.close()
        sel.close()


def main():
    """Main function to run the server."""
    try:
        # load config.json
        with open('config.json', 'r') as f:
            config = json.load(f)
        host = config['host']
        port = config['port']
        protocol = config['protocol']
        accepted_versions = config['accepted_versions']
        
        # Convert port to int if it's a string
        try:
            port = int(port)
        except (TypeError, ValueError):
            print("Error: Port must be a number")
            sys.exit(1)
            
        if port < 1024 and port != 0:  # Avoid privileged ports
            print("Error: Please use a port number >= 1024")
            sys.exit(1)
            
        lsock = initialize_server(host, port)
        run_server(accepted_versions, protocol)
    except json.JSONDecodeError as e:
        logger.error(f"Error reading config file: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\nShutting down server...")
        sys.exit(0)

if __name__ == '__main__':
    main()
