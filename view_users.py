from database import MessageDatabase
from tabulate import tabulate

def view_users():
    # Create database connection
    db = MessageDatabase()
    conn = db.connect()
    
    if conn is not None:
        try:
            cursor = conn.cursor()
            # Get all users from the users table
            cursor.execute("SELECT userid, username, associated_socket FROM users")
            users = cursor.fetchall()
            
            if users:
                # Create headers for the table
                headers = ["User ID", "Username", "Associated Socket"]
                # Use tabulate to create a nice table format
                print("\nUsers Table:")
                print(tabulate(users, headers=headers, tablefmt="grid"))
            else:
                print("\nNo users found in the database.")
                
        except Exception as e:
            print(f"Error retrieving users: {e}")
        finally:
            conn.close()
    else:
        print("Could not connect to the database.")

if __name__ == "__main__":
    view_users()
