#!/usr/bin/env python3
import gdb

from . import lua

HELP_LUA = 'Commands to inspect Lua states.'
HELP_STACK = 'Prints the values on the stack associated with a Lua state.'

def _make_command(doc, invoke, *args, **kwargs):
    class Command(gdb.Command):
        def __init__(self):
            super(Command, self).__init__(*args, **kwargs)
    Command.__doc__ = doc
    if invoke:
        Command.invoke = invoke
    Command()

def _cmd_stack(_0, arg, _1):
    lua.lua().dump_stack(gdb.parse_and_eval(arg or 'L'))

_make_command(HELP_LUA, None, 'lua', gdb.COMMAND_RUNNING, prefix=True)
_make_command(
    HELP_STACK, _cmd_stack, 'lua stack',
    gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
