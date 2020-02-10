#! /usr/bin/python

"""
"""

import multiterm as mt
import serial
import wx

s0 = serial.Serial('/dev/tnt0', 9600, bytesize=8, parity='N', stopbits=1, timeout=0, xonxoff=0, rtscts=0)
s1 = serial.Serial('/dev/tnt1', 9600, bytesize=8, parity='N', stopbits=1, timeout=0, xonxoff=0, rtscts=0)

#s = mt.Settings()
app = mt.MTApp()
key = mt.MTNodeKeyboard(app)
ss0 = mt.MTNodeSerial(s0)
ss1 = mt.MTNodeSerial(s1)
t0 = mt.MTNodeText(app, wx.RED)
t1 = mt.MTNodeText(app, wx.BLUE)

key.append_child(ss0)
ss0.append_child(t0)
ss1.append_child(t1)

app.MainLoop()

