from saleae.analyzers import HighLevelAnalyzer, AnalyzerFrame, StringSetting, NumberSetting, ChoicesSetting
from os import path, getenv
import sys

DEFAULT_PPRZ_HOME = f"{getenv('HOME')}/paparazzi"

fdir = path.dirname(path.abspath(__file__))
PYTHON_PACKAGES = path.abspath(path.join(fdir, "lib"))

if PYTHON_PACKAGES not in sys.path:
    sys.path.append(PYTHON_PACKAGES)

PPRZ_HOME = getenv("PAPARAZZI_HOME", DEFAULT_PPRZ_HOME)
sys.path.append(PPRZ_HOME + "/var/lib/python")  # pprzlink

from pprzlink.pprz_transport import PprzTransport, PprzParserState, STX
import pprzlink.messages_xml_map as messages_xml_map
import pprzlink.message as message

messages_xml_map.parse_messages(path.join(PPRZ_HOME, "var/messages.xml"))

# High level analyzers must subclass the HighLevelAnalyzer class.
class PprzlinkAnalyser(HighLevelAnalyzer):
    # List of settings that a user can set for this High Level Analyzer.
    protocol = ChoicesSetting(label='Protocol', choices=('pprzlink v2.0', 'pprzlink v1.0', 'Xbee API'))
    display_content = ChoicesSetting(label='Display content?', choices=('Yes', 'No'))

    # An optional list of types this analyzer produces, providing a way to customize the way frames are displayed in Logic 2.
    result_types = {
        'pprz_detailled': {
            'format': '{{data.msg_name}} [{{data.sender_id}}->{{data.receiver_id}}] {{data.msg}}'
        },
        'pprz': {
            'format': '{{data.msg_name}} [{{data.sender_id}}->{{data.receiver_id}}]'
        }
    }

    def __init__(self):
        '''
        Initialize HLA.

        Settings can be accessed using the same name used above.
        '''

        self.trans = PprzTransport()
        self.stx_time = 0

        print("Settings:", self.protocol, self.display_content)

    def decode(self, frame: AnalyzerFrame):
        '''
        Process a frame from the input analyzer, and optionally return a single `AnalyzerFrame` or a list of `AnalyzerFrame`s.

        The type and data values in `frame` will depend on the input analyzer.
        '''
        c = frame.data['data']
        if ord(c) == STX and self.trans.state == PprzParserState.WaitSTX:
            self.stx_time = frame.start_time

        if self.trans.parse_byte(c):
            try:
                #print(self.trans.buf)
                (sender_id, receiver_id, component_id, msg) = self.trans.unpack()
                ret = ''
                for idx, f in enumerate(msg.fieldnames):
                    ret += '%s : %s, ' % (f, msg.fieldvalues[idx])
                
                
            except ValueError as e:
                logger.warning("Ignoring unknown message, %s" % e)
            else:
                if self.display_content == "Yes":
                    msg_type = 'pprz_detailled'
                else:
                    msg_type = 'pprz'

                return AnalyzerFrame(msg_type, self.stx_time, frame.end_time, {
                    'msg_name': msg.name,
                    'sender_id': sender_id,
                    'receiver_id': receiver_id,
                    'component_id': component_id,
                    'msg': ret,
                })
            
