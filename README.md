# MultiTerm
MultiTerm is a python3 library that helps you write your own terminal program.

## Features
- It can handle several serial lines
- It is extensible by a node system
- You can also write your own nodes to extend Multiterm
- It is based on wx_python and can be extended by wx.Button, wx.Choice, wx.Statusbar

## Warning
The keyboard handling in wx_python seems a bit odd, I did not manage to get the real keyboard character, e.g. if on your keyboard there is the key '+' and shift-'+' is really a '\*', then the '\*' will not appear, shift-'+' will only lead to a normal '+'.
Any help here is appreciated.

## Nodes
The Nodes are an important part of MultiTerm.  Here are some features of the Nodes:
- Nodes can behave as input and/or output Nodes.
- Input Nodes can receive data from other Nodes.
- Output Nodes can forward data to other Nodes that were registered to them.
- Data to/from Nodes are always in the form of bytearray()s.
- A fix output Node (implemented as a singleton) already exists that outputs any key presses to its receivers.
- Several input Nodes can be instantiated (with a color parameter) that displays its input in the specified color in the apps text panel.
- Several Nodes exist that receive input, process it and output the processed data to the registered receiver Nodes.
- Nodes can optionally receive a unique ID during construction to identify these Nodes.

An example:
```python
class NodeNothing(mt.Node):
    def __init__(self, app, uid = ''):
        mt.Node.__init__(self, app, uid)

    def recv(self, ba, caller_uid):
        for ch in self.ch['_']:
            ch.recv(ba, self)

app = mt.MultiTerm()
key = app.nodeKeyboard('my_key')
nothing = NodeNothing(app)
t0 = app.nodeText(wx.RED, 'red_text')
t1 = app.nodeText(wx.BLUE, 'blue_text')
key.append_receiver(nothing)
nothing.append_receiver(t0, t1) # append_receiver can take more than one parameter
```
The form ```node = app.nodeSomthing()``` are convenience functions and can also be formulated ```node = mt.NodeSomething(app)```.
When ```key``` is instantiated, the UID ```'my_key'``` is given as a parameter.
In ```key```, any keypress is placed into a ```ba = bytearray()``` and the list of receivers is iterated.
Each receivers function ```node.recv(ba, caller_uid)``` is called.
```caller_uid``` in this case is ```'my_key'```.
Now the method ```recv()``` of ```nothing = NodeNothing()``` is called which directly forwards
the information in ```ba``` to its receivers, which are the two ```NodeText()```.
This way the output of ```key``` is displayed in RED and in BLUE in the text window.

The following Nodes are already available in MultiTerm:
- NodeKeyboard(): outputs any key presses.
- NodeSerial(serial): outputs any received characters, any received data is output on the serial line.  The serial line must be instantiated beforehand and passed as a parameter.  The parameter ```timeout``` must be set to 0.
- NodeText(color): displays any received data in the text panel in the given color.
- NodeLogfile(filename): writes any input into the file.  The file is overwritten silently if it exists before.
- NodeSeqCheck(...): triggers user-defined actions based on the input data that is received.
- NodeLinebuffer(): collects any input data and only passes them on to its receivers when a newline character is received.
- NodeHex(): converts its input into a hexadecimal representation and outputs it to its receivers.
- NodeSelect(): it can receive data from several Nodes and each input can selectively be enabled / disabled.  Only the enabled inputs data are forwarded to the receivers.  Enabling / disabling is done by this Nodes methods ```enable(caller_uid)``` / ```disable(caller_uid)```.


## Examples
In the following, some example code is given that should represent the features of MultiTerm.

### Example 1
In this example the linux kernel module [tty0tty](https://github.com/lcgamboa/tty0tty) is used.
This example:
- opens two serial lines
- the keyboard input is written to the second serial line
- the input from the serial lines is displayed in different colors

```python
import multiterm as mt
import serial
import wx

app = mt.MultiTerm()

# for any serial, timeout = 0 is important, else the call to read() blocks
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
```

The following examples don't use the serial line at all, they just demonstrate the features of the node system.
Also, the import statements and the call to app.MainLoop() are skipped, they are though necessary in all examples.

### Example 2
This example:
- uses a sequence checker, that checks the input stream for a certain sequence of bytes
- calls functions based on the input sequences
- redirects the output to the text window

```python
def func1(app, dta, last_byte):
    print("FUNC1", last_byte)

app = mt.MultiTerm()

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
```

### Example 3
This example:
- logs all keyboard input into a file
- does line buffering of the input and outputs only complete lines to the text window

```python
app = mt.Multiterm()
key = app.nodeKeyboard()
t0 = app.nodeText(wx.RED)
logf = app.nodeLogfile("output.log")
lbuf = app.nodeLinebuffer()

key.append_receiver(logf)
key.append_receiver(lbuf)
lbuf.append_receiver(t0)
```

### Example 4
This example:
- checks the keyboard input for the sequence ESC-a and then toggles the input of a selector
- the selector either outputs the keyboard or the keyboard hexdump to the text output

```python
toggle = True

app = mt.Multiterm()
sel = app.nodeSelect()

def func2(app, dta, last_byte):
    toggle = not toggle
    if toggle:
        sel.enable('hdump')
        sel.disable('key')
    else:
        sel.enable('key')
        sel.disable('hdump')

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
func1(None, None, None)
```

### Example 5:
This example implements an own Node that just forwards all input bytes incremented by 1

```python
class NodeTest(mt.Node):
    def __init__(self, app, uid = ''):
        mt.Node.__init__(self, app, uid)

    def recv(self, ba, caller):
        nba = bytearray(map(lambda x: x+1, ba))
        for ch in self.ch['_']:
        ch.recv(nba, self)

app = mt.Multiterm()
key = app.nodeKeyboard('key')
tst = NodeTest(app)
t0 = app.nodeText(wx.RED)

key.append_receiver(tst)
tst.append_receiver(t0)
```

### Example 6:
```python
def func3(evt):
    print("CLICKED " + str(evt))

def func4(evt):
    print("CHOICE " + evt.GetString())

sbar = app.addStatusBar()
sbar.SetStatusText("Hi there")
app.addButton("My Button", func3)
app.addChoice(['Option A', 'Option B', 'Option C'], func4)

```
