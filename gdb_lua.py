#!/bin/env python3
import sys

import gdb

LUA_TNIL = 0
LUA_TBOOLEAN = 1
LUA_TLIGHTUSERDATA = 2
LUA_TNUMBER = 3
LUA_TSTRING = 4
LUA_TTABLE = 5
LUA_TFUNCTION = 6
LUA_TUSERDATA = 7
LUA_TTHREAD = 8
TYPE_NAMES = (
    'nil',
    'boolean',
    'lightuserdata',
    'number',
    'string',
    'table',
    'function',
    'userdata',
    'thread')

def ttype(v): return v['tt_'] & 0x0f
def tvalue(v): return v['value_']
def variant(tt): return (tt >> 4) & 0b11

def isinteger(tt): return not variant(tt)
def is_lua_closure(tt): return variant(tt) == 0
def is_light_cfunction(tt): return variant(tt) == 1
def is_c_closure(tt): return variant(tt) == 2
def toboolean(tt): return bool(variant(tt))

def lookup_type(name):
    try:
        return gdb.lookup_type(name)
    except gdb.error:
        gdb.write(f'type "{name}" not found\n', gdb.STDERR)

def iter_stack(L):
    s, t = L['stack'] + 1, L['top']
    while s != t:
        yield s
        s += 1

def iter_array(h, cap):
    a = h['array']
    for i in range(1, cap + 1):
        if ttype(a.dereference()) == LUA_TNIL:
            break
        yield i, a
        a += 1

def iter_array(h, cap):
    n = h['node']
    for _ in range(0, cap):
        yield n
        n += 1

def make_command(doc, invoke, *args, **kwargs):
    class Command(gdb.Command):
        def __init__(self):
            super(Command, self).__init__(*args, **kwargs)
    Command.__doc__ = doc
    if invoke:
        Command.invoke = invoke
    Command()

class Lua(object):
    def __init__(self):
        types = list(map(lookup_type, ('lua_State', 'TValue', 'union GCUnion')))
        if not all(types):
            return
        self.lua_state, self.tvalue, gc_union = types
        self.gc_union_p = gc_union.pointer()
        self.int_t = gdb.lookup_type('int')
        self.void_p = gdb.lookup_type('void').pointer()
        self.char_p = gdb.lookup_type('char').pointer()

    def gc(self, v):
        return tvalue(v)['gc'].cast(self.gc_union_p)

    def dump_stack(self, L):
        for i, v in enumerate(iter_stack(L)):
            val = v['val']
            tt = ttype(val)
            gdb.write(f'{i + 1}: {v} {TYPE_NAMES[tt]}')
            self.DUMP[min(tt, len(self.DUMP) - 1)](self, val)
            gdb.write('\n')

    def dump_unknown(self, v):
        gdb.write(f' {v}')

    def dump_nil(*_):
        pass

    def dump_boolean(self, v):
        gdb.write(f' {int(toboolean(v["tt_"]))}')

    def dump_lightuserdata(self, v):
        gdb.write(f' {tvalue(v)["p"]}')

    def dump_number(self, v):
        if isinteger(v['tt_']):
            return gdb.write(f' {tvalue(v)["i"]}')
        gdb.write(f' {tvalue(v)["n"]}')

    def dump_string(self, v):
        s = self.gc(v)['ts']['contents'].cast(self.char_p)
        gdb.write(f' {s}')

    def dump_table(self, v):
        gdb.write(f' {self.dump_table(v)}')

    def dump_table(self, v):
        h = self.gc(v)['h']
        cap = int(h['alimit'].cast(self.int_t))
        length = sum(1 for _ in iter_array(h, cap))
        hash_cap = 1 << int(h['lsizenode'])
        hash_length = sum(
            1 for x in iter_array(h, hash_cap)
            if ttype(x['i_val']) != LUA_TNIL)
        s = (
            f'(array_capacity: {cap}, length: {length},'
            f' hash_capacity: {hash_cap}, hash_length: {hash_length})')
        gdb.write(f' {s}')

    def dump_function(self, v):
        tt = int(v['tt_'])
        if is_lua_closure(tt):
            return gdb.write(' lclosure')
        if is_light_cfunction(tt):
            return gdb.write(f' cfunction {tvalue(v)["p"]}')
        if is_c_closure(tt):
            cl = self.gc(v)['cl']['c']
            return gdb.write(
                f' cclosure {cl["f"]} (nupvalues: {int(cl["nupvalues"])})')

    def dump_userdata(self, v):
        u = self.gc(v)['u']
        uv = u["uv"]["uv"].address.cast(self.void_p)
        gdb.write(f' {uv} (nuvalue: {u["nuvalue"]}, size: {u["len"]})')

    def dump_thread(self, v):
        gdb.write(f' {self.gc(v)["th"].address}')

    DUMP = (
        dump_nil,
        dump_boolean,
        dump_lightuserdata,
        dump_number,
        dump_string,
        dump_table,
        dump_function,
        dump_userdata,
        dump_thread,
        dump_unknown)


if __name__ == '__main__':
    make_command(
        'Commands to inspect Lua states.',
        None, 'lua', gdb.COMMAND_RUNNING, prefix=True)
    make_command(
        'Print the values on the stack associated with a Lua state.',
        lambda _0, arg, *_1: Lua().dump_stack(gdb.parse_and_eval(arg or 'L')),
        'lua stack', gdb.COMMAND_RUNNING, gdb.COMPLETE_EXPRESSION)
