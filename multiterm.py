#! /usr/bin/python3

"""
"""

import wx
import wx.lib.newevent
import os
import sys
import zlib
import pickle
import serial
import threading


SerialEvent, EVT_SERIAL_EVENT = wx.lib.newevent.NewEvent()

ESCMARKER = 0
FRAMESTART = 1
ACK = 2
NACK = 3
ESC = 255

htab = (0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46)


# print a byte string
def printb(txt):
    print(txt.decode('utf-8', 'ignore'))

# return a hex dump of a byte array as another byte array
def hdump(ba, bpl = 8):
    ret = bytearray()
    for ix, x in enumerate(ba):
        if (ix % bpl) == 0 and ix != 0:
            ret.append(13)
        ret.append(32)
        h = int(x / 16)
        l = x & 15
        ret.append(htab[h])
        ret.append(htab[l])
    ret.append(13)

    return ret


def rfind(lst, val, start = None):
    if start is None:
        start = len(lst) - 1
    for i in range(start, -1, -1):
        if lst[i] == val:
            return i
    return -1


def lfind(lst, val, start = None):
    if start is None:
        start = 0
    for i in range(start, len(lst), 1):
        if lst[i] == val:
            return i
    return -1


def list_add(l, v):
    if v == ESC:
        l.append(ESC)
        l.append(ESCMARKER)
    else:
        l.append(v)


class MTException(Exception):
    pass

class ProcHandler(threading.Thread):
    def __init__(self, app):
        threading.Thread.__init__(self)
        self.app = app
        self.stop = False

    def run(self):
        while not self.stop:
            for ob in self.app.proc:
                ob.proc()


# a ByteSeq describes a certain sequence of bytes.  If the same sequence is input into this ByteSeq
# then it will "match", else the ByteSeq's counter will be reset and the input is scanned again.
# ByteSeqs are checked from within a NodeSeqcheck, if there is a match then it will call the call target
# with certain parameters (the app, the given dta parameter and the last byte that was input into this ByteSeq).
class ByteSeq(object):
    def __init__(self, cll, bstr, dta = None, forward = False):
        self.call = cll # call target
        self.dta = dta # parameter to call
        self.forward = forward # if characters shall be forwarded to children if this seq is still possible

        # check if the last byte of the sequence is rather a list than a single byte
        if bstr[-1] == ord(b']'):
            ix = bstr.rfind(b'[')
            if ix < 0:
                raise MTException(b"ByteSeq '%s': did not find matching '['" % (bstr))
            self.bstr = bstr[:ix]
            s = bstr[ix+1:-1]
            ss = s.split(b",")
            self.last = []
            for sss in ss:
                if len(sss) == 3 and sss[1] == ord(b'-'):
                    self.last.append( (sss[0], sss[2]) )
                elif len(sss) == 1:
                    self.last.append( (sss[0], sss[0]) )
                else:
                   raise MTException(b"ByteSeq '%s': did not understand '%s'" % (bstr, sss))
                q = self.last[-1]
            self.ln = len(self.bstr) + 1
        else:
            self.bstr = bstr # the sequence to match
            self.last = None
            self.ln = len(bstr)
        self.reset()

    # return True if byte b matches this ByteSeq at index ix
    def mtch(self, b, ix):
        assert ix < self.ln
        if not self.last is None:
            if ix < self.ln-1:
                return b == self.bstr[ix]
            else:
                for rg in self.last:
                    if rg[0] <= b and b <= rg[1]:
                        return True
                return False
        else:
            return b == self.bstr[ix]

    def reset(self):
        self.ix = 0
        self.match = False
        self.last_byte = bytearray()

    def received(self, b):
        if self.ix < self.ln:
            if self.mtch(b, self.ix):
                self.ix += 1
                if self.ix == self.ln:
                    self.last_byte.append(b)
                    self.match = True
            else:
                self.reset()
        else:
            self.reset()

    def matched(self):
        return self.match


# The Node, this is the base class for all other Nodes
class Node(object):
    """This is the base class for all other nodes.  It is meant to be derived and not to be used directly.

A Node should know the MultiTerm app that it is used in and optionally can have a UID, a user chosen name
that can be used to identify this node.

A Node can receive input data using the method recv(ba, caller_uid).  "ba" is a bytearray containing
0 or more bytes that this node shall process.

Other Nodes can be set as receivers of this node by calling Node.append_receiver().  This method can optionally
take an identifier that is handled depending on the nodes behavior.  Most often, this parameter is omitted.
Processed data of a node will then behanded to the registered receiver nodes by calling their method recv(ba, caller_uid).
The parameter "caller_uid" will be the UID given to the calling node in its constructor.
"""
    def __init__(self, app, uid = ''):
        self.ch = dict()
        self.ch['_'] = []
        self.uid = uid
        self.app = app
        self.ba = bytearray()

    def append_receiver(self, *ch):
        """This function can be used to register receivers (other Nodes) to this Node.
Anything this Node wants to output goes to its receivers.
Receivers can register with a key (as first parameter, '_' if no key is given).
This class can use the receivers for different purposes.
"""
        if len(ch) >= 2 and isinstance(ch[0], str):
            k = ch[0]
            a = ch[1:]
        else:
            k = '_'
            a = ch
        if not k in self.ch:
            self.ch[k] = []

        self.ch[k].extend(a)

    def recv(self, ba, caller):
        """To be implemented in the derived class
        """
        pass

    def proc(self):
        """To be implemented in the derived class
        """
        pass


