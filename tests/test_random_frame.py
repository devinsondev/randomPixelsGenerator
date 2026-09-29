import unittest

import numpy as np

from random_frame import derive_frame_seed, generate_rgb_frame


class RandomFrameTests(unittest.TestCase):
    def test_frame_seed_is_reproducible_and_frame_specific(self) -> None:
        first = derive_frame_seed(worker_seed=123, frame_index=1)
        repeated = derive_frame_seed(worker_seed=123, frame_index=1)
        second = derive_frame_seed(worker_seed=123, frame_index=2)

        self.assertEqual(first, repeated)
        self.assertNotEqual(first, second)

    def test_frame_can_be_reproduced_from_frame_seed(self) -> None:
        seed = derive_frame_seed(worker_seed=987, frame_index=42)

        first = generate_rgb_frame(16, 12, seed)
        second = generate_rgb_frame(16, 12, seed)

        np.testing.assert_array_equal(first, second)


if __name__ == "__main__":
    unittest.main()
