# High Level Analyzer
# For more information and documentation, please go to https://support.saleae.com/extensions/high-level-analyzer-extensions

from saleae.analyzers import HighLevelAnalyzer, AnalyzerFrame, StringSetting, NumberSetting, ChoicesSetting
import socket
import json
import time
from enum import Enum

class RxState(Enum):
    IDLE = 0
    HEAD_OK = 1
    GOT_LENGTH = 2



class Sts3032Analyser(HighLevelAnalyzer):
    result_types = {
        'packet' : {
            'format': 'ID: {{data.id}}'
        },
        'error' : {
            'format': 'ERROR: {{data.msg}}'
        },
    }

    def __init__(self):
        self.buffer = b' '
        self.rx_state = RxState.IDLE
        self.expected_bytes = 1
        self.start = [None, None]


    def decode(self, frame: AnalyzerFrame):

        if 'error' in frame.data:
            return

        c = frame.data['data']
        self.buffer += c

        ret = None

        if self.rx_state == RxState.IDLE:
            self.start[1] = self.start[0]
            self.start[0] = frame.start_time
            if self.buffer[-1] == 0xFF and self.buffer[-2] == 0xFF:
                self.buffer = self.buffer[-2:]
                self.rx_state = RxState.HEAD_OK
                self.expected_bytes = 2
        elif self.rx_state == RxState.HEAD_OK:
            self.expected_bytes -= 1
            if self.expected_bytes == 0:
                self.rx_state = RxState.GOT_LENGTH
                self.expected_bytes = self.buffer[-1]
        elif self.rx_state == RxState.GOT_LENGTH:
            self.expected_bytes -= 1
            if self.expected_bytes == 0:
                chk = 255 - (sum(self.buffer[2:-1]) % 256)
                if chk == self.buffer[-1]:
                    ret = AnalyzerFrame('packet', self.start[1], frame.end_time, {'id': self.buffer[2], 'data': self.buffer})
                else:
                    ret = AnalyzerFrame('error', self.start[1], frame.end_time, {'msg': "error",  'data': self.buffer})
                self.buffer = b' '
                self.rx_state = RxState.IDLE
                return ret



