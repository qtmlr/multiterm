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


def rindex(lst, val, start = None):
    if start is None:
        start = len(lst) - 1
    for i in range(start, -1, -1):
        if lst[i] == val:
            return i


def lindex(lst, val, start = None):
    if start is None:
        start = 0
    for i in range(start, len(lst), 1):
        if lst[i] == val:
            return i


def list_add(l, v):
    if v == ESC:
        l.append(ESC)
        l.append(ESCMARKER)
    else:
        l.append(v)


class ProcHandler(threading.Thread):
    def __init__(self, app):
        threading.Thread.__init__(self)
        self.app = app
        self.stop = False

    def run(self):
        while not self.stop:
            for ob in self.app.proc:
                ob.proc()


class ByteSeq(object):
    def __init__(self, cll, bstr, dta = None, display = False):
        self.call = cll # call target
        self.dta = dta # parameter to call
        self.display = display # if characters shall be forwarded to children if this seq is still possible
        self.bstr = bstr # the sequence to match
        self.reset()

    def reset(self):
        self.ix = 0
        self.match = False
        self.got = bytearray()

    def received(self, b):
        if self.ix < len(self.bstr):
            bc = self.bstr[self.ix]
            wcard = bc == ord('_')
            if b == bc or wcard:
                if wcard:
                    self.got.append(b)
                self.ix += 1
                if self.ix == len(self.bstr):
                    self.match = True
            else:
                self.reset()
        else:
            self.reset()

    def matched(self):
        return self.match


# The Node, this is the base class
class Node(object):
    """This is the base class for all other nodes.  It is meant to be derived and not to be used directly.
    """
    def __init__(self, uid = ''):
        self.ch = dict()
        self.ch['_'] = []
        self.uid = uid
        self.ba = bytearray()

    def append_receiver(self, *ch):
        """This function can be used to register receivers (other Nodes) to this Node.
        Anything this Node wants to output goes to its receivers.
        Receivers can register with a key ('_' if no key is given).
        This class can use the receivers under the different keys for different purposes.
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
        pass

    def proc(self):
        pass


class NodeSelect(Node):
    """
    """
    def __init__(self, uid = ''):
        Node.__init__(self, uid)
        self.d = dict()
        self.df = True

    def default_enable(self, df):
        self.df = df

    def enable(self, k):
        print("enable", k)
        self.d[k] = True

    def disable(self, k):
        print("disable", k)
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
    def __init__(self, uid = ''):
        Node.__init__(self, uid)

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
    def __init__(self, uid = ''):
        Node.__init__(self, uid)

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
    def __init__(self, uid = ''):
        Node.__init__(self, uid)
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
    def __init__(self, uid = ''):
        Node.__init__(self, uid)
        self.ba = bytearray()

    def recv(self, ba, caller):
        self.ba.extend(ba)
        ix = rindex(self.ba, 13)
        if not ix is None:
            f = self.ba[:ix + 1]
            self.ba = self.ba[ix+1:]
            for ch in self.ch['_']:
                ch.recv(f, self.uid)


class NodeSeqCheck(Node):
    """Check the input streams against a list of byte sequences (lobs).
    If a sequence is detected then call the registered callout.
    """
    def __init__(self, app, lobs, uid = ''):
        Node.__init__(self, uid)
        self.app = app
        self.esc = 27
        self.lobs = lobs # list of byte sequences

    def recv(self, ba, caller):
        for b in ba:
            print("Check", b)

            display = True
            for bs in self.lobs:
                bs.received(b)
                if bs.ix != 0 and bs.display == False:
                    display = False
                if bs.matched():
                    bs.call(self.app, bs.dta, bs.got)
                    bs.reset() # reset all?

            if display:
                bba = bytearray()
                bba.append(b)
                for ch in self.ch['_']:
                    ch.recv(bba, self.uid)


class NodeLogfile(Node):
    """Write all incoming data into a log file.
    """
    def __init__(self, fname, uid = ''):
        Node.__init__(self, uid)
        self.fname = fname
        self.fd = open(self.fname, "wb")

    def recv(self, ba, caller):
        self.fd.write(ba)


class NodeKeyboard(Node):
    """Send the keyboard input data to the registered receivers.
    It seems problematic to get the real characters, e.g. Shift-+ does not give *.
    """
    def __init__(self, app, uid = ''):
        Node.__init__(self, uid)
        self.app = app
        app.register_keylistener(self)

    def recv(self, ba, caller = ''):
        if len(ba) != 0:
#            print("kbd recv", ba)
            for ch in self.ch['_']:
                ch.recv(ba, self.uid)


class NodeSerial(Node):
    """The input and output from a serial line is handled by this Node.
    """
    def __init__(self, app, ser, uid = ''):
        Node.__init__(self, uid)
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
        Node.__init__(self, uid)
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
        self.tc = MTTextCtrl(self)
        self.vbox = wx.BoxSizer(wx.VERTICAL)
        self.vbox.Add(self.tc, proportion = 1, flag = wx.EXPAND | wx.ALL, border = 0)

        self.SetSizer(self.vbox)
        self.Show(True)

        self.Bind(wx.EVT_CLOSE, self.OnClose)

        print("starting threads")
        self.par.thr.start()

    def OnClose(self, evt):
        self.stop_thread()
        self.Destroy()

    def stop_thread(self):
        print("stopping thread")
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
        print("serial event")
        evt.ch.recv(evt.ba, evt.uid)

    def register_keylistener(self, kl):
        self.kl = kl

    def register_proc(self, ob):
        self.proc.append(ob)

    def quit(self):
        self.f.OnClose(None)


if __name__ == '__main__':
    s = Settings()
    s.show()
    s.save()
    s.show()
    s.load()
    s.show()
    app = MultiTerm(redirect = False, settings = s)
    app.MainLoop()

