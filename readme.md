# Multi Term
A terminal program that handles several serial lines (in parallel)

## Features
- Handles several serial lines
- Extensible by a node system

## Open
- python config file
- input char handling / key handling
- keyboard sequence handling
- node: line buffering
- node: xfer protocol
- do not handle all ch the same in a node

## Done:
- node: colored output
- importing a python settings module
- filter system
- node: log to file
- implement as package

## Layout
- menu bar
- status line: all the serials, where does keyboard go, ...
- mode selection
- text display
- node display

## Filter System
- MTNode with children and proc() and recv(ba)
- forward byte array to MTNode()
- derive from MtNode in imported settings module
- list of root leafs in app, settings file can add more
- One MTNode for keyboard input
- several MTNode for serial input and also serial output
- keyboard: proc is called, call recv of the children
- serial in: in proc, read serial and directly call recv of the children
- serial out: call recv, data is written to serial

