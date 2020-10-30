#!/usr/bin/env python3
import gdb

from . import printing
from . import types

def _is_lua_53():
    return gdb.lookup_global_symbol('lua_newuserdatauv') is None

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
            val = self.stkid_to_value(v)
            tt = types.ttype(val)
            gdb.write(f'{i + 1}: {v} {types.TYPE_NAMES[tt]} ')
            printing.dump(self, val['tt_'], val['value_'])
            gdb.write('\n')

class Lua53(Lua):
    def __init__(self):
        super(Lua53, self).__init__()
        max_align = gdb.lookup_type('L_Umaxalign')
        tstring = gdb.lookup_type('TString')
        udata = gdb.lookup_type('Udata')
        self.tstring_size = max(tstring.sizeof, max_align.sizeof)
        self.udata_size = max(udata.sizeof, max_align.sizeof)

    def stkid_to_value(self, v):
        return v.dereference()
    def toboolean(self, v, _tt):
        return v['b']
    def isinteger(self, tt):
        return bool(types.variant(tt))
    def string_contents(self, s):
        return self.data_suffix(s.address, self.tstring_size) \
            .cast(self.char_p)
    def alimit(self, h):
        return h['sizearray']
    def uv(self, v):
        return (self.data_suffix(v.address, self.udata_size), None)
    def data_suffix(self, ptr, size):
        return (ptr.cast(self.char_p) + size).cast(self.void_p)

class Lua54(Lua):
    def stkid_to_value(self, v):
        return v['val']
    def toboolean(self, _v, tt):
        return bool(types.variant(tt))
    def isinteger(self, tt):
        return not bool(types.variant(tt))
    def string_contents(self, s):
        return s['contents'].cast(self.char_p)
    def alimit(self, h):
        # TODO isrealasize
        return h['alimit']
    def uv(self, v):
        return (
            v['uv']['uv'].address.cast(self.void_p),
            v['nuvalue'],
        )

def lua():
    if _is_lua_53():
        return Lua53()
    return Lua54()
