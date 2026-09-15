import unittest

from opengarage.dispatcher import CommandDispatcher


class TestCommandDispatcher(unittest.TestCase):
    def test_build_command(self):
        command = CommandDispatcher.build_command("open", "abc123")
        self.assertEqual(command, "cc?dkey=abc123&open=1")

    def test_build_command_light_uses_toggle(self):
        command = CommandDispatcher.build_command("light", "abc123")
        self.assertEqual(command, "cc?dkey=abc123&light=toggle")

    def test_build_command_lock_uses_toggle(self):
        command = CommandDispatcher.build_command("lock", "abc123")
        self.assertEqual(command, "cc?dkey=abc123&lock=toggle")

    def test_build_command_url_encodes_devkey_special_chars(self):
        command = CommandDispatcher.build_command("open", "a&b=c")
        self.assertEqual(command, "cc?dkey=a%26b%3Dc&open=1")

    def test_invalid_action_raises(self):
        with self.assertRaises(ValueError):
            CommandDispatcher.build_command("invalid", "abc123")


if __name__ == "__main__":
    unittest.main()
