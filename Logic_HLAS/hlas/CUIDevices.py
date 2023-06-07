# High Level Analyzer
# For more information and documentation, please go to https://support.saleae.com/extensions/high-level-analyzer-extensions

from saleae.analyzers import HighLevelAnalyzer, AnalyzerFrame, StringSetting, NumberSetting, ChoicesSetting
import socket
import json
import time


class AMT22Analyser(HighLevelAnalyzer):
    resolution = ChoicesSetting(choices=('12 bits', '14 bits'))
    result_types = {
        'read_pos' : {
            'format': 'Position: {{data.pos}}'
        },
        'reset' : {
            'format': 'Reset'
        },
        'set_zero' : {
            'format': 'Set Zero Point'
        },
        'read_turns' : {
            'format': 'Turns: {{data.turns}}, Position: {{data.pos}}'
        },
        'error' : {
            'format': 'ERROR: {{data.msg}}'
        },
    }

    def __init__(self):
        self.mosi_data = b''
        self.miso_data = b''
        self.start = 0

    def check(self, data):
        rx_even = (data >> 14) & 0x01
        rx_odd = (data >> 15) & 0x01
        odd = 1;
        even = 1;
        for i in range(7):
            even ^= (data>>(2*i)) & 0x01;
            odd  ^= (data>>(2*i+1)) & 0x01;
        return even == rx_even and odd == rx_odd

    def get_value(self, b_arr):
        data = b_arr[0] << 8 | b_arr[1]
        val = data & 0x3fff
        if self.resolution == "12 bits":
            val >>= 2
        return val, self.check(data)

    def decode(self, frame: AnalyzerFrame):
        if frame.type == "enable":
            self.mosi_data = b''
            self.miso_data = b''
            self.start = frame.start_time
        elif frame.type == "result":
            self.mosi_data += frame.data["mosi"]
            self.miso_data += frame.data["miso"]
        elif frame.type == "disable":
            if self.mosi_data == b'\x00\x00':
                # read position
                pos, valid = self.get_value(self.miso_data)
                if valid:
                    return AnalyzerFrame('read_pos', self.start, frame.end_time, {'pos': pos})
                else:
                    return AnalyzerFrame('error', self.start, frame.end_time, {'msg': f"read position: {pos}", 'pos': pos})
            elif self.mosi_data == b'\x00\x60':
                # reset
                return AnalyzerFrame('reset', self.start, frame.end_time, {})
            elif self.mosi_data == b'\x00\x70':
                # set zero point
                return AnalyzerFrame('set_zero', self.start, frame.end_time, {})
            elif self.mosi_data == b'\x00\xa0\x00\x00':
                # read turns
                pos, pos_valid = self.get_value(self.miso_data[:2])
                turns, turns_valid = self.get_value(self.miso_data[2:])
                if pos_valid and turns_valid:
                    return AnalyzerFrame('set_zero', self.start, frame.end_time, {'pos': pos, 'turns': turns})
                else:
                    return AnalyzerFrame('error', self.start, frame.end_time, {'msg': f"read turns: {turns}, position: {pos}", 'pos': pos})
            else:
                return AnalyzerFrame('error', self.start, frame.end_time, {'msg': f"unknown command: {self.mosi_data}"})
