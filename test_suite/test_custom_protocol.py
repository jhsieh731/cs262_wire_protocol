import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from custom_protocol import CustomProtocol

class TestCustomProtocol(unittest.TestCase):
    def test_simple_dict(self):
        data = {"name": "Alice"}
        serialized = CustomProtocol.serialize(data)
        self.assertEqual(CustomProtocol.deserialize(serialized), data)

    def test_nested_dict(self):
        data = {"user": {"name": "Bob", "age": 25}}
        serialized = CustomProtocol.serialize(data)
        self.assertEqual(CustomProtocol.deserialize(serialized), data)

    def test_list_serialization(self):
        data = {"scores": [95, 88, 76]}
        serialized = CustomProtocol.serialize(data)
        self.assertEqual(CustomProtocol.deserialize(serialized), data)
    
    def test_nested_list_dict(self):
        data = {"students": [{"name": "Alice"}, {"name": "Bob"}]}
        serialized = CustomProtocol.serialize(data)
        self.assertEqual(CustomProtocol.deserialize(serialized), data)
    
    def test_special_characters(self):
        data = {"quote": 'She said, "Hello!"'}
        serialized = CustomProtocol.serialize(data)
        expected = '{quote:"She said, \"Hello!\""}'
        self.assertEqual(CustomProtocol.deserialize(serialized), data)
    
    def test_boolean_and_null(self):
        data = {"active": True, "deleted": False, "missing": None}
        serialized = CustomProtocol.serialize(data)
        self.assertEqual(CustomProtocol.deserialize(serialized), data)
    
    def test_number_formats(self):
        data = {"int": 42, "float": 3.14159, "negative": -7}
        serialized = CustomProtocol.serialize(data)
        self.assertEqual(CustomProtocol.deserialize(serialized), data)
    
    def test_empty_dict_and_list(self):
        data = {"empty_dict": {}, "empty_list": []}
        serialized = CustomProtocol.serialize(data)
        self.assertEqual(CustomProtocol.deserialize(serialized), data)

    def test_bad_data(self):
        data = "bad data"
        with self.assertRaises(AttributeError):
            CustomProtocol.deserialize(data)

    # assume if serialize/deserialize are correct then their helper functions are correct
    # the checksum function is a sum and mod (basic op, not testing)

        
    
if __name__ == "__main__":
    unittest.main()
