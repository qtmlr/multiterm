# Multi Term
Multi Term is a python3 library that helps you write your own terminal program.

## Features
- It handles several serial lines
- It is extensible by a node system

## Open
- get the classes from app, not from mt, no need to give app as parameter then
- python config file
- input char handling / key handling / getting shift etc. correct in wx
- use a python settings module for GUI position etc.
- node: byte seq: check that byte sequences are unique and don't contain each other
- node: wx.Button / wx.DropDown / wx.Statusbar / others?

## Done:
- implement as package
- node system
- node: keyboard sequence handling
- node: colored output
- node: log to file
- node: line buffering
- node: xfer protocol
- node: xfer out
- node: xfer in
- node: byte seq: make last char an asterisk / a parameter / a region
- node: hexdump output
- node: add caller id
- node: select / switch
- do not handle all ch the same in a node
- node: a second path apart from ch

## Layout
- menu bar
- status line: all the serials, where does keyboard go, ...
- mode selection
- text display
- node display

## Node System
- Node with children and proc() and recv(ba)
- forward byte array to Node()
- derive from Node in imported settings module
- list of root leafs in app, settings file can add more
- One Node for keyboard input
- several Node for serial input and also serial output
- keyboard: proc is called, call recv of the children
- serial in: in proc, read serial and directly call recv of the children
- serial out: call recv, data is written to serial

