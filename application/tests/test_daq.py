from PySide2.QtCore import QObject, Signal
import numpy as np
from numpy.testing import assert_equal

import topside as top
from ..daq import trim_earlier, DAQBridge
from ..plumbing_bridge import PlumbingBridge


class MockPlumbingBridge(QObject):
    dataUpdated = Signal(dict, int)
    engineLoaded = Signal(top.PlumbingEngine)

    def __init__(self):
        QObject.__init__(self)


def test_trim_earlier():
    arr = np.array([1, 2, 3, 4, 5])

    assert_equal(trim_earlier(arr, 2.5), [3, 4, 5])
    assert_equal(trim_earlier(arr, 4), [4, 5])
    assert_equal(trim_earlier(arr, 6), [])

    assert_equal(trim_earlier(np.array([]), 10), [])


def test_daq_bridge_add_remove():
    m = DAQBridge(MockPlumbingBridge())

    m.addChannel('p1')
    m.addChannel('p2')
    m.removeChannel('p1')

    assert 'p1' not in m.data_values
    assert_equal(m.data_values['p2'], [])


def test_daq_model_update():
    m = DAQBridge(MockPlumbingBridge())

    m.addChannel('p1')
    m.addChannel('p2')

    m.update({
        'p1': np.array([10, 11]),
        'p2': np.array([20, 21]),
        'p3': np.array([30, 31])  # should be ignored
    }, np.array([5e6, 6e6]))

    assert_equal(m.times, [5, 6])
    assert_equal(m.data_values['p1'], [10, 11])
    assert_equal(m.data_values['p2'], [20, 21])


def test_daq_model_update_rollover():
    m = DAQBridge(MockPlumbingBridge())

    m.addChannel('p1')
    m.addChannel('p2')

    m.update({
        'p1': np.array([10, 11, 12, 13]),
        'p2': np.array([20, 21, 22, 23])
    }, np.array([5e6, 10e6, 15e6, 20e6]))

    assert_equal(m.times, [10, 15, 20])
    assert_equal(m.data_values['p1'], [11, 12, 13])
    assert_equal(m.data_values['p2'], [21, 22, 23])


def test_daq_model_update_earlier_time():
    m = DAQBridge(MockPlumbingBridge())

    m.addChannel('p1')
    m.addChannel('p2')

    m.update({
        'p1': np.array([10, 11, 12, 13]),
        'p2': np.array([20, 21, 22, 23])
    }, np.array([10e6, 11e6, 12e6, 13e6]))

    m.update({
        'p1': np.array([14, 15, 16, 17]),
        'p2': np.array([24, 25, 26, 27])
    }, np.array([5e6, 6e6, 7e6, 8e6]))

    assert_equal(m.times, [5, 6, 7, 8])
    assert_equal(m.data_values['p1'], [14, 15, 16, 17])
    assert_equal(m.data_values['p2'], [24, 25, 26, 27])
