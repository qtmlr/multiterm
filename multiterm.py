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

    def received(self, b):
        if self.ix < len(self.bstr):
            if b == self.bstr[self.ix]:
                self.ix += 1
                if self.ix == len(self.bstr):
                    self.match = True
            else:
                self.reset()
        else:
            self.reset()

    def matched(self):
        return self.match


class Node(object):
    def __init__(self):
        self.ch = []
        self.ba = bytearray()

    def append_receiver(self, ch):
        self.ch.append(ch)

    def recv(self, ba):
        pass

    def proc(self):
        pass

def rindex(lst, val, start = None):
    if start is None:
        start = len(lst) - 1
    for i in range(start, -1, -1):
        if lst[i] == val:
            return i

class NodeLinebuffer(Node):
    def __init__(self):
        Node.__init__(self)
        self.ba = bytearray()

    def recv(self, ba):
        self.ba.extend(ba)
        ix = rindex(self.ba, 13)
        if not ix is None:
            f = self.ba[:ix + 1]
            self.ba = self.ba[ix+1:]
            for ch in self.ch:
                ch.recv(f)


class NodeSeqCheck(Node):
    def __init__(self, app, lobs):
        Node.__init__(self)
        self.app = app
        self.esc = 27
        self.lobs = lobs # list of byte sequences

    def recv(self, ba):
        for b in ba:
            print("Check", b)

            display = True
            for bs in self.lobs:
                bs.received(b)
                if bs.ix != 0 and bs.display == False:
                    display = False
                if bs.matched():
                    bs.call(self.app, bs.dta)
                    bs.reset() # reset all?

            if display:
                bba = bytearray()
                bba.append(b)
                for ch in self.ch:
                    ch.recv(bba)


class NodeLogfile(Node):
    def __init__(self, app, fname):
        Node.__init__(self)
        self.app = app
        self.fname = fname
        self.fd = open(self.fname, "wb")

    def recv(self, ba):
        self.fd.write(ba)

class NodeKeyboard(Node):
    def __init__(self, app):
        Node.__init__(self)
        self.app = app
        app.register_keylistener(self)

    def recv(self, ba):
        if len(ba) != 0:
#            print("kbd recv", ba)
            for ch in self.ch:
                ch.recv(ba)

class NodeSerial(Node):
    def __init__(self, app, ser):
        Node.__init__(self)
        self.app = app
        self.ser = ser

    def recv(self, ba):
#        print("serial recv", ba)
        self.ser.write(ba)

    def proc(self):
        ba = self.ser.read()
        if len(ba) != 0:
            for ch in self.ch:
                evt = SerialEvent(ba = ba, ch = ch)
                wx.PostEvent(self.app, evt)
#                ch.recv(ba)

class NodeText(Node):
    def __init__(self, app, col):
        Node.__init__(self)
        self.app = app
        self.col = col

    def recv(self, ba):
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

        self.append_text(wx.RED, b"Hi There")

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
        self.par.par.kl.recv(ba)

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
        evt.ch.recv(evt.ba)

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

