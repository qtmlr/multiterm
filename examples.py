#! /usr/bin/python3

"""
"""

import multiterm as mt
import serial
import wx
import sys

toggle = True

app = mt.MultiTerm()
sel = app.nodeSelect()

def func1(app, dta, last_byte):
    print("FUNC1", last_byte)

def func2(app, dta, last_byte):
    global toggle
    global sel
    toggle = not toggle
    if toggle:
        sel.enable('hdump')
        sel.disable('key')
    else:
        sel.enable('key')
        sel.disable('hdump')

def func3(evt):
    print("CLICKED " + str(evt))

def func4(evt):
    print("CHOICE " + evt.GetString())

class NodeTest(mt.Node):
    def __init__(self, app, uid = ''):
        mt.Node.__init__(self, app, uid)

    def recv(self, ba, caller):
        nba = bytearray(map(lambda x: x+1, ba))
        for ch in self.ch['_']:
            ch.recv(nba, self.uid)


def example1():
    # For any serial, timeout = 0 is important, else the call to read() blocks.
    # This example uses the linux kernel module tty0tty which gives the below used devices.
    ser0 = serial.Serial('/dev/tnt0', 9600, bytesize=8, parity='N', stopbits=1, timeout=0, xonxoff=0, rtscts=0)
    ser1 = serial.Serial('/dev/tnt1', 9600, bytesize=8, parity='N', stopbits=1, timeout=0, xonxoff=0, rtscts=0)

    # create the nodes that we want to use
    key = app.nodeKeyboard()
    sn0 = app.nodeSerial(ser0)
    sn1 = app.nodeSerial(ser1)
    t0 = app.nodeText(wx.RED)
    t1 = app.nodeText(wx.BLUE)

    # connect the nodes together
    key.append_receiver(sn1)
    sn0.append_receiver(t0)
    sn1.append_receiver(t1)

def example2():
    key = app.nodeKeyboard()
    t0 = app.nodeText(wx.RED)
    seq_check = app.nodeSeqCheck([
        mt.ByteSeq(func1, b"\x1b\x1b", 1, False),     # call func1 on double-ESC, dta = 1, don't forward any characters if this sequence may match
        mt.ByteSeq(func1, b"\x1bb[x-z]", 3.14, True),    # after ESC-b there may be x, y or z coming.  Forward these characters to the receiver
        mt.ByteSeq(func1, b"\x1baz", (1, 2, 3), False), # ESC, a, z
        mt.ByteSeq(func1, b"\x1ba[a-c,e,g-i]", b'qqq', False),  # ESC, a, followed by any character from the list [a, b, c, e, g, h, i]
    ])

    key.append_receiver(seq_check)
    seq_check.append_receiver(t0)

def example3():
    key = app.nodeKeyboard()
    t0 = app.nodeText(wx.RED)
    logf = app.nodeLogfile("output.log")
    lbuf = app.nodeLinebuffer()

    key.append_receiver(logf)
    key.append_receiver(lbuf)
    lbuf.append_receiver(t0)

def example4():
    key = app.nodeKeyboard('key')
    t0 = app.nodeText(wx.RED)
    hd = app.nodeHex('hdump')
    seq_check = app.nodeSeqCheck(
        [ mt.ByteSeq(func2, b"\x1ba", 0, False)
        ]
    )

    key.append_receiver(seq_check)
    key.append_receiver(hd)
    key.append_receiver(sel)
    hd.append_receiver(sel)
    sel.append_receiver(t0)
    func2(None, None, None)

def example5():
    key = app.nodeKeyboard('key')
    tst = NodeTest(app)
    t0 = app.nodeText(wx.RED)

    key.append_receiver(tst)
    tst.append_receiver(t0)


def example6():
    sbar = app.addStatusBar()
    sbar.SetStatusText("Hi there")
    app.addButton("My Button", func3)
    app.addChoice(['Option A', 'Option B', 'Option C'], func4)

example1()

# run forever
app.MainLoop()

