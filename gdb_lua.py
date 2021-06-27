#!/bin/env python3
import itertools
import sys
import typing

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

G: typing.Optional['Lua'] = None

class LuaInitializationFailed(Exception): pass

class RawTypeTag(object):
    __slots__ = ('v',)
    def __init__(self, tt: int):
        self.v = tt

class TypeTag(object):
    __slots__ = ('v',)
    def __init__(self, tt: RawTypeTag):
        self.v = tt.v & TTYPE_MASK

class TypeVariant(object):
    __slots__ = ('v',)
    def __init__(self, tt: RawTypeTag):
        self.v = (tt.v >> 4) & 0b11

class GDBValue(object):
    def __init__(self, v: gdb.Value):
        self.v = v

class LuaState(GDBValue): pass
class StkId(GDBValue): pass
class Hash(GDBValue): pass
class HashNode(GDBValue): pass
class TValue(GDBValue): pass
class Value(GDBValue): pass
class TString(GDBValue): pass

def idx_or_none(v: typing.Mapping[int, typing.Any], i: int):
    return v[i] if i < len(v) else None

def ttype(v: TValue) -> TypeTag: return TypeTag(RawTypeTag(v.v['tt_']))
def tvalue(v: TValue) -> Value: return Value(v.v['value_'])
def array_cap(l: 'Lua', h: Hash) -> int: return int(l.alimit(h).cast(l.int_t))
def hash_cap(h: Hash) -> int: return 1 << int(h.v['lsizenode'])

def is_lua_closure(tt: RawTypeTag) -> bool: return TypeVariant(tt).v == 0
def is_light_cfunction(tt: RawTypeTag) -> bool: return TypeVariant(tt).v == 1
def is_c_closure(tt: RawTypeTag) -> bool: return TypeVariant(tt).v == 2

def is_lua_53() -> bool:
    f = 'lua_newuserdatauv'
    try:
        gdb.parse_and_eval(f)
        return False
    except gdb.error as e:
        arg = e.args[0]
        if arg != f'No symbol "{f}" in current context.':
            raise
        return True

def lookup_type(name: str) -> typing.Optional[gdb.Type]:
    try:
        return gdb.lookup_type(name)
    except gdb.error:
        gdb.write(f'type "{name}" not found\n', gdb.STDERR)
    return None

def iter_stack(L: LuaState) -> typing.Iterator[StkId]:
    s, t = L.v['stack'] + 1, L.v['top']
    while s != t:
        yield StkId(s)
        s += 1

def stack_idx(L: LuaState, i: int) -> typing.Optional[StkId]:
    s, t = L.v['stack'], L.v['top']
    if 0 < i and i < t - s:
        return StkId(s + i)
    return None

def iter_array(h: Hash, cap: int) -> typing.Iterator[tuple[int, TValue]]:
    a = h.v['array']
    for i in range(1, cap + 1):
        if ttype(TValue(a.dereference())).v == LUA_TNIL:
            break
        yield i, TValue(a)
        a += 1

def iter_hash(h: Hash, cap: int) -> typing.Iterator[HashNode]:
    n = h.v['node']
    for _ in range(0, cap):
        yield HashNode(n)
        n += 1

def make_command(
    doc: str,
    invoke: typing.Optional[typing.Callable],
    *args, **kwargs,
) -> gdb.Command:
    class Command(gdb.Command):
        def __init__(self):
            super(Command, self).__init__(*args, **kwargs)
    Command.__doc__ = doc
    if invoke:
        Command.invoke = invoke
    Command()

class ValuePrinter(object):
    'Shared implementation of printers for types that contain a `struct Value`.'
    def __init__(self, val: Value, tt: RawTypeTag):
        self.val = val
        self.type = tt

    def display_hint(self) -> typing.Optional[str]:
        tt = TypeTag(self.type)
        if tt.v == LUA_TSTRING:
            return 'string'
        elif tt.v == LUA_TTABLE:
            return 'map'
        return None

    def to_string(self):
        return lua().dump(self.val, self.type)

    def children(self) -> typing.Union[tuple, typing.Iterator]:
        if TypeTag(self.type).v != LUA_TTABLE:
            return ()
        l = lua()
        h = Hash(l.gc(self.val)['h'])
        cap, hcap = array_cap(l, h), hash_cap(h)
        hash_kv = l.hash_kv
        return itertools.chain(
            itertools.chain.from_iterable(
                (('', str(i)), ('', x.v.dereference()))
                for i, x in iter_array(h, cap)),
            itertools.chain.from_iterable(
                (('', x[0]), ('', x[1]))
                for x in map(hash_kv, iter_hash(h, hcap)) if x))

