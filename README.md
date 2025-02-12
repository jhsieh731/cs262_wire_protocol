# Client Application Documentation

## Overview

This document provides detailed information on the client-side implementation of a networked chat application using Python. The application includes:

- A GUI built with Tkinter for user interactions, allowing users to send and receive messages in a structured, visually accessible format.
- A network client using sockets and selectors for communication, ensuring seamless data transfer.
- A server-side implementation for managing multiple client connections and message exchanges.
- Secure password handling using SHA-256 hashing, ensuring user data integrity and protection.
- Integration with a database for managing user accounts, messages, and authentication.

## Networking Setup

- `initialize_client(server_host, server_port, input_protocol)`: Initializes the client by setting up a selector for handling network events and establishing communication parameters.
- `start_connection(gui, request)`: Establishes a connection to the server and registers a message handler, allowing bidirectional communication between client and server.
- `network_thread(request)`: Handles incoming network events and processes messages efficiently in a dedicated thread, ensuring non-blocking performance and real-time updates.
- `send_to_server(request)`: Queues and sends messages to the server, ensuring reliability and immediate processing of user requests, including error handling for dropped connections.
- `initialize_server(host, port)`: Initializes the server, sets up a socket for listening, and registers it with the selector to handle incoming client connections efficiently.
- `accept_wrapper(sock)` (on client) or `accept_wrapper(sock, accepted_versions, protocol)` (on server): Accepts a new client connection and registers it for communication, enabling seamless multiple-client interaction with proper session management.
- `run_server()` (on client) or `run_server(accepted_versions, protocol)` (on server): Runs the server event loop, processing incoming connections and messages, ensuring constant availability and proper error handling.

## Message Handling

### Message Class

Handles sending and receiving of structured messages between the client and server, ensuring consistency and security.

#### Attributes

- `selector`: Selector instance for managing network events
- `sock`: Client socket connection
- `addr`: Address of the connected client
- `request`: JSON-formatted request from the client
- `gui`: Reference to the GUI for handling responses
- `_recv_buffer`: Buffer for incoming data, ensuring smooth data retrieval
- `_send_buffer`: Buffer for outgoing data, reducing network congestion
- `protocol_mode`: Defines whether messages are transmitted using JSON or a custom protocol, allowing flexibility in encoding.
- `custom_protocol`: Instance of CustomProtocol for serialization and checksum validation, ensuring message integrity.
- `db`: Instance of MessageDatabase for storing and retrieving messages and user authentication.

#### Methods

- `_set_selector_events_mask(mode)`: Configures event listening mode for the selector.
- `_read()`: Reads data from the socket into the receive buffer, processing partial data if necessary.
- `_write()`: Sends buffered data through the socket, ensuring message completion.
- `_json_encode(obj, encoding)`: Encodes an object into a JSON-formatted byte stream for structured message handling.
- `_json_decode(json_bytes, encoding)`: Decodes a JSON-formatted byte stream into an object, preserving data accuracy.
- `_create_message(content_bytes, action, content_length)`: Constructs a formatted message for transmission, including error handling for malformed data.
- `process_events(mask)`: Handles incoming read/write events based on selector triggers, managing multiple event types.
- `read()`: Reads and processes received messages, verifying data integrity.
- `write()`: Sends buffered messages and manages socket state, ensuring real-time communication.
- `close()`: Closes the socket connection and cleans up resources, preventing memory leaks.
- `queue_request()`: Queues outgoing requests for transmission, handling priority messages efficiently.
- `process_protoheader()`: Extracts message header length from the received data buffer, ensuring message correctness.
- `process_header()`: Parses the message header and extracts metadata, validating message structure.
- `reset_state()`: Resets message state after processing responses, ensuring new messages are handled correctly.
- `process_response()`: Handles incoming responses, verifies checksum (if using a custom protocol), and updates the GUI accordingly.
- `_create_response_content()`: Generates response content based on the received request, integrating database operations.
- `process_request()`: Processes and validates incoming requests, ensuring data consistency.

## GUI Implementation

### ClientGUI Class

This class is responsible for handling the GUI interactions of the client, ensuring a smooth and user-friendly experience.

#### Attributes

- `master`: Root window
- `user_uuid`: Unique identifier for the user, ensuring secure authentication
- `selected_accounts`: Currently selected chat partner, enabling targeted messaging
- `username`: Logged-in user's name, used for personalized interactions
- `current_page`: Tracks pagination for account searching, optimizing performance
- `max_accounts_page`: Maximum available pages, ensuring controlled data loading
- `num_messages`: Number of messages to display, managing message retrieval
- `num_undelivered`: Count of undelivered messages, ensuring prompt delivery
- `msgid_map`: Maps listbox indices to message IDs, ensuring proper message tracking

## Dependencies

The application requires Python 3.6 or higher and uses the following standard library packages:

- `tkinter`: For the graphical user interface
- `socket`: For network communication
- `selectors`: For handling multiple connections
- `threading`: For concurrent operations
- `hashlib`: For password hashing
- `json`: For message serialization
- `struct`: For binary data handling
- `datetime`: For timestamp management

For development and testing, these should all be included natively in the official Python (default Mac version is not sufficient).

## Running the Application

1. Start the server:

   ```bash
   python server.py <host> <port>
   ```

   Where `<host>` is the server's address and `<port>` is the port number (≥ 1024).

2. Start the client:

   ```bash
   python client.py <host> <port> <protocol>
   ```

   Where `<host>` is the server's address and `<port>` is the server's port number.

## Notes

- Ensure that the server is running before launching the client.
- Messages are queued for delivery using a threaded network handler to improve efficiency.
- Error handling is implemented to manage failed logins and server communication issues.
- The server must be started with a valid host and port and must avoid using privileged ports (<1024).
- The application employs SHA-256 hashing to protect user passwords.
- The UI is designed to be intuitive and user-friendly, featuring a structured layout and interactive elements.
- Multi-threading allows simultaneous interactions, preventing lag and blocking issues.
- Search and pagination features ensure efficient management of large datasets, enhancing usability.
- Users can delete their accounts securely with password verification to prevent unauthorized deletions.
- Enhanced security measures, including encryption for sensitive messages, ensuring private communication.
- Logging and debugging features included for troubleshooting network and GUI issues.
