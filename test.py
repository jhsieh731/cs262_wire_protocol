from custom_protocol import CustomProtocol

protocol = CustomProtocol()




# Example Usage
data = {
    "name": "Alice",
    "age": 30,
    "scores": [95, 88, 76],
    "details": {
        "height": 5.5,
        "hobbies": ["reading[abd]{asdf}", "cycling"],
        "more": [{"a": 1}, {"b": 2}]
    },
    "active": True,
    "id": None
}

serialized = protocol.serialize(data)
print("Serialized:", serialized)

unserialized = protocol.deserialize(serialized)
print("Unserialized:", unserialized)

assert unserialized == data  # Ensures correctness
