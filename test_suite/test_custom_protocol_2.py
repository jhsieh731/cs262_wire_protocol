import unittest
from custom_protocol_2 import CustomProtocol

# to run: python3 -m unittest test_suite/test_custom_protocol_2.py -v

class TestCustomProtocol(unittest.TestCase):
    def setUp(self):
        """Set up a CustomProtocol instance for each test."""
        self.protocol = CustomProtocol()

    def test_compute_checksum(self):
        """Test checksum computation."""
        # Test empty data
        self.assertEqual(CustomProtocol.compute_checksum(b""), 0)
        
        # Test known data
        self.assertEqual(CustomProtocol.compute_checksum(b"test"), 448 % 256)
        
        # Test large data
        large_data = b"x" * 1000
        self.assertEqual(CustomProtocol.compute_checksum(large_data), (120 * 1000) % 256)

    def test_serialize_part_primitives(self):
        """Test serialization of primitive data types."""
        # Test string serialization
        self.assertEqual(CustomProtocol.serialize_part("hello"), '"hello"')
        self.assertEqual(CustomProtocol.serialize_part('test"quote"'), '"test\\"quote\\""')
        
        # Test number serialization
        self.assertEqual(CustomProtocol.serialize_part(42), "42")
        self.assertEqual(CustomProtocol.serialize_part(3.14), "3.14")
        
        # Test boolean serialization
        self.assertEqual(CustomProtocol.serialize_part(True), "true")
        self.assertEqual(CustomProtocol.serialize_part(False), "false")
        
        # Test None serialization
        self.assertEqual(CustomProtocol.serialize_part(None), "null")

    def test_serialize_part_complex(self):
        """Test serialization of complex data types."""
        # Test list serialization
        self.assertEqual(CustomProtocol.serialize_part([1, "two", True]), '[1,"two",true]')
        
        # Test dict serialization
        test_dict = {"name": "John", "age": 30}
        result = CustomProtocol.serialize_part(test_dict)
        # Since dictionary order is not guaranteed, check both possible orderings
        self.assertTrue(
            result == '{age:30,name:"John"}' or 
            result == '{name:"John",age:30}'
        )
        
        # Test nested structures
        nested = {"data": [1, {"x": 2}]}
        self.assertEqual(CustomProtocol.serialize_part(nested), '{data:[1,{x:2}]}')

    def test_serialize(self):
        """Test full dictionary serialization."""
        test_data = {
            "action": "test",
            "message": "hello",
            "uuid": "123"
        }
        # Only fields in self.keys should be included and in order
        expected = b'["test","hello","123"]'  # Assuming these fields are in self.keys
        result = self.protocol.serialize(test_data)
        self.assertEqual(result, expected)

    def test_deserialize_part_primitives(self):
        """Test deserialization of primitive data types."""
        # Test string deserialization
        self.assertEqual(CustomProtocol.deserialize_part('"hello"'), "hello")
        self.assertEqual(CustomProtocol.deserialize_part('"test\\"quote\\""'), 'test"quote"')
        
        # Test number deserialization
        self.assertEqual(CustomProtocol.deserialize_part("42"), 42)
        self.assertEqual(CustomProtocol.deserialize_part("3.14"), 3.14)
        
        # Test boolean deserialization
        self.assertEqual(CustomProtocol.deserialize_part("true"), True)
        self.assertEqual(CustomProtocol.deserialize_part("false"), False)
        
        # Test None deserialization
        self.assertEqual(CustomProtocol.deserialize_part("null"), None)

    def test_deserialize_part_complex(self):
        """Test deserialization of complex data types."""
        # Test list deserialization
        self.assertEqual(
            CustomProtocol.deserialize_part('[1,"two",true]'),
            [1, "two", True]
        )
        
        # Test dict deserialization
        self.assertEqual(
            CustomProtocol.deserialize_part('{name:"John",age:30}'),
            {"name": "John", "age": 30}
        )
        
        # Test nested structures
        self.assertEqual(
            CustomProtocol.deserialize_part('{data:[1,{x:2}]}'),
            {"data": [1, {"x": 2}]}
        )

    def test_deserialize(self):
        """Test full message deserialization."""
        # Test login_register action
        login_data = b'["password123","testuser"]'
        expected = {
            "password": "password123",
            "username": "testuser"
        }
        result = self.protocol.deserialize(login_data, "login")
        self.assertEqual(result, expected)
        
        # Test invalid action
        result = self.protocol.deserialize(login_data, "invalid_action")
        self.assertEqual(result, {})
        
        # Test mismatched field count
        result = self.protocol.deserialize(b'["single_value"]', "login_register")
        self.assertEqual(result, {})

    def test_parse_dict(self):
        """Test parsing of dictionary from serialized string."""
        # Test empty dictionary
        self.assertEqual(CustomProtocol._parse_dict(""), {})
        
        # Test simple key-value pairs
        self.assertEqual(
            CustomProtocol._parse_dict('name:"John",age:30'),
            {"name": "John", "age": 30}
        )
        
        # Test nested dictionaries
        self.assertEqual(
            CustomProtocol._parse_dict('user:{name:"John",age:30},active:true'),
            {"user": {"name": "John", "age": 30}, "active": True}
        )
        
        # Test dictionary with list values
        self.assertEqual(
            CustomProtocol._parse_dict('numbers:[1,2,3],names:["John","Jane"]'),
            {"numbers": [1, 2, 3], "names": ["John", "Jane"]}
        )
        
        # Test dictionary with simple keys
        self.assertEqual(
            CustomProtocol._parse_dict('simple:"value",normal:123'),
            {"simple": "value", "normal": 123}
        )
        
        # Test dictionary with quoted keys
        self.assertEqual(
            CustomProtocol._parse_dict('"key:with:colon":"value"'),
            {"key:with:colon": "value"}
        )

    def test_parse_list(self):
        """Test parsing of list from serialized string."""
        # Test empty list
        self.assertEqual(CustomProtocol._parse_list(""), [])
        
        # Test simple values
        self.assertEqual(
            CustomProtocol._parse_list('1,"two",true,null'),
            [1, "two", True, None]
        )
        
        # Test nested lists
        self.assertEqual(
            CustomProtocol._parse_list('1,[2,3],4'),
            [1, [2, 3], 4]
        )
        
        # Test lists with dictionaries
        self.assertEqual(
            CustomProtocol._parse_list('{name:"John"},{name:"Jane"}'),
            [{"name": "John"}, {"name": "Jane"}]
        )
        
        # Test mixed nested structures
        self.assertEqual(
            CustomProtocol._parse_list('1,{x:[2,3]},"test"'),
            [1, {"x": [2, 3]}, "test"]
        )

    def test_split_items(self):
        """Test splitting of serialized items."""
        # Test simple list
        self.assertEqual(
            CustomProtocol._split_items('1,2,3'),
            ['1', '2', '3']
        )
        
        # Test with nested structures
        self.assertEqual(
            CustomProtocol._split_items('1,{a:2,b:3},[4,5]'),
            ['1', '{a:2,b:3}', '[4,5]']
        )
        
        # Test with strings containing delimiters
        self.assertEqual(
            CustomProtocol._split_items('"a,b",{x:1},c'),
            ['"a,b"', '{x:1}', 'c']
        )

    def test_is_number(self):
        """Test number validation."""
        self.assertTrue(CustomProtocol._is_number("42"))
        self.assertTrue(CustomProtocol._is_number("-42"))
        self.assertTrue(CustomProtocol._is_number("3.14"))
        self.assertFalse(CustomProtocol._is_number("abc"))
        self.assertFalse(CustomProtocol._is_number("12.34.56"))

    def test_escape_unescape_key(self):
        """Test key escaping and unescaping."""
        # Test normal keys
        self.assertEqual(CustomProtocol._escape_key("normal"), "normal")
        
        # Test keys with special characters
        self.assertEqual(CustomProtocol._escape_key("key:with:colons"), '"key:with:colons"')
        self.assertEqual(CustomProtocol._escape_key("key,with,commas"), '"key,with,commas"')
        
        # Test unescaping
        self.assertEqual(CustomProtocol._unescape_key('"escaped:key"'), "escaped:key")
        self.assertEqual(CustomProtocol._unescape_key("normal"), "normal")

if __name__ == '__main__':
    unittest.main()
