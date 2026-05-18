from __future__ import annotations

import unittest

import config
from utils.jobs import JOBS, roll_job_payout


class TestJobs(unittest.TestCase):
    def test_payout_multiplier(self) -> None:
        job = JOBS[0]
        payouts = [roll_job_payout(job, payout_mult=1.0) for _ in range(200)]
        low = int(job.payout_min * config.JOB_PAYOUT_MULTIPLIER)
        high = int(job.payout_max * config.JOB_PAYOUT_MULTIPLIER)
        self.assertTrue(all(low <= p <= high for p in payouts))


if __name__ == "__main__":
    unittest.main()
