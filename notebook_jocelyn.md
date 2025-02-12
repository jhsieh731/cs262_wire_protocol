# Wire Protocol

Client actions:

- Create account: prompt for username
        - taken: Login
        - not taken: get password & encrypt
- Login: prompt for username and password (encrypted)
- List accounts (top $n$): parameter is search substring %xyz% (possibly null), offset
        - Filter accounts
- Send message:
        - client sends senderid, recipientid, content
        - server hit database to find recipientid,
        - try to deliver to the socket
        - log to database (including isdelivered)
- Receive message:
        - if client receives message from server, push notif (delivered) on top?
- Delete message(s)
- Delete account

Database:

- Table 1: users (userid, username, hashed password, associated socket)
- Table 2: messages (msgid, senderid, recipient id, message, status [pending, delivered, seen], timestamp)

## MESSAGE

Protoheader (fixed length):

- version number
- protocol type
- json header length

Header:

- content length
- action
- (note: encoding is always UTF-8)

## Log

2/3/25: Took boilerplate multi-client code from here [https://realpython.com/python-sockets/#multi-connection-client-and-server]

- Thoughts: application level wire protocol should  include a header in UTF-8
        - version num | length | operation
        - server and client have different parsers for operations?
- added tkinter to client using chatgpt

2/4/25:

- Rewrote client Message class to use the wire protocol outlined above (JSON format), still need to keep the socket open so that Messages can be edited & sent over the same socket as long as the user is logged in.

2/5/25:

- Added UI interface to create account/login.

2/6/25-2/9/25: Oops! I literally had the flu and a high grade fever, but don't worry I still made progress on this project because the grind never stops (even on your deathbed). Hooray.

- Wrote implementations for "load_page_data", "delete_messages" "load_undelivered", "load_messages", from gui request to server handling (db hits, etc) to gui serving the response
- Fixed pending/delivered status bug.
- Added button and capability to load more messages in middle column.
- Adding anything to messages triggers a reload so database and client gui are in-sync quite well (num_messages tells server how many messages to load).
- Cleaned msg_server so that anything returning status fields returns "success" (usually Boolean) and "error" (string message).
- Added password hash on the client-side.
- Implemented custom protocol that essentially stringifies dictionary and un-stringifies it in entirety (not great because it is still really chunky; ChatGPT helped with this).
- Some bug fixes on custom protocol.
- Added a timestamp to send messages so ordering is done by client send time, not server process time.
- Bug fix so user can only delete received messages (tkinter does not allow you to set property to make something unselectable, so you only know which ones are deleted at the end--an on select check introduces too much lag).
- Consolidated request/response keys.
- Added version number to json header (changed later to protoheader because it makes more sense at the very very start).
- Changed all client request sends from gui to be threaded to reduce lag.

2/10/25:

- added config file for server, decided not to change how load responses works (so as to reduce response size as you load inevitably more). This is because it would lead to unclear handling of num_messages depending on where you call load_messages. If I have time I might just add another function to resolve this.
- Update timestamps when message status changes to delivered from pending.
- Redesign protocols to remove keys (much smaller).
- Move "response_type" to be "action" instead.
- Separate gui from client file. Refactor _create_response in msg_server (again) for cleaner code.

2/11/25:

- Refactored more code
- database now returns lists to reduce keys being stored in server response, reordered gui file to be better organized.
- added a register sequence to better match the specs.
