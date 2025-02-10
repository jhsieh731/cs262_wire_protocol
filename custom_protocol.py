class CustomProtocol:
    # compute checksum
    @staticmethod
    def compute_checksum(data):
        """Computes a simple checksum for the given string of bytes."""
        return sum(data) % 256

    @staticmethod
    def serialize_part(data):
        """Converts a dictionary with nested lists/dictionaries into a string representation."""
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

    @staticmethod
    def serialize(data):
        """Converts a dictionary with nested lists/dictionaries into a string representation."""
        # encode data
        data_string = CustomProtocol.serialize_part(data)
        return data_string.encode()
    
    @staticmethod
    def deserialize_part(data):
        """Parses a string representation back into a dictionary with nested lists/dictionaries."""
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
       

    @staticmethod
    def deserialize(data):
        """Parses a string representation back into a dictionary with nested lists/dictionaries."""
        # decode from utf-8
        data_string = data.decode("utf-8")
        return CustomProtocol.deserialize_part(data_string)

    @staticmethod
    def _parse_dict(data):
        """Parses a dictionary from a serialized string."""
        result = {}
        items = CustomProtocol._split_items(data, is_dict=True)
        for item in items:
            if ":" in item:
                key, value = item.split(":", 1)
                result[CustomProtocol._unescape_key(key)] = CustomProtocol.deserialize_part(value)
        return result

    @staticmethod
    def _parse_list(data):
        """Parses a list from a serialized string."""
        items = CustomProtocol._split_items(data, is_dict=False)
        return [CustomProtocol.deserialize_part(item) for item in items]

    @staticmethod
    def _split_items(data, is_dict):
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

