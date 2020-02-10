#! /usr/bin/python3

"""
"""

import wx
import os
import sys
import zlib
import pickle
import serial


class MTNode(object):
    def __init__(self):
        self.ch = []
        self.ba = bytearray()

    def append_child(self, ch):
        self.ch.append(ch)

    def recv(self, ba):
        pass
#        self.ba.extend(ba)

    def proc(self):
        pass
#        for i, ch in enumerate(self.ch):
#            ch.proc()

class MTNodeKeyboard(MTNode):
    def __init__(self, app):
        MTNode.__init__(self)
        self.app = app
        app.register_keylistener(self)

    def recv(self, ba):
        if len(ba) != 0:
            print("kbd recv", ba)
            for ch in self.ch:
                ch.recv(ba)

#    def proc(self):
#        ba = bytearray()
#        while True:
#            k = app.key()
#            if k == 0:
#                break
#            ba.append(k)
#        if len(ba) != 0:
#            for ch in self.ch:
#                ch.recv(ba)

class MTNodeSerial(MTNode):
    def __init__(self, ser):
        MTNode.__init__(self)
        self.ser = ser

    def recv(self, ba):
#        print("serial recv", ba)
        self.ser.write(ba)

    def proc(self):
        ba = self.ser.read()
        if len(ba) != 0:
            for ch in self.ch:
                ch.recv(ba)

class MTNodeText(MTNode):
    def __init__(self, app, col):
        MTNode.__init__(self)
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
        print("textctrl:", self.par)
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
        print("frame:", self.par)
        self.tc = MTTextCtrl(self)
        self.vbox = wx.BoxSizer(wx.VERTICAL)
        self.vbox.Add(self.tc, proportion = 1, flag = wx.EXPAND | wx.ALL, border = 0)

        self.SetSizer(self.vbox)
        self.Show(True)

    def append_text(self, tcol, txt):
        self.tc.append_text(tcol, txt)

class MTApp(wx.App):
    def __init__(self, *args, **kwds):
        wx.App.__init__(self, *args, **kwds)
#        self.s = s
        self.kl = None
        self.f = MTFrame(self)
        self.f.Show()
#        self.st = load_mod("settings.py")
#        print("fontsize", self.st.fontsize)
#        self.st.init(self)
#        self.Bind(wx.EVT_IDLE, self.OnIdle)

    def register_keylistener(self, kl):
        self.kl = kl

#    def OnIdle(self, evt):
#        print("Idle")

if __name__ == '__main__':
    s = Settings()
    s.show()
    s.save()
    s.show()
    s.load()
    s.show()
    app = MTApp(redirect = False, settings = s)
    app.MainLoop()
