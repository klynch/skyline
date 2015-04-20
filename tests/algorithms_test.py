#!/usr/bin/env python

import unittest
from mock import Mock, patch
from argparse import Namespace
from time import time

import collections
import sys
from os.path import dirname, abspath

from skyline.analyzer import algorithms
from skyline.analyzer.analyzer import Analyzer

class TestAlgorithms(unittest.TestCase):
    """
    Test all algorithms with a common, simple/known anomalous data set
    """

    def data(self, ts):
        """
        Mostly ones (1), with a final value of 1000
        """
        timeseries = list(map(list, zip(map(float, range(int(ts) - 86400, int(ts) + 1)), [1] * 86401)))
        timeseries[-1][1] = 1000
        timeseries[-2][1] = 1
        timeseries[-3][1] = 1
        return ts, timeseries

    def test_tail_avg(self):
        _, timeseries = self.data(time())
        self.assertEqual(algorithms.tail_avg(timeseries, Namespace()), 334)

    def test_grubbs(self):
        _, timeseries = self.data(time())
        self.assertTrue(algorithms.grubbs(timeseries, Namespace()))

    @patch.object(algorithms.time, 'time')
    def test_first_hour_average(self, timeMock):
        timeMock.return_value, timeseries = self.data(time())
        self.assertTrue(algorithms.first_hour_average(timeseries, Namespace(full_duration=86400)))

    def test_stddev_from_average(self):
        _, timeseries = self.data(time())
        self.assertTrue(algorithms.stddev_from_average(timeseries, Namespace()))

    def test_stddev_from_moving_average(self):
        _, timeseries = self.data(time())
        self.assertTrue(algorithms.stddev_from_moving_average(timeseries, Namespace()))

    def test_mean_subtraction_cumulation(self):
        _, timeseries = self.data(time())
        self.assertTrue(algorithms.mean_subtraction_cumulation(timeseries, Namespace()))

    @patch.object(algorithms.time, 'time')
    def test_least_squares(self, timeMock):
        timeMock.return_value, timeseries = self.data(time())
        self.assertTrue(algorithms.least_squares(timeseries, Namespace()))

    def test_histogram_bins(self):
        _, timeseries = self.data(time())
        self.assertTrue(algorithms.histogram_bins(timeseries, Namespace()))

    @patch.object(algorithms.time, 'time')
    @patch('skyline.api.SkylineRedisApi')
    def test_run_selected_algorithm(self, ApiMock, timeMock):
        timeMock.return_value, timeseries = self.data(time())
        args = Namespace(min_tolerable_length=1, stale_period=500, max_tolerable_boredom=100, boredom_set_size=1, full_duration=86400, consensus=6)
        result, ensemble, datapoint = Analyzer(ApiMock(), args).is_anomalous(timeseries, "test.metric")
        self.assertTrue(result)
        self.assertTrue(collections.Counter(ensemble.values())[True] >= 4)
        self.assertTrue(isinstance(datapoint, list))
        self.assertEqual(datapoint[1], 1000)

    @patch.object(algorithms, 'ALGORITHMS')
    @patch.object(algorithms.time, 'time')
    @patch('skyline.api.SkylineRedisApi')
    def test_run_selected_algorithm_runs_novel_algorithm(self, ApiMock, timeMock,
                                                         algorithmsListMock):
        """
        Assert that a user can add their own custom algorithm.

        This mocks out settings.ALGORITHMS and settings.CONSENSUS to use only a
        single custom-defined function (alwaysTrue)
        """
        algorithmsListMock.__iter__.return_value = ['alwaysTrue']
        consensusMock = 1
        timeMock.return_value, timeseries = self.data(time())

        alwaysTrue = Mock(return_value=True)
        args = Namespace(min_tolerable_length=1, stale_period=500, max_tolerable_boredom=100, boredom_set_size=1, full_duration=86400, consensus=1, enable_second_order=False)
        with patch.dict(algorithms.__dict__, {'alwaysTrue': alwaysTrue}):
            result, ensemble, datapoint = Analyzer(ApiMock(), args).is_anomalous(timeseries, "test.metric")


        alwaysTrue.assert_called_with(timeseries, args)
        self.assertTrue(result)
        self.assertEqual(ensemble, {'alwaysTrue': True})
        self.assertEqual(algorithms.tail_avg(timeseries, Namespace()), 334)


if __name__ == '__main__':
    unittest.main()
