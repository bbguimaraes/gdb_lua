#!/usr/bin/env python3
import typing

import gdb

from . import lua
from . import printing
from . import types

HELP_LUA = 'Commands to inspect Lua states.'
HELP_STACK = '''\
Prints the values on the stack associated with a Lua state.

Positional arguments (all optional) are:

- L: the expression identifying the current Lua state (default: `L`)
- i: the stack index to print (default: all)\
'''

def _make_command(
    doc: str,
    invoke: typing.Optional[typing.Callable],
    *args, **kwargs,
):
    class Command(gdb.Command):
        def __init__(self):
            super(Command, self).__init__(*args, **kwargs)
    Command.__doc__ = doc
    if invoke:
        Command.invoke = invoke # type: ignore
    Command()

def _cmd_stack(_, arg: str, _from_tty):
    args = gdb.string_to_argv(arg)
    lua.lua().dump_stack(
        types.LuaState(gdb.parse_and_eval(lua.idx_or_none(args, 0) or 'L')),
        lua.idx_or_none(args, 1))

def _register_printers(obj):
    gdb.printing.register_pretty_printer(obj, printing.TValuePrinter.create)
    gdb.printing.register_pretty_printer(obj, printing.NodeKeyPrinter.create)

_register_printers(gdb.current_objfile())
_make_command(HELP_LUA, None, 'lua', gdb.COMMAND_RUNNING, prefix=True)
_make_command(
    HELP_STACK, _cmd_stack, 'lua stack',
    gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
