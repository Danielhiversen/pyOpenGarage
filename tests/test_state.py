import unittest

from opengarage.state import NormalizedState, normalize_state


class TestStateNormalizer(unittest.TestCase):
    def test_known_door_states(self):
        payload = {"door": 0}
        state = normalize_state(payload)
        self.assertEqual(state.door_state, "closed")

        payload = {"door": 1}
        state = normalize_state(payload)
        self.assertEqual(state.door_state, "open")

        payload = {"door": 2}
        state = normalize_state(payload)
        self.assertEqual(state.door_state, "opening")

        payload = {"door": 3}
        state = normalize_state(payload)
        self.assertEqual(state.door_state, "closing")

        payload = {"door": 4}
        state = normalize_state(payload)
        self.assertEqual(state.door_state, "stopped")

    def test_unknown_door_state(self):
        payload = {"door": 99}
        state = normalize_state(payload)
        self.assertEqual(state.door_state, "unknown")

    def test_optional_fields_and_capabilities(self):
        payload = {
            "door": 1,
            "secv": 2,
            "has_swrx": 1,
            "light": 1,
            "lock": 0,
            "obstruct": 1,
            "nopenings": 42,
            "pemu": 7,
        }
        state = normalize_state(payload)
        self.assertTrue(state.capabilities["security_plus"])
        self.assertTrue(state.capabilities["light_control"])
        self.assertTrue(state.capabilities["lock_control"])
        self.assertTrue(state.capabilities["obstruction"])
        self.assertTrue(state.capabilities["openings_counter"])
        self.assertTrue(state.capabilities["pemu"])
        self.assertEqual(state.nopenings, 42)
        self.assertEqual(state.pemu, 7)

    def test_non_dict_payload_is_safe(self):
        state = normalize_state("not-a-dict")
        self.assertIsInstance(state, NormalizedState)
        self.assertEqual(state.door_state, "unknown")
        self.assertIn("_raw", state.raw)

    def test_invalid_optional_values_and_to_dict(self):
        payload = {
            "door": "not-int",
            "secv": "invalid",
            "has_swrx": "invalid",
            "light": "invalid",
            "lock": "invalid",
            "obstruct": "invalid",
            "nopenings": "invalid",
            "pemu": "invalid",
        }
        state = normalize_state(payload)
        self.assertIsNone(state.door_value)
        self.assertIsNone(state.secv)
        self.assertIsNone(state.has_swrx)
        self.assertIsNone(state.light_on)
        self.assertIsNone(state.lock_engaged)
        self.assertIsNone(state.obstruction)
        self.assertIsNone(state.nopenings)
        self.assertIsNone(state.pemu)

        state_dict = state.to_dict()
        self.assertEqual(state_dict["door_state"], "unknown")
        self.assertIn("capabilities", state_dict)
        self.assertEqual(state_dict["raw"], payload)


if __name__ == "__main__":
    unittest.main()
