#!/usr/bin/python3
from serial import Serial
from serial.threaded import Protocol, ReaderThread
import time
import struct
from enum import Enum
from threading import Event


class RxState(Enum):
    IDLE = 0
    HEAD_OK = 1
    GOT_LENGTH = 2


class Instruction(Enum):
    PING = 0x01
    READ_DATA = 0x02
    WRITE_DATA = 0x03
    REGWRITE_DATA = 0x04
    ACTION = 0x05
    SYNCWRITE_DATA = 0x83
    RESET = 0x06

class Regs(Enum):
    ID = 5
    RESPONSE_LEVEL = 8
    MAX_TORQUE = 16
    TARGET_POS = 42
    LOCK_FLAG = 55
    CURRENT_POS = 56
    CURRENT_LOAD = 60


class STSProtocol(Protocol):
    """
    Attributes:
        persistent_settings     set to True to keep changes made to the eprom after power down
    """

    def __init__(self) -> None:
        super().__init__()
        self.persistent_settings = False
        self.transport = None
        self.e = Event()
        self._msg_sent = b''
        self._msg_sent_id = {}
        self._msg_rcv = b''
        self._buffer = b'  '
        self._rx_state = RxState.IDLE
        self._expected_bytes = 1
        self.pos = {}
        self.load = {}

    def connection_made(self, transport):
        self.transport = transport
    
    def _persistent(func):
        def inner(self, id, *args, **kwargs):
            if self.persistent_settings:
                self.lock_eprom(id, 0)
                time.sleep(0.01)
            func(self, id, *args, **kwargs)
            if self.persistent_settings:
                time.sleep(0.01)
                self.lock_eprom(id, 1)

        return inner
    
    def data_received(self, data):
        for c in data:
            if self._decode(c.to_bytes(1, 'little')):
                if self._msg_rcv == self._msg_sent:
                    # echo
                    pass
                else:
                    # print('msg:', self.msg_rcv)
                    id = self._msg_rcv[2]
                    state = self._msg_rcv[4]
                    p_len = self._msg_rcv[3] - 2
                    params = self._msg_rcv[5:5+p_len]
                    if state != 0:
                        print(f"id {id}: state={state}")
                    if id in self._msg_sent_id:
                        if self._msg_sent_id[id][4] == Instruction.PING.value:
                            print(f"PONG from {id} with state= {state}")
                        elif self._msg_sent_id[id][4] == Instruction.READ_DATA.value:
                            addr = self._msg_sent_id[id][5]
                            self._handle_read(id, addr, params)   
    
    def _decode(self, c):
        ret = False
        self._buffer += c
        if self._rx_state == RxState.IDLE:
            if self._buffer[-1] == 0xFF and self._buffer[-2] == 0xFF:
                self._buffer = self._buffer[-2:]
                self._rx_state = RxState.HEAD_OK
                self._expected_bytes = 2
        elif self._rx_state == RxState.HEAD_OK:
            self._expected_bytes -= 1
            if self._expected_bytes == 0:
                self._rx_state = RxState.GOT_LENGTH
                self._expected_bytes = self._buffer[-1]
        elif self._rx_state == RxState.GOT_LENGTH:
            self._expected_bytes -= 1
            if self._expected_bytes == 0:
                chk = 255 - (sum(self._buffer[2:-1]) % 256)
                if chk == self._buffer[-1]:
                    ret = True
                    self._msg_rcv = self._buffer
                else:
                    print('error')
                self._buffer = b' '
                self._rx_state = RxState.IDLE
        return ret


    def _send(self, id: int, data: bytearray):
        msg = b'\xff\xff'
        msg += struct.pack('<BB', id, len(data)+1)
        msg += data
        chk = 255 - sum(msg[2:]) & 0xFF
        msg += struct.pack('<B', chk)
        self._msg_sent = msg
        self._msg_sent_id[id] = msg
        self.transport.write(msg)
    
    def _handle_read(self, id, addr, params):
        if addr == Regs.CURRENT_POS.value:
            pos = params[1]<<8 | params[0]
            self.pos[id] = pos
            self.e.set()
        elif addr == Regs.CURRENT_LOAD.value:
            load = params[1]<<8 | params[0]
            self.load[id] = load
            self.e.set()
        else:
            print(f"{addr}: {params}")
    

    def ping(self, id):
        data = struct.pack('<B', Instruction.PING.value)
        self._send(id, data)
    
    def move(self, id: int, pos: int):
        data = struct.pack('<BBH', Instruction.WRITE_DATA.value, Regs.TARGET_POS.value, pos)
        self._send(id, data)
    
    
    def read_pos(self, id, timeout=0.2):
        data = struct.pack('<BBB', Instruction.READ_DATA.value, Regs.CURRENT_POS.value, 2)
        self._send(id, data)
        self.e.clear()
        if self.e.wait(timeout):
            return self.pos[id]
    
    def read_load(self, id, timeout=0.2):
        data = struct.pack('<BBB', Instruction.READ_DATA.value, Regs.CURRENT_LOAD.value, 2)
        self._send(id, data)
        self.e.clear()
        if self.e.wait(timeout):
            return self.load[id]

    def lock_eprom(self, id: int, lock: int):
        data = struct.pack('<BBB', Instruction.WRITE_DATA.value, Regs.LOCK_FLAG.value, lock)
        self._send(id, data)

    @_persistent
    def set_id(self, id: int, new_id: int):
        data = struct.pack('<BBB', Instruction.WRITE_DATA.value, Regs.ID.value, new_id)
        self._send(id, data)
    
    @_persistent
    def set_response_level(self, id, level):
        data = struct.pack('<BBB', Instruction.WRITE_DATA.value, Regs.RESPONSE_LEVEL.value, level)
        self._send(id, data)
    
    @_persistent
    def set_max_torque(self, id: int, torque: int):
        data = struct.pack('<BBH', Instruction.WRITE_DATA.value, Regs.MAX_TORQUE.value, torque)
        self._send(id, data)
    
    # def connection_lost(self, exc):
    #     ...

def get_sts(port, baurate=1000000):
    ser = Serial(port, baurate)
    t = ReaderThread(ser, STSProtocol)
    t.start()
    transport, sts = t.connect()
    return sts

if __name__ == "__main__":
    ser = Serial("/dev/bmp-serial", 1000000)
    with ReaderThread(ser, STSProtocol) as sts:
        sts: STSProtocol
        pos = 0
        while True:
            time.sleep(1)
            sts.move(2, pos)
            time.sleep(0.1)
            sts.read_pos(2)
            time.sleep(0.1)
            pos = (pos + 100)%3900

    # # without context manager
    # t = ReaderThread(ser, STSProtocol)
    # t.start()
    # transport, sts = t.connect()
    # pos = 0
    # while True:
    #     sts.move(2, pos)
    #     pos = (pos + 100)%3900
    #     time.sleep(1)
    # t.close()