class NodeSelect(Node):
    """
    """
    def __init__(self, app, uid = ''):
        Node.__init__(self, app, uid)
        self.d = dict()
        self.df = True

    def default_enable(self, df):
        self.df = df

    def enable(self, k):
        self.d[k] = True

    def disable(self, k):
        self.d[k] = False

    def recv(self, ba, caller):
        for ch in self.ch['_']:
            df = self.df
            if caller in self.d:
                df = self.d[caller]
            if df:
                ch.recv(ba, self.uid)


class NodeHex(Node):
    """A Node that converts its input to hexadecimal numbers and outputs these to its receivers.
    """
    def __init__(self, app, uid = ''):
        Node.__init__(self, app, uid)

    def recv(self, ba, caller):
        b = bytearray()
        for x in ba:
            b.append(32)
            h = int(x / 16)
            l = x & 15
            b.append(htab[h])
            b.append(htab[l])
        for ch in self.ch['_']:
            ch.recv(b, self.uid)


class NodeXferOut(Node):
    """Convert an input bytearray to a XFER packet
    """
    def __init__(self, app, uid = ''):
        Node.__init__(self, app, uid)

    def recv(self, ba, caller):
        b = bytearray()
        l = len(ba)
        assert l < 65535, "bytearray too long: %i" % (l)
        lh = int(l / 256)
        ll = l & 255
        b.append(ESC)
        b.append(FRAMESTART)
        list_add(b, lh)
        list_add(b, ll)
        s = lh + ll
        for x in ba:
            list_add(b, x)
            s += x
        s &= 255
        list_add(b, s)

        for ch in self.ch['_']:
            ch.recv(b, self.uid)


class NodeXferIn(Node):
    """Scan the input bytearrays to an XFER packet.  The packet will be handled differently
    from the other data.
    TODO: What happens if a packet is not recognized?
    TODO: Are the other data just forwarded to the children?
    """
    def __init__(self, app, uid = ''):
        Node.__init__(self, app, uid)
        self.reset()
        self.pch = []

    def add_packet_receiver(self, ob):
        self.pch.append(ob)

    def no_packet(self):
        self.p = bytearray()
        self.st = 0
        self.l = 0
        self.s = 0
        self.ix = 0
        self.esc = False

    def reset(self):
        self.ba = bytearray()
        self.no_packet()

# st:
# 0: no packet, just normal bytes
# 1: FRAMESTART
# 2: LEN_HI
# 3: LEN_LO
# 4: DATA
# 5: CSUM
    def rx(self, v):
        print("rx", v, self.st)
        if self.st == 0:
            if v == ESC:
                self.st = 1
                self.esc = True
            else:
                self.ba.append(v)
            return

        if self.esc:
            if v == ESCMARKER:
                v = ESC
            self.esc = False
        else:
            if v == ESC:
                self.esc = True
                return

        if self.st == 1:
            if v == FRAMESTART:
                self.st = 2
            else:
                self.no_packet()    

        elif self.st == 2:
            self.s = v
            self.l = 256 * v
            self.st = 3

        elif self.st == 3:
            self.s += v
            self.l += v
            if self.l == 0:
                self.st = 5
            self.st = 4

        elif self.st == 4:
            self.s += v
            self.p.append(v)
            self.ix += 1
            if self.ix >= self.l:
                self.st = 5

        elif self.st == 5:
            if v == self.s:
                if len(self.ba) != 0:
                    for ch in self.ch['_']:
                        ch.recv(self.ba, self.uid)
                    self.ba = bytearray()

                for ch in self.pch:
                    ch.recv(self.p, self.uid)
                self.reset()
            else:
                self.no_packet()


    def recv(self, ba, caller):
        ln = len(ba)
        if ln == 0:
            return
        for x in ba:
            self.rx(x)
        if len(self.ba) != 0:
            for ch in self.ch['_']:
                ch.recv(self.ba, self.uid)
            self.ba = bytearray()


