# Wire Protocol

Client actions:
- Create account: prompt for username
    - taken: Login
    - not taken: get password & encrypt
- Login: prompt for username and password (encrypted)
- List accounts (top $n$)
    - Filter accounts
- Send message
- Read message
- Delete message(s)
- Delete account

## Log
2/3/25: Took boilerplate multi-client code from https://realpython.com/python-sockets/#multi-connection-client-and-server
- Thoughts: application level wire protocol should  include a header in UTF-8
    - version num | length | operation
    - server and client have different parsers for operations?

- added tkinter to client using chatgpt