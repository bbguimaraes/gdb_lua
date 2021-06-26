#!/bin/env python3
import itertools
import sys

import gdb

HELP_LUA = 'Commands to inspect Lua states.'
HELP_STACK = '''\
Prints the values on the stack associated with a Lua state.

Positional arguments (all optional) are:

- L: the expression identifying the current Lua state (default: `L`)
- i: the stack index to print (default: all)\
'''

TTYPE_MASK = 0b1111

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
    'thread',
)

G = None

class LuaInitializationFailed(Exception): pass

def idx_or_none(v, i): return v[i] if i < len(v) else None

def ttype(v): return v['tt_'] & TTYPE_MASK
def tvalue(v): return v['value_']
def variant(tt): return (tt >> 4) & 0b11
def array_cap(l, v): return int(l.alimit(v).cast(l.int_t))
def hash_cap(v): return 1 << int(v['lsizenode'])

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

def stack_idx(L, i):
    s, t = L['stack'], L['top']
    if 0 < i and i < t - s:
        return s + i

def iter_array(h, cap):
    a = h['array']
    for i in range(1, cap + 1):
        if ttype(a.dereference()) == LUA_TNIL:
            break
        yield i, a
        a += 1

def iter_hash(h, cap):
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

class Value(object):
    'Shared implementation of printers for types that contain a `struct Value`.'
    def __init__(self, val, tt):
        self.val = val
        self.type = tt

    def display_hint(self):
        tt = self.type & TTYPE_MASK
        if tt == LUA_TSTRING:
            return 'string'
        elif tt == LUA_TTABLE:
            return 'map'

    def to_string(self):
        return lua().dump(self.val, self.type)

    def children(self):
        if self.type & TTYPE_MASK != LUA_TTABLE:
            return ()
        l = lua()
        h = l.gc(self.val)['h']
        cap, hcap = array_cap(l, h), hash_cap(h)
        hash_kv = l.hash_kv
        return itertools.chain(
            itertools.chain.from_iterable(
                (('', str(i)), ('', x.dereference()))
                for i, x in iter_array(h, cap)),
            itertools.chain.from_iterable(
                (('', x[0]), ('', x[1]))
                for x in map(hash_kv, iter_hash(h, hcap)) if x))

class TValuePrinter(object):
    'Printer for tagged values.'
    @classmethod
    def create(cls, val):
        if str(val.type) in ('TValue', 'struct TValue'):
            return cls(val)

    def __init__(self, val): self.value = Value(tvalue(val), val['tt_'])
    def display_hint(self): return self.value.display_hint()
    def to_string(self): return self.value.to_string()
    def children(self): return self.value.children()

class NodeKeyPrinter(object):
    'Printer for hash table nodes.'
    @classmethod
    def create(cls, val):
        if str(val.type) in ('NodeKey', 'struct NodeKey'):
            return cls(val)

    def __init__(self, val): self.value = Value(val['key_val'], val['key_tt'])
    def display_hint(self): return self.value.display_hint()
    def to_string(self): return self.value.to_string()
    def children(self): return self.value.children()


