# MultiTerm
MultiTerm is a python3 library that helps you write your own terminal program.

## Features
- It can handle several serial lines
- It is extensible by a node system, you can also write your own nodes
- It is based on wx_python and can be extended by wx.Button, wx.Choice, wx.Statusbar

## Warning
The keyboard handling in wx_python seems a bit odd, I did not manage to get the real keyboard
character, e.g. if on your keyboard there is the key '+' and shift-'+' is really a '*', then
the '*' will not appear, shift-'+' will only lead to a normal '+'.  Any help here is appreciated.

## Examples
In the following, some example code is given that should represent the features of MultiTerm

# Example 1
This example:
- opens two serial lines
- the keyboard input is written to the second serial line
- the input from the serial lines is displayed in different colors

import multiterm as mt
import serial
import wx

app = mt.MultiTerm()

# timeout = 0 is important, else the call to read() blocks
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

# run forever
app.MainLoop()


The following examples don't use the serial line at all, they just demonstrate the features of the node system.
Also, the import statements and the call to app.MainLoop() are skipped, they are though necessary in all examples.

# Example 2
This example:
- uses a sequence checker, that checks the input stream for a certain sequence of bytes
- calls functions based on the input sequences
- redirects the output to the text window

def func1(app, dta, got):
    print("FUNC1", got)

app = mt.MultiTerm()

key = app.nodeKeyboard()
t0 = app.nodeText(wx.RED)
seq_check = app.nodeSeqCheck([
    mt.ByteSeq(func1, b"\x1b\x1b", 1, False),     # call func1 on double-ESC, dta = 1, don't forward any characters if this sequence may match
    mt.ByteSeq(func1, b"\x1bb[x-z]", 3.14, True),    # after ESC-b there may be x, y or z coming.  Forward these characters to the receiver
    mt.ByteSeq(func1, b"\x1baz", (1, 2, 3), False), # ESC, a, z
    mt.ByteSeq(func1, b"\x1ba[a-c,e,g-i]", b'qqq', False),  # ESC, a, followed by any character from the list [a, b, c, e, g, h, i]
    ])

key.append__receiver(seq_check)
seq_check.append_receiver(t0)

# Example 3
This example:
- logs all keyboard input into a file
- does line buffering of the input and outputs only complete lines to the text window

app = mt.Multiterm()
key = app.nodeKeyboard()
t0 = app.nodeText(wx.RED)
logf = app.nodeLogfile("output.log")
lbuf = app.nodeLinebuffer()

key.append_receiver(logf)
key.append_receiver(lbuf)
lbuf.append_receiver(t0)


# Example 4
This example:
- checks the keyboard input for the sequence ESC-a and then toggles the input of a selector
- the selector either outputs the keyboard or the keyboard hexdump to the text output

toggle = True
def func1(app, dta, got):
    toggle = not toggle
    if toggle:
        sel.enable('hdump')
        sel.disable('key')
    else:
        sel.enable('key')
        sel.disable('hdump')

app = mt.Multiterm()
key = app.nodeKeyboard('key')
t0 = app.nodeText(wx.RED)
hd = app.nodeHex('hdump')
sel = app.nodeSelect()
seq_check = app.nodeSeqCheck(
    [ mt.ByteSeq(func1, b"\x1ba", 0, False)
    ]
)

key.append_receiver(seq_check)
key.append_receiver(hd)
key.append_receiver(sel)
hd.append_receiver(sel)
sel.append_receiver(t0)
func1(None, None, None)

# Example 5:
This example implements an own Node that just forwards all input bytes incremented by 1

class NodeTest(mt.Node):
    def __init__(self, app, uid = ''):
        mt.Node.__init__(self, app, uid)

    def recv(self, ba, caller):
        nba = map(lambda x: x+1, ba)
        for ch in self.ch['_']:
        ch.recv(nba, self)

app = mt.Multiterm()
key = app.nodeKeyboard('key')
tst = NodeTest(app)
t0 = app.nodeText(wx.RED)

key.append_receiver(tst)
tst.append_receiver(t0)

