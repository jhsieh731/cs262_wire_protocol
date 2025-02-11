class CustomProtocol:
    def __init__(self):
        self.keys = [
            "accounts", # list of dicts
            "action",
            "content-length",
            "checksum",
            "error",
            "message",
            "messages", # list of dicts
            "msgids", # list of ints
            "num_messages",
            "num_pending",
            "offset",
            "password",
            "recipient_username",
            "search_term",
            "sender_username",
            "sender_uuid",
            "success",
            "timestamp",
            "total_count",
            "username",
            "uuid",
        ]
        self.dict_reconstruction = {
            "header": ["action", "content-length", "checksum"],
            "load_page_data": ["uuid"],
            "search_accounts": ["offset", "search_term"],
            "delete_messages": ["msgids"],
            "load_undelivered": ["num_messages", "uuid"],
            "load_messages": ["num_messages", "uuid"],
            "send_message": ["message", "recipient_username", "timestamp", "uuid"],
            "login_register": ["password", "username"],
            "delete_account": ["password", "uuid"],
            "login_error": ["message"],
            "login_register_r": ["uuid"],
            "load_page_data_r": ["accounts", "messages", "num_pending", "total_count"],
            "search_accounts_r": ["accounts", "total_count"],
            "load_messages_r": ["messages", "total_count"],
            "send_message_r": ["error", "success"],
            "receive_message_r": ["message", "sender_username", "sender_uuid"],
            "load_undelivered_r": ["messages"],
            "delete_messages_r": ["total_count"],
            "delete_account_r": ["error", "success"],
            "error": ["error"],
        }


    @staticmethod
    def compute_checksum(data):
        """Computes a simple checksum for the given string of bytes."""
        return sum(data) % 256
    
    @staticmethod
    def serialize_part(data):
        """Stringify data types"""
        if isinstance(data, dict):
            items = [f"{CustomProtocol._escape_key(str(key))}:{CustomProtocol.serialize_part(value)}" for key, value in data.items()]
            return "{" + ",".join(items) + "}"
        elif isinstance(data, list):
            serialized_items = [CustomProtocol.serialize_part(item) for item in data]
            return "[" + ",".join(serialized_items) + "]"
        elif isinstance(data, str):
            return '"' + data.replace('"', '\\"') + '"'  # Escape quotes properly
        elif isinstance(data, bool):  # Handle booleans explicitly
            return "true" if data else "false"
        elif data is None:  # Handle None values
            return "null"
        else:
            return str(data)  # Handles int and float


    def serialize(self, dictionary):
        """Serialize a dictionary to a stringified list."""
        res = []
        for key in self.keys:
            if key in dictionary:
                res.append(CustomProtocol.serialize_part(dictionary[key]))
        res_string = "[" + ",".join(res) + "]"
        return res_string.encode()
    

    @staticmethod
    def deserialize_part(data):
        """Parses a string representation back into original datatype"""
        data = data.strip()

        if data.startswith("{") and data.endswith("}"):
            return CustomProtocol._parse_dict(data[1:-1])
        elif data.startswith("[") and data.endswith("]"):
            return CustomProtocol._parse_list(data[1:-1])
        elif data.startswith('"') and data.endswith('"'):
            return data[1:-1].replace('\\"', '"')  # Unescape quotes
        elif data == "true":
            return True
        elif data == "false":
            return False
        elif data == "null":
            return None
        elif "." in data and data.replace(".", "", 1).isdigit():
            return float(data)
        elif CustomProtocol._is_number(data):
            return int(data)
        else:
            return data  # Should not happen in well-formed input
       

    def deserialize(self, data, action):
        """Deserialize request"""
        # decode from utf-8
        data_string = data.decode("utf-8")

        lst = CustomProtocol.deserialize_part(data_string)
        fields = self.dict_reconstruction.get(action)

        if not fields or len(lst) != len(fields):
            return {}
        # zip fields and list into dict
        return dict(zip(fields, lst))


    @staticmethod
    def _parse_dict(data):
        """Parses a dictionary from a serialized string."""
        result = {}
        items = CustomProtocol._split_items(data)
        for item in items:
            if ":" in item:
                key, value = item.split(":", 1)
                result[CustomProtocol._unescape_key(key)] = CustomProtocol.deserialize_part(value)
        return result

    @staticmethod
    def _parse_list(data):
        """Parses a list from a serialized string."""
        items = CustomProtocol._split_items(data)
        return [CustomProtocol.deserialize_part(item) for item in items]

    @staticmethod
    def _split_items(data):
        """Splits serialized items while handling nested structures."""
        items, stack, current, in_string = [], [], "", False
        for char in data:
            if char == '"':
                in_string = not in_string  # Toggle string mode
            elif not in_string:
                if char in "{[":
                    stack.append(char)
                elif char in "}]":
                    stack.pop()
                elif char == "," and not stack:
                    items.append(current.strip())
                    current = ""
                    continue
            current += char
        if current.strip():
            items.append(current.strip())
        return items
    
    @staticmethod
    def _is_number(value):
        if value.startswith("-"):
                value = value[1:]
        return value.replace(".", "", 1).isdigit()

    @staticmethod
    def _escape_key(key):
        """Escapes dictionary keys to ensure proper serialization."""
        if any(c in key for c in ":{},[]"):
            return f'"{key}"'
        return key

    @staticmethod
    def _unescape_key(key):
        """Unescapes dictionary keys after unserialization."""
        return key[1:-1] if key.startswith('"') and key.endswith('"') else key

