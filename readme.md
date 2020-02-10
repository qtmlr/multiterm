# Multi Term
A terminal program that handles several serial lines at once (in parallel)

## Features


## Open
- log to file
- own protocols
- filter system
- python config file
- configured by a python file
- input char handling / key handling

## Done:
- colored output
- importing a python settings module

## Layout
- menu bar
- status line: all the serials, where does keyboard go, ...
- mode selection
- text display
- node display

## Filter System
- MTNode with children and proc()
- forward byte array to MTNode()
- derive from MtNode in imported settings module
- list of root leafs in app, settings file can add more
- One MTNode for keyboard input
- several MTNode for serial input and also serial output
- keyboard: proc is called, call recv of the children
- serial in: in proc, read serial and directly call recv of the children
- serial out: call recv, data is written to serial

