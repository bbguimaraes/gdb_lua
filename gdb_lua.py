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

class LuaInitializationFailed(Exception): pass

def ttype(v): return v['tt_'] & 0b1111
def tvalue(v): return v['value_']
def variant(tt): return (tt >> 4) & 0b11

def is_lua_closure(tt): return variant(tt) == 0
def is_light_cfunction(tt): return variant(tt) == 1
def is_c_closure(tt): return variant(tt) == 2

def is_lua_53():
    f = 'lua_newuserdatauv'
    try:
        gdb.parse_and_eval(f)
        return False
    except gdb.error as e:
        arg, *_ = *e.args, ''
        if arg != f'No symbol "{f}" in current context.':
            raise
        return True

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
            raise LuaInitializationFailed()
        self.lua_state, self.tvalue, gc_union = types
        self.gc_union_p = gc_union.pointer()
        self.int_t = gdb.lookup_type('int')
        self.void_p = gdb.lookup_type('void').pointer()
        self.char_p = gdb.lookup_type('char').pointer()

    def gc(self, v):
        return tvalue(v)['gc'].cast(self.gc_union_p)

    def dump_stack(self, L):
        for i, v in enumerate(iter_stack(L)):
            val = self.stkid_to_value(v)
            tt = ttype(val)
            gdb.write(f'{i + 1}: {v} {TYPE_NAMES[tt]}')
            self.DUMP[min(tt, len(self.DUMP) - 1)](self, val)
            gdb.write('\n')

    def dump_unknown(self, v):
        gdb.write(f' {v}')

    def dump_nil(*_):
        pass

    def dump_boolean(self, v):
        gdb.write(f' {int(self.toboolean(v))}')

    def dump_lightuserdata(self, v):
        gdb.write(f' {tvalue(v)["p"]}')

    def dump_number(self, v):
        if self.isinteger(v['tt_']):
            return gdb.write(f' {tvalue(v)["i"]}')
        gdb.write(f' {tvalue(v)["n"]}')

    def dump_string(self, v):
        s = self.string_contents(self.gc(v)['ts']).cast(self.char_p)
        gdb.write(f' {s}')

    def dump_table(self, v):
        gdb.write(f' {self.dump_table(v)}')

    def dump_table(self, v):
        h = self.gc(v)['h']
        cap = int(self.alimit(h).cast(self.int_t))
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
        uv, nuv = self.uv(u)
        gdb.write(f' {uv} ({nuv}size: {u["len"]})')

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


class Lua53(Lua):
    def __init__(self):
        super(Lua53, self).__init__()
        max_size = self.calc_max_size()
        if max_size is None:
            raise LuaInitializationFailed()
        types = list(map(lookup_type, (('TString', 'Udata'))))
        if not all(types):
            raise LuaInitializationFailed()
        tstring, udata = types
        self.tstring_size = max(max_size, tstring.sizeof)
        self.udata_size = max(max_size, udata.sizeof)

    def stkid_to_value(self, x):
        return x.dereference()
    def toboolean(self, x):
        return tvalue(x)['b']
    def isinteger(self, x):
        return bool(variant(x))
    def string_contents(self, x):
        return self.data_suffix(x.address, self.tstring_size)
    def alimit(self, x):
        return x['sizearray']
    def uv(self, x):
        return (self.data_suffix(x.address, self.udata_size), '')
    def data_suffix(self, ptr, size):
        return (ptr.cast(self.char_p) + size).cast(self.void_p)
    def calc_max_size(self):
        # No good way to find this because the types used for alignment are not
        # present in the debug information.
        types = list(map(lookup_type, ('lua_Integer', 'lua_Number')))
        if all(types):
            return max(
                x.sizeof for x in (
                    gdb.lookup_type('double'), gdb.lookup_type('long'),
                    self.void_p, *types))

class Lua54(Lua):
    def stkid_to_value(self, x):
        return x['val']
    def toboolean(self, x):
        return bool(variant(x['tt_']))
    def isinteger(self, x):
        return not bool(variant(x))
    def string_contents(self, x):
        return x['contents']
    def alimit(self, x):
        return x['alimit']
    def uv(self, x):
        return (
            x["uv"]["uv"].address.cast(self.void_p),
            f'nuvalue: {x["nuvalue"]}, ')

def lua():
    if is_lua_53():
        return Lua53()
    return Lua54()

if __name__ == '__main__':
    make_command(
        'Commands to inspect Lua states.',
        None, 'lua', gdb.COMMAND_RUNNING, prefix=True)
    make_command(
        'Print the values on the stack associated with a Lua state.',
        lambda _0, arg, *_1: lua().dump_stack(gdb.parse_and_eval(arg or 'L')),
        'lua stack', gdb.COMMAND_RUNNING, gdb.COMPLETE_EXPRESSION)