class NodeLinebuffer(Node):
    """Buffer input data until a \n is detected, then output them all at once.
    """
    def __init__(self, app, uid = ''):
        Node.__init__(self, app, uid)
        self.ba = bytearray()

    def recv(self, ba, caller):
        self.ba.extend(ba)
        ix = rfind(self.ba, 13)
        if ix >= 0:
            f = self.ba[:ix + 1]
            self.ba = self.ba[ix+1:]
            for ch in self.ch['_']:
                ch.recv(f, self.uid)


class NodeSeqCheck(Node):
    """Check the input streams against a list of byte sequences (lobs).
    If a sequence is detected then call the registered callout.
    """
    def __init__(self, app, lobs, uid = ''):
        Node.__init__(self, app, uid)
        self.esc = 27
        self.lobs = lobs # list of byte sequences

    def recv(self, ba, caller):
        for b in ba:
            forward = True
            for bs in self.lobs:
                bs.received(b)
                if bs.ix != 0 and bs.forward == False:
                    forward = False
                if bs.matched():
                    bs.call(self.app, bs.dta, bs.last_byte)
                    bs.reset()

            if forward:
                bba = bytearray()
                bba.append(b)
                for ch in self.ch['_']:
                    ch.recv(bba, self.uid)


class NodeLogfile(Node):
    """Write all incoming data into a log file.
    """
    def __init__(self, app, fname, uid = ''):
        Node.__init__(self, app, uid)
        self.fname = fname
        self.fd = open(self.fname, "wb")

    def recv(self, ba, caller):
        self.fd.write(ba)


def singleton(class_):
    instances = {}
    def getinstance(*args, **kwargs):
        if class_ not in instances:
            instances[class_] = class_(*args, **kwargs)
        return instances[class_]
    return getinstance


@singleton
class NodeKeyboard(Node):
    """Send the keyboard input data to the registered receivers.
    It seems problematic to get the real characters, e.g. Shift-+ does not give *.
    """
    def __init__(self, app, uid = ''):
        Node.__init__(self, app, uid)
        self.app = app
        app.register_keylistener(self)

    def recv(self, ba, caller = ''):
        if len(ba) != 0:
            for ch in self.ch['_']:
                ch.recv(ba, self.uid)


class NodeSerial(Node):
    """The input and output from a serial line is handled by this Node.
    """
    def __init__(self, app, ser, uid = ''):
        Node.__init__(self, app, uid)
        self.app = app
        self.ser = ser

    def recv(self, ba, caller = ''):
        self.ser.write(ba)

    def proc(self):
        ba = self.ser.read()
        if len(ba) != 0:
            for ch in self.ch['_']:
                evt = SerialEvent(ba = ba, ch = ch, uid = self.uid)
                wx.PostEvent(self.app, evt)


class NodeText(Node):
    """Instances of these Nodes get a color parameter.  The input is colored by that color
    and displayed in the wx.TextCtrl.
    """
    def __init__(self, app, col, uid = ''):
        Node.__init__(self, app, uid)
        self.app = app
        self.col = col

    def recv(self, ba, caller):
        self.app.f.tc.append_text(self.col, ba)


def load_mod(path):
    ver = sys.version_info
    if ver[0] == 3 and ver[1] >= 5:
        import importlib.util
        spec = importlib.util.spec_from_file_location("module.name", path)
        foo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(foo)
        return foo
    else:
#        from importlib.machinery import SourcelessFileLoaderceFileLoader
        from importlib.machinery import SourcelessFileLoader
        foo = SourcelessFileLoader("module.name", path).load_module()
        return foo


def configdir():
    return os.path.expanduser("~")


def configfile():
    return configdir() + "/.multiterm.dta"


class Settings(dict):
    """Save / Load settings data, also handle default data for them.
    """
    def __init__(self):
        super(Settings, self).__init__(self)
        self.__dict__ = self
        self.x = 10
        self.y = 10
        self.w = 1024
        self.h = 768
        pth = configfile()
        if os.path.isfile(pth):
            self.load()

    def save(self):
        d = pickle.dumps(self.__dict__)
        dz = zlib.compress(d)
        pth = configfile()
        f = open(pth, "wb")
        f.write(dz)
        f.close()

    def load(self):
        pth = configfile()
        f = open(pth, "rb")
        dz = f.read()
        f.close()
        d = zlib.decompress(dz)
        q = pickle.loads(d)
        for k in q.keys():
            self.__dict__[k] = q[k]

    def show(self):
        print(self.__dict__)


