import unittest

from worker_protocol import WorkerConfig


class WorkerConfigTests(unittest.TestCase):
    def test_accepts_valid_runtime_config(self) -> None:
        config = WorkerConfig(
            width=64,
            height=64,
            interval_ms=1,
            mvp_threshold=18.0,
            auto_save=True,
            send_image=True,
        )

        self.assertIs(config.validated(), config)

    def test_rejects_more_than_supported_image_bounds(self) -> None:
        config = WorkerConfig(
            width=5000,
            height=64,
            interval_ms=1,
            mvp_threshold=18.0,
            auto_save=True,
            send_image=True,
        )

        with self.assertRaises(ValueError):
            config.validated()

    def test_rejects_invalid_threshold(self) -> None:
        config = WorkerConfig(
            width=64,
            height=64,
            interval_ms=1,
            mvp_threshold=101.0,
            auto_save=True,
            send_image=True,
        )

        with self.assertRaises(ValueError):
            config.validated()


if __name__ == "__main__":
    unittest.main()
