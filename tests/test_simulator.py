import unittest

from simulator.app import parse_args


class SimulatorArgumentTests(unittest.TestCase):
    def test_parse_args_accepts_valid_values(self) -> None:
        args = parse_args(["--port", "8001", "--width", "640", "--height", "480", "--fps", "10"])

        self.assertEqual(8001, args.port)
        self.assertEqual(640, args.width)
        self.assertEqual(480, args.height)
        self.assertEqual(10, args.fps)

    def test_parse_args_rejects_invalid_port(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["--port", "0"])

    def test_parse_args_rejects_invalid_dimensions_or_fps(self) -> None:
        for args in (["--width", "-1"], ["--height", "0"], ["--fps", "0"]):
            with self.assertRaises(SystemExit):
                parse_args(list(args))


if __name__ == "__main__":
    unittest.main()
