import unittest

from opengarage.errors import (OpenGarageError, ResponseError, TransportError,
                               UnsupportedFeatureError)


class TestErrors(unittest.TestCase):
    def test_error_hierarchy(self):
        self.assertTrue(issubclass(TransportError, OpenGarageError))
        self.assertTrue(issubclass(ResponseError, OpenGarageError))
        self.assertTrue(issubclass(UnsupportedFeatureError, OpenGarageError))

    def test_response_error_fields(self):
        err = ResponseError(status=500, url="http://example/jc")
        self.assertEqual(err.status, 500)
        self.assertEqual(err.url, "http://example/jc")
        self.assertIn("500", str(err))

    def test_unsupported_feature_message(self):
        err = UnsupportedFeatureError("Light control not supported")
        self.assertIn("Light control", str(err))


if __name__ == "__main__":
    unittest.main()
