#!/usr/bin/env python3
import gdb

from . import printing
from . import types

def _iter_stack(L):
    s, t = L['stack'] + 1, L['top']
    while s != t:
        yield s
        s += 1

class Lua(object):
    def __init__(self):
        self.lua_state = gdb.lookup_type('lua_State')
        self.tvalue = gdb.lookup_type('TValue')
        gc_union = gdb.lookup_type('union GCUnion')
        self.gc_union_p = gc_union.pointer()
        self.int_t = gdb.lookup_type('int')
        self.void_p = gdb.lookup_type('void').pointer()
        self.char_p = gdb.lookup_type('char').pointer()

    def gc(self, v):
        return v['gc'].cast(self.gc_union_p)

    def dump_stack(self, L):
        for i, v in enumerate(_iter_stack(L)):
            val = v['val']
            tt = types.ttype(val)
            gdb.write(f'{i + 1}: {v} {types.TYPE_NAMES[tt]} ')
            printing.dump(self, val['tt_'], val['value_'])
            gdb.write('\n')
