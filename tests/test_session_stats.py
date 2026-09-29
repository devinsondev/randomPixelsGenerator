import unittest

from session_stats import ScoreStats


class ScoreStatsTests(unittest.TestCase):
    def test_tracks_average_maximum_and_top_scores(self) -> None:
        stats = ScoreStats(top_size=3)

        stats.record(1, 2.0)
        stats.record(2, 8.0)
        stats.record(3, 4.0)
        stats.record(4, 6.0)

        self.assertEqual(stats.count, 4)
        self.assertAlmostEqual(stats.average, 5.0)
        self.assertIsNotNone(stats.maximum)
        self.assertEqual(stats.maximum.frame_index, 2)
        self.assertEqual(stats.maximum.score, 8.0)
        self.assertEqual(
            [(item.frame_index, item.score) for item in stats.top],
            [(2, 8.0), (4, 6.0), (3, 4.0)],
        )


if __name__ == "__main__":
    unittest.main()
