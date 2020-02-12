#! /usr/bin/python

"""
"""

import multiterm as mt
import serial
import wx



def func1(app, dta):
    print("FUNC1")

def func2(app, dta):
    print("FUNC2")

def quitter(app, dta):
    app.quit()

# timeout = 0 is important, else the call to read() blocks
s0 = serial.Serial('/dev/tnt0', 9600, bytesize=8, parity='N', stopbits=1, timeout=0, xonxoff=0, rtscts=0)
s1 = serial.Serial('/dev/tnt1', 9600, bytesize=8, parity='N', stopbits=1, timeout=0, xonxoff=0, rtscts=0)

app = mt.MultiTerm()

sc = mt.NodeSeqCheck( app, [
        mt.ByteSeq(quitter, b"\x1b\x1b", 0, False),
        mt.ByteSeq(func1, b"\x1ba", 0, False),
        mt.ByteSeq(func2, b"b", 0, True),
    ]
)

lb = mt.NodeLinebuffer()

key = mt.NodeKeyboard(app)

ss0 = mt.NodeSerial(app, s0)
ss1 = mt.NodeSerial(app, s1)
t0 = mt.NodeText(app, wx.RED)
t1 = mt.NodeText(app, wx.BLUE)

log = mt.NodeLogfile(app, "log.txt")

if False:
    key.append_receiver(ss0)
    ss0.append_receiver(t0)
    ss1.append_receiver(t1)
    ss1.append_receiver(log)

    app.register_proc(ss0)
    app.register_proc(ss1)


elif False:
    key.append_receiver(sc)
    sc.append_receiver(t0)

elif True:
    key.append_receiver(lb)
    lb.append_receiver(t1)


app.MainLoop()
