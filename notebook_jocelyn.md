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
    - if client receives message from server, push notif (delivered) on top
- Delete message(s)
- Delete account

Database:
- Table 1: users (userid, username, hashed password, associated socket)
- Table 2: messages (msgid, senderid, recipient id, message, status [pending, delivered, seen], timestamp)
    - what does it mean to choose how many messages to be delivered at once?

## MESSAGE
Protoheader (fixed length):
- version number
- json header length

Header:
- content length
- action
- (note: encoding is always UTF-8)

## Log
2/3/25: Took boilerplate multi-client code from https://realpython.com/python-sockets/#multi-connection-client-and-server
- Thoughts: application level wire protocol should  include a header in UTF-8
    - version num | length | operation
    - server and client have different parsers for operations?

- added tkinter to client using chatgpt

2/4/25: Rewrote client Message class to use the wire protocol outlined above (JSON format), still need to keep the socket open so that Messages can be edited & sent over the same socket as long as the user is logged in. Maybe we should not call it a Message, since it persists?

2/5/25: Added UI interface to create account/login. Would love to add a temporary dictionary storing mappings to active soccets/userids, but need to somehow bypass my message object

2/6/25-2/9/25: Oops! I literally had the flu and a high grade fever, but don't worry I still made progress on this project because the grind never stops (even on your deathbed). Hooray. 


jsonheader: 
"version"
"content-length"
"action"


actions: 
"load_page_data"
"search_accounts"
"delete_messages"
"load_undelivered"
"load_messages"
"send_message"
"login_register"
"delete_account"


content:
"uuid"
"search_term"
"current_page"
"msgids"
"num_messages"
"sender_uuid"
"recipient_username"
"message"
"timestamp"
"username"
"password"


Should we forcibly try to determine whether an incoming request is json or custom & then match it? 


add-ons:
- We should probably use "action" in our server messages instead of response-type but lowkey that's a lot of work