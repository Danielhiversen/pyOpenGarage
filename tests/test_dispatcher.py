import unittest

from opengarage.dispatcher import CommandDispatcher


class TestCommandDispatcher(unittest.TestCase):
    def test_build_command(self):
        command = CommandDispatcher.build_command("open", "abc123")
        self.assertEqual(command, "cc?dkey=abc123&open=1")

    def test_invalid_action_raises(self):
        with self.assertRaises(ValueError):
            CommandDispatcher.build_command("invalid", "abc123")


if __name__ == "__main__":
    unittest.main()