class MTTextCtrl(wx.TextCtrl):
    def __init__(self, par):
        wx.TextCtrl.__init__(self, par, style = wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.par = par
        self.tcol = None
        self.SetDefaultStyle(wx.TextAttr(colText = wx.BLACK, colBack = wx.NullColour,
            font = wx.Font(12, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, False)))

        self.Bind(wx.EVT_CHAR_HOOK, self.OnChar)
        self.SetFocus()

#        self.append_text(wx.RED, b"Hi There")

    def OnChar(self, evt):
        m = evt.GetModifiers()
        k = evt.GetUnicodeKey()
        sdown = evt.ShiftDown()
        cdown = evt.ControlDown()
        adown = evt.AltDown()
        if k == 0:
            k = evt.GetKeyCode()
        if k == 0 or k > 255:
            return

        c = str(chr(k))
        if sdown:
            c = c.upper()
        else:
            c = c.lower()

        ba = bytearray()
        ba.append(ord(c))
        if self.par.par.kl:
            self.par.par.kl.recv(ba, 'wx.Key')

    def append_text(self, tcol, txt):
        if self.tcol != tcol:
            self.SetDefaultStyle(wx.TextAttr(colText = tcol))
            self.tcol = tcol
        self.AppendText(txt.decode('utf-8', 'ignore'))


class MTFrame(wx.Frame):
    def __init__(self, par):
        wx.Frame.__init__(self, None)
        self.par = par

        self.vbox = wx.BoxSizer(wx.VERTICAL)

        self.panel = wx.Panel(self)
#        self.panel.SetBackgroundColour(wx.RED)
        self.vbox.Add(self.panel, proportion = 0, flag = wx.EXPAND | wx.ALL, border = 0)

        self.tc = MTTextCtrl(self)
        self.vbox.Add(self.tc, proportion = 1, flag = wx.EXPAND | wx.ALL, border = 0)

        self.hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.panel.SetSizer(self.hbox)

        self.SetSizer(self.vbox)
        self.Show(True)

        self.Bind(wx.EVT_CLOSE, self.OnClose)

        self.par.thr.start()

    def OnClose(self, evt):
        self.stop_thread()
        self.Destroy()

    def stop_thread(self):
        self.par.thr.stop = True
        self.par.thr.join()

    def append_text(self, tcol, txt):
        self.tc.append_text(tcol, txt)


class MultiTerm(wx.App):
    def __init__(self, *args, **kwds):
        wx.App.__init__(self, *args, **kwds)
#        self.s = s
        self.proc = []
        self.thr = ProcHandler(self)
        self.kl = None
        self.f = MTFrame(self)
        self.f.Show()
#        self.st = load_mod("settings.py")
#        print("fontsize", self.st.fontsize)
#        self.st.init(self)

        self.Bind(EVT_SERIAL_EVENT, self.OnSerial)

    def OnSerial(self, evt):
        evt.ch.recv(evt.ba, evt.uid)

    def register_keylistener(self, kl):
        self.kl = kl

    def register_proc(self, ob):
        self.proc.append(ob)

    def quit(self):
        self.f.OnClose(None)

    def addButton(self, txt, cback):
        btn = wx.Button(self.f.panel, -1, txt)
        self.f.hbox.Add(btn)
        self.f.hbox.Layout()
        self.f.Fit()
        btn.Bind(wx.EVT_BUTTON, cback)

    def addChoice(self, lst, cback):
        chc = wx.Choice(self.f.panel, -1, choices = lst)
        self.f.hbox.Add(chc)
        self.f.hbox.Layout()
        self.f.Fit()
        chc.Bind(wx.EVT_CHOICE, cback)

    def addStatusBar(self):
        sbar = self.f.CreateStatusBar()
        return sbar

    # Node returning methods
    def nodeSelect(self, uid = ''):
        ret = NodeSelect(self, uid)
        return ret

    def nodeHex(self, uid = ''):
        ret = NodeHex(self, uid)
        return ret

    def nodeXferOut(self, uid = ''):
        ret = NodeXferOut(self, uid)
        return ret

    def nodeXferIn(self, uid = ''):
        ret = NodeXferIn(self, uid)
        return ret

    def nodeLinebuffer(self, uid = ''):
        ret = NodeLinebuffer(self, uid)
        return ret

    def nodeSeqCheck(self, lobs, uid = ''):
        ret = NodeSeqCheck(self, lobs, uid)
        return ret

    def nodeLogfile(self, fname, uid = ''):
        ret = NodeLogfile(self, fname, uid)
        return ret

    def nodeKeyboard(self, uid = ''):
        ret = NodeKeyboard(self, uid)
        return ret

    def nodeSerial(self, ser, uid = ''):
        ret = NodeSerial(self, ser, uid)
        self.register_proc(ret)
        return ret

    def nodeText(self, col, uid = ''):
        ret = NodeText(self, col, uid)
        return ret



if __name__ == '__main__':
    s = Settings()
    s.show()
    s.save()
    s.show()
    s.load()
    s.show()
    app = MultiTerm(redirect = False, settings = s)
    app.MainLoop()

