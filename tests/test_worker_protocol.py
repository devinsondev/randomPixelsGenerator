import unittest

from worker_protocol import WorkerConfig


def make_config(**overrides) -> WorkerConfig:
    values = {
        "width": 64,
        "height": 64,
        "interval_ms": 1,
        "mvp_threshold": 18.0,
        "auto_threshold": True,
        "top_percent": 0.01,
        "threshold_warmup": 10_000,
        "auto_save": True,
        "send_image": True,
    }
    values.update(overrides)
    return WorkerConfig(**values)


class WorkerConfigTests(unittest.TestCase):
    def test_accepts_valid_runtime_config(self) -> None:
        config = make_config()
        self.assertIs(config.validated(), config)

    def test_rejects_more_than_supported_image_bounds(self) -> None:
        with self.assertRaises(ValueError):
            make_config(width=5000).validated()

    def test_rejects_invalid_threshold(self) -> None:
        with self.assertRaises(ValueError):
            make_config(mvp_threshold=101.0).validated()

    def test_rejects_invalid_top_percent(self) -> None:
        with self.assertRaises(ValueError):
            make_config(top_percent=0.0).validated()

    def test_rejects_too_short_warmup(self) -> None:
        with self.assertRaises(ValueError):
            make_config(threshold_warmup=10).validated()


if __name__ == "__main__":
    unittest.main()