class Lua(object):
    def __init__(self):
        types = list(map(lookup_type, ('lua_State', 'TValue', 'union GCUnion')))
        if not all(types):
            raise LuaInitializationFailed(
                'failed to find types in debugging info')
        self.lua_state, self.tvalue, gc_union = types
        self.gc_union_p = gc_union.pointer()
        self.int_t = gdb.lookup_type('int')
        self.void_p = gdb.lookup_type('void').pointer()
        self.char_p = gdb.lookup_type('char').pointer()

    def gc(self, v):
        return v['gc'].cast(self.gc_union_p)

    def dump_stack(self, L, i=None):
        if i is not None:
            return self.dump_stack_idx(L, int(i))
        for i, v in enumerate(iter_stack(L)):
            val = self.stkid_to_value(v)
            tt = ttype(val)
            gdb.write(f'{i + 1}: {v} {TYPE_NAMES[tt]} {val}\n')

    def dump_stack_idx(self, L, i):
        v = stack_idx(L, i)
        if v is None:
            raise Exception(f'invalid stack index: {i}')
        val = self.stkid_to_value(v)
        tt = ttype(val)
        gdb.write(f'{TYPE_NAMES[tt]} {val}\n')

    def dump(self, v, tt):
        i = min(tt & TTYPE_MASK, len(self._DUMP) - 1)
        return self._DUMP[i](self, v, tt)

    def _dump_unknown(self, v, _tt):
        return v

    def _dump_nil(*_):
        return 'nil'

    def _dump_boolean(self, v, tt):
        return str(int(self.toboolean(v, tt)))

    def _dump_lightuserdata(self, v, _tt):
        return v['p']

    def _dump_number(self, v, tt):
        if self.isinteger(tt):
            return v['i']
        return v['n']

    def _dump_string(self, v, _tt):
        return self.string_contents(self.gc(v)['ts']).cast(self.char_p)

    def _dump_table(self, v, _tt):
        return self.dump_table(v)

    def _dump_table(self, v, _tt):
        h = self.gc(v)['h']
        cap, hcap = array_cap(self, h), hash_cap(h)
        length = sum(1 for _ in iter_array(h, cap))
        hlength = sum(
            1 for x in iter_hash(h, hcap)
            if ttype(x['i_val']) != LUA_TNIL)
        return (
            f'(array_capacity: {cap}, length: {length},'
            f' hash_capacity: {hcap}, hash_length: {hlength})')

    def _dump_function(self, v, tt):
        tt = int(tt)
        if is_lua_closure(tt):
            return 'lclosure'
        if is_light_cfunction(tt):
            return f'cfunction {v["p"]}'
        if is_c_closure(tt):
            cl = self.gc(v)['cl']['c']
            return f'cclosure {cl["f"]} (nupvalues: {int(cl["nupvalues"])})'

    def _dump_userdata(self, v, _tt):
        u = self.gc(v)['u']
        uv, nuv = self.uv(u)
        return f'{uv} ({nuv}size: {u["len"]})'

    def _dump_thread(self, v, _tt):
        return f'{self.gc(v)["th"].address}'

    _DUMP = (
        _dump_nil,
        _dump_boolean,
        _dump_lightuserdata,
        _dump_number,
        _dump_string,
        _dump_table,
        _dump_function,
        _dump_userdata,
        _dump_thread,
        _dump_unknown,
    )


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
    def toboolean(self, v, _tt):
        return v['b']
    def isinteger(self, tt):
        return bool(variant(tt))
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

    @staticmethod
    def hash_kv(n):
        v = n['i_val']
        if ttype(v) != LUA_TNIL:
            return n['i_key']['tvk'], v


class Lua54(Lua):
    def stkid_to_value(self, x):
        return x['val']
    def toboolean(self, _v, tt):
        return bool(variant(tt))
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

    @staticmethod
    def hash_kv(n):
        v = n['i_val']
        if ttype(v) != LUA_TNIL:
            return n['u'], v

def lua():
    global G
    if G is None:
        if is_lua_53():
            G = Lua53()
        else:
            G = Lua54()
    return G

def cmd_stack(_, arg, _from_tty):
    args = gdb.string_to_argv(arg)
    lua().dump_stack(
        gdb.parse_and_eval(idx_or_none(args, 0) or 'L'),
        idx_or_none(args, 1))

def register_printers(obj):
    gdb.printing.register_pretty_printer(obj, TValuePrinter.create)
    gdb.printing.register_pretty_printer(obj, NodeKeyPrinter.create)

if __name__ == '__main__':
    register_printers(gdb.current_objfile())
    make_command(HELP_LUA, None, 'lua', gdb.COMMAND_RUNNING, prefix=True)
    make_command(
        HELP_STACK, cmd_stack, 'lua stack',
        gdb.COMMAND_RUNNING, gdb.COMPLETE_EXPRESSION)
