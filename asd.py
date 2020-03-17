#! /usr/bin/python

"""
"""

import multiterm as mt
import serial
import wx
import sys



def func1(app, dta, got):
    print("FUNC1", got)

def func2(app, dta, got):
    print("FUNC2", got)
    c = got
    if c == b'b':
        sel.enable('hdumper')
    elif c == b'c':
        sel.disable('hdumper')
    elif c == b'd':
        sel.enable('seqcheck')
    elif c == b'e':
        sel.disable('seqcheck')

def quitter(app, dta, got):
    app.quit()

def func3(evt):
    print("CLICKED " + str(evt))

def func4(evt):
    print("CHOICE " + evt.GetString())


class NodeTest(mt.Node):
    def __init__(self, app, nm, uid = ''):
        mt.Node.__init__(self, app, uid)
        self.nm = nm

    def recv(self, ba, caller):
        self.ba = ba[:]
        bh = mt.hdump(ba)
        print("NAME:", self.nm)
        print(bh.decode('utf-8'))
        print("---------------")


# timeout = 0 is important, else the call to read() blocks
s0 = serial.Serial('/dev/tnt0', 9600, bytesize=8, parity='N', stopbits=1, timeout=0, xonxoff=0, rtscts=0)
s1 = serial.Serial('/dev/tnt1', 9600, bytesize=8, parity='N', stopbits=1, timeout=0, xonxoff=0, rtscts=0)

app = mt.MultiTerm()
sbar = app.addStatusBar()
sbar.SetStatusText("Hi there")
app.addButton("QWE", func3)
app.addChoice(['9600', '19200', '38400'], func4)

sc = app.nodeSeqCheck( [
        mt.ByteSeq(quitter, b"\x1b\x1b", 0, False),
        mt.ByteSeq(func1, b"\x1bb[x-z]", 0, True),
        mt.ByteSeq(func2, b"\x1baz", 0, False),
        mt.ByteSeq(func2, b"\x1ba[a-c,e,g-i]", 0, False),
    ],
    'seqcheck'
)

lb = app.nodeLinebuffer()

key = app.nodeKeyboard()

ss0 = app.nodeSerial(s0)
ss1 = app.nodeSerial(s1)
t0 = app.nodeText(wx.RED)
t1 = app.nodeText(wx.BLUE)

log = app.nodeLogfile("log.txt")
hd = app.nodeHex('hdumper')

sel = app.nodeSelect()


def do_a():
    key.append_receiver(ss0)
    ss0.append_receiver(t0)
    ss1.append_receiver(t1)
    ss1.append_receiver(log)

#    app.register_proc(ss0)
#    app.register_proc(ss1)

def do_b():
    key.append_receiver(sc)
    sc.append_receiver(t0)

def do_c():
    key.append_receiver(lb)
    lb.append_receiver(t1)

def  do_d():
    key.append_receiver()

def do_e():
    key.append_receiver(sc)
    sc.append_receiver(hd)
    hd.append_receiver(t0)

def do_f():
    key.append_receiver(sc)
    sc.append_receiver(hd)
    hd.append_receiver(sel)
    sc.append_receiver(sel)
    sel.append_receiver(t0)

def do_g():
    ntp = NodeTest(app, 'PACKET')
    ntb = NodeTest(app, 'BYTES')
    xo = mt.NodeXferOut(app)
    xo.append_receiver(ntb)
    ba = bytearray()
    ba.extend( (1, 2, 3) )
    xo.recv(ba, 'test')
    packet = ntb.ba[:]
    packet.insert(0, 0x66)
    packet.insert(0, 0x65)
    packet.insert(0, 0x64)
    packet.extend( (0x61, 0x62, 0x63) )

    xi = mt.NodeXferIn(app)
    xi.append_receiver(ntb)
    xi.add_packet_receiver(ntp)
    xi.recv(packet, 'test')


do_a()
app.MainLoop()
