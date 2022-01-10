# -*- coding: utf-8 -*-
"""
Created on Mon Nov 15 21:55:32 2021

@author: Dell
"""


class CorrelationStatistics:
    def __init__(self, coin, strongest_minute, slope, intercept, r_value, p_value, std_err, change_at_3sd, datapoints, timestamp):
        self.coin = coin
        self.strongest_minute = strongest_minute
        self.slope = slope
        self.intercept = intercept
        self.r_value = r_value
        self.p_value = p_value
        self.std_err = std_err
        self.change_at_3sd = change_at_3sd
        self.datapoints = datapoints
        self.timestamp = timestamp
