## Wire Protocol
1. Client Action -> create account
    Type -> isUsernameUnique
    Parameters -> username
    Server Action ->
        - If username unique, prompt for password and create new account
            Parameters -> username, hashed password
        - If username not unique, prompt for password and login
2. Client Action -> login
    Type -> login
    Parameters -> username, hashed password
    Server Action ->
        - If username and password match, login and show chat page
            Type -> displayUnreadMessages
            Parameters -> username, timestamp
        - If username and password do not match, show error
3. Client Action -> list accounts
    Type -> listAccounts
    Parameters -> search term, offset
    Server Action ->
        - Hit database
        - Filter accounts based on search term (username contains search term)
        - Return list of account usernames
        - Allow pagination
4. Client Action -> send message
    Type -> sendMessage
    Parameters -> senderid, recipientid, message, timestamp
    (QUESTION: what does it mean to specify the number of messages to be delivered at once?)
    Server Action ->
        - If recipient is logged in, deliver immediately
        - If recipient is not logged in, store message for delivery when recipient logs in
5. Client Action -> delete message
    Server Action ->
        - If message is not deleted, show error
        - If message is deleted, remove from database and notify client
6. Client Action -> delete account
    Server Action ->
        - If account is deleted, remove from user table in database and close socket
        - If account is not deleted, show error
7. Client Action -> check inbox
    Type -> checkInbox
    Parameters -> userid
    Server Action ->
        - Show messages delivered while user was offline
8. Client Action -> read message
    Type -> readMessage
    Parameters -> userid, messageid, showChatLimit
    Server Action ->
        - Update message status to seen
        - Only show messages within showChatLimit

TODO: Add protocol type to JSON header
TODO: Make contact page - list all accounts
TODO: Add search bar to contact page
TODO: Make inbox page look like email inbox
TODO: Setup db with new table
TODO: Add action cases in _create_response_json_content in msg_server.py
TODO: Login/Create account page

## Database Table Schemas
- users (userid, username, hashed password, associated socket)
- messages (msgid, senderid, recipient id, message, status [pending, delivered, seen], timestamp)

DESIGN CONSIDERATION: How should we implement showing unread messages while still allowing users to specify how many messages to be delivered at once?
Option 1: Show all unread messages without preview. Allow users to specify how many messages to read at once. "Read" here will mean "delivered". Can that assumption be made?
Option 2: Show only a number of unread messages at once. Show the total number of unread messages in the inbox and prompt users for how many messages to read at once. "Read" here will mean "seen".

## Debugging
2/5
    - Bug in _write in msg_server.py. Need to reset the states and properties of Message and switch back to read mode after sending the response.
    - I'm attempting to simulate listing all accounts when I realize that we aren't populating the Message object when receiving a request in write mode. Is this ok?
    - According to msg_server.py, "action" is in the JSONheader. Is this consistent throughout the project?
    - In client.py start_connection, message is initialized with JSONheader?
2/7
    - How to not send password as plaintext? I attempted to salt it before sending it over and storing salted password in the database but I'm unable to login after because salting is not determinate. What's the best way to encrypt password?
    - We shouldn’t send them as plaintext but since we’re serializing it anyway, does that matter?
2/8
    - Substring match doesn't work -- only prefix match. Since this is how it works in contacts (default phone app), is that fine?

QUESTION: Is it true that the socket should only be open for one transaction at a time then close?

DESIGN CONSIDERATION: When listing all accounts, should we paginate or inifinite scroll?
Paginate:
    Pro:
        - Smaller packets
        - Maybe faster
    Con:
        - More complex sql query and need to keep track of offset in client gui
Infinite scroll:
    Pro:
        - No need to keep track of offset in client gui
        - Simpler sql query
    Con:
        - Larger packet weight

TODO: On server side, check server number. If server doesn’t match, return error
TODO: On server side, if error parsing data, return the packet

TODO: Demo (5-10 minutes)
TODO: Code walkthrough (10 minutes)
TODO: Code review (10 minutes)
    On Friday 2/14, turn in:
        Code, tests, docs
        Engineering notebooks
    On Sunday 2/16, turn in:
        Review for each of the other groups
        Grade of 1-5

## Demo Script

There should be two existing users, "existing_user_1" and "existing_user_2", in the db

1. Client 1: Log in as existing_user_1
2. Client 1: Send message to existing_user_2
3. Client 2: Log in as existing_user_2
4. Client 2: See undelivered message
5. Client 2: Delete message
6. Client 2: Delete account
7. Client 3: Create account as user_3
8. Client 1: Send message to user_3