class TValuePrinter(object):
    'Printer for tagged values.'
    @classmethod
    def create(cls, val: gdb.Value) -> typing.Optional['TValuePrinter']:
        if str(val.type) in ('TValue', 'struct TValue'):
            return cls(TValue(val))
        return None

    def __init__(self, val: TValue):
        self.value = ValuePrinter(tvalue(val), RawTypeTag(val.v['tt_']))

    def display_hint(self): return self.value.display_hint()
    def to_string(self): return self.value.to_string()
    def children(self): return self.value.children()

class NodeKeyPrinter(object):
    'Printer for hash table nodes.'
    @classmethod
    def create(cls, val: gdb.Value):
        if str(val.type) in ('NodeKey', 'struct NodeKey'):
            return cls(HashNode(val))

    def __init__(self, n: HashNode):
        self.value = ValuePrinter(
            Value(n.v['key_val']),
            RawTypeTag(n.v['key_tt']))

    def display_hint(self): return self.value.display_hint()
    def to_string(self): return self.value.to_string()
    def children(self): return self.value.children()

class Lua(object):
    def __init__(self):
        types = list(map(lookup_type, (
            'lua_State', 'TValue', 'union GCUnion', 'LClosure')))
        if not all(types):
            raise LuaInitializationFailed(
                'failed to find types in debugging info')
        self.lua_state, self.tvalue, gc_union, lclosure = types
        self.gc_union_p = gc_union.pointer()
        self.lclosure_p = lclosure.pointer()
        self.int_t = gdb.lookup_type('int')
        self.void_p = gdb.lookup_type('void').pointer()
        self.char_p = gdb.lookup_type('char').pointer()

    def stkid_to_value(_self, _v: StkId) -> TValue:
        raise NotImplementedError()
    def toboolean(_self, _v, _tt) -> bool: raise NotImplementedError()
    def isinteger(_self, _tt: RawTypeTag) -> bool:
        raise NotImplementedError()
    def string_contents(_self, _s: TString) -> gdb.Value:
        raise NotImplementedError()
    def alimit(self, _h: Hash) -> gdb.Value: raise NotImplementedError()
    def uv(_self, _v: gdb.Value) -> tuple[gdb.Value, str]:
        raise NotImplementedError()
    @staticmethod
    def hash_kv(n: HashNode) -> tuple[TValue, TValue]:
        raise NotImplementedError()

    def gc(self, v: Value):
        return v.v['gc'].cast(self.gc_union_p)

    def dump_stack(self, L: LuaState, i: typing.Optional[int]=None):
        if i is not None:
            return self.dump_stack_idx(L, int(i))
        for i, v in enumerate(iter_stack(L)):
            val = self.stkid_to_value(v)
            tt = ttype(val)
            gdb.write(f'{i + 1}: {v.v} {TYPE_NAMES[tt.v]} {val.v}\n')

    def dump_stack_idx(self, L: LuaState, i: int):
        v = stack_idx(L, i)
        if v is None:
            raise Exception(f'invalid stack index: {i}')
        val = self.stkid_to_value(v)
        tt = ttype(val)
        gdb.write(f'{TYPE_NAMES[tt.v]} {val.v}\n')

    def dump(self, v: Value, tt: RawTypeTag):
        i = min(TypeTag(tt).v, len(self._DUMP) - 1)
        return self._DUMP[i](self, v, tt)

    def _dump_unknown(self, v: Value, _tt):
        return v

    def _dump_nil(_self, _v, _tt):
        return 'nil'

    def _dump_boolean(self, v: Value, tt: RawTypeTag):
        return str(int(self.toboolean(v, tt)))

    def _dump_lightuserdata(self, v: Value, _tt):
        return v.v['p']

    def _dump_number(self, v: Value, tt: RawTypeTag):
        if self.isinteger(tt):
            return v.v['i']
        return v.v['n']

    def _dump_string(self, v: Value, _tt):
        return self.string_contents(TString(self.gc(v)['ts'])).cast(self.char_p)

    def _dump_table(self, v: Value, _tt):
        h = Hash(self.gc(v)['h'])
        cap, hcap = array_cap(self, h), hash_cap(h)
        length = sum(1 for _ in iter_array(h, cap))
        hlength = sum(
            1 for x in iter_hash(h, hcap)
            if ttype(TValue(x.v['i_val'])).v != LUA_TNIL)
        return (
            f'(array_capacity: {cap}, length: {length},'
            f' hash_capacity: {hcap}, hash_length: {hlength})')

    def _dump_function(self, v: Value, raw_tt: RawTypeTag):
        if is_lua_closure(raw_tt):
            p = v.v.cast(self.lclosure_p)
            return f'lclosure {p}'
        if is_light_cfunction(raw_tt):
            return f'cfunction {v.v["p"]}'
        if is_c_closure(raw_tt):
            cl = self.gc(v)['cl']['c']
            return f'cclosure {cl["f"]} (nupvalues: {int(cl["nupvalues"])})'

    def _dump_userdata(self, v: Value, _tt):
        u = self.gc(v)['u']
        uv, nuv = self.uv(u)
        return f'{uv} ({nuv}size: {u["len"]})'

    def _dump_thread(self, v: Value, _tt):
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
        types = list(map(lookup_type, (('TString', 'Udata'))))
        if not all(types):
            raise LuaInitializationFailed(
                'failed to find types in debugging info')
        tstring, udata = types
        self.tstring_size = max(max_size, tstring.sizeof)
        self.udata_size = max(max_size, udata.sizeof)

    def stkid_to_value(self, v: StkId):
        return TValue(v.v.dereference())
    def toboolean(self, v: Value, _tt):
        return v.v['b']
    def isinteger(self, tt: RawTypeTag) -> bool:
        return bool(TypeVariant(tt).v)
    def string_contents(self, s: TString):
        return self.data_suffix(s.v.address, self.tstring_size)
    def alimit(self, h: Hash) -> gdb.Value:
        return h.v['sizearray']
    def uv(self, v: gdb.Value) -> tuple[gdb.Value, str]:
        return (self.data_suffix(v.address, self.udata_size), '')
    def data_suffix(self, ptr, size):
        return (ptr.cast(self.char_p) + size).cast(self.void_p)

    def calc_max_size(self):
        # No good way to find this because the types used for alignment are not
        # present in the debug information.
        types = list(map(lookup_type, ('lua_Integer', 'lua_Number')))
        if not all(types):
            raise LuaInitializationFailed(
                'failed to find types in debugging info')
        return max(
            x.sizeof for x in (
                gdb.lookup_type('double'), gdb.lookup_type('long'),
                self.void_p, *types))

    @staticmethod
    def hash_kv(n: HashNode):
        v = n.v['i_val']
        if ttype(TValue(v)).v != LUA_TNIL:
            return n.v['i_key']['tvk'], v

class Lua54(Lua):
    def stkid_to_value(self, v: StkId):
        return TValue(v.v['val'])
    def toboolean(self, _v, tt: RawTypeTag):
        return bool(TypeVariant(tt).v)
    def isinteger(self, tt: RawTypeTag):
        return not bool(TypeVariant(tt).v)
    def string_contents(self, s: TString):
        return s.v['contents']
    def alimit(self, h: Hash) -> gdb.Value:
        return h.v['alimit']

    def uv(self, v: gdb.Value) -> tuple[gdb.Value, str]:
        return (
            v["uv"]["uv"].address.cast(self.void_p),
            f'nuvalue: {v["nuvalue"]}, ')

    @staticmethod
    def hash_kv(n: HashNode):
        v = n.v['i_val']
        if ttype(TValue(v)).v != LUA_TNIL:
            return n.v['u'], v

def lua() -> Lua:
    global G
    if G is None:
        if is_lua_53():
            G = Lua53()
        else:
            G = Lua54()
    return G

def cmd_stack(_, arg: str, _from_tty):
    args = gdb.string_to_argv(arg)
    lua().dump_stack(
        LuaState(gdb.parse_and_eval(idx_or_none(args, 0) or 'L')),
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
