from database import MessageDatabase

def view_all_messages():
    db = MessageDatabase()
    messages = db.get_messages("", "")  # This will show messages where server1 is sender or receiver
    
    print("\nAll messages in database:")
    print("-" * 80)
    print(f"{'Sender':15} | {'Receiver':15} | {'Message':30} | {'Timestamp'}")
    print("-" * 80)
    
    for msg in messages:
        sender, receiver, message, status, timestamp = msg
        # Handle content whether it's bytes or string
        if isinstance(message, bytes):
            message = message.decode('utf-8')
        print(f"{sender:15} | {receiver:15} | {status:15} | {str(message)[:30]:30} | {timestamp}")

if __name__ == "__main__":
    view_all_messages()
