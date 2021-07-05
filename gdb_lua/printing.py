#!/usr/bin/env python3
import itertools
import typing

import gdb

from . import lua
from . import types

class ValuePrinter(object):
    'Shared implementation of printers for types that contain a `struct Value`.'
    def __init__(self, v: types.Value, tt: types.RawTypeTag):
        self.v = v
        self.tt = tt

    def display_hint(self) -> typing.Optional[str]:
        tt = types.TypeTag(self.tt)
        if types.is_string(tt):
            return 'string'
        elif types.is_table(tt):
            return 'map'
        return None

    def to_string(self):
        return dump(lua.lua(), self.v, self.tt)

    def children(self) -> typing.Union[tuple, typing.Iterator]:
        if not types.is_table(types.TypeTag(self.tt)):
            return ()
        l = lua.lua()
        h = l.gc(self.v).to_hash()
        cap, hcap = types.array_cap(l, h), types.hash_cap(h)
        hash_kv = l.hash_kv
        return itertools.chain(
            itertools.chain.from_iterable(
                (('', str(i)), ('', x.v.dereference()))
                for i, x in _iter_array(h, cap)),
            itertools.chain.from_iterable(
                (('', x[0].v), ('', x[1].v))
                for x in map(hash_kv, _iter_hash(h, hcap)) if x))

class TValuePrinter(object):
    'Printer for tagged values.'
    @classmethod
    def create(cls, v: gdb.Value) -> typing.Optional['TValuePrinter']:
        if str(v.type.unqualified()) in ('TValue', 'struct TValue'):
            return cls(types.TValue(v))
        return None

    def __init__(self, v: types.TValue):
        self.value = ValuePrinter(types.tvalue(v), types.tt(v))

    def display_hint(self): return self.value.display_hint()
    def to_string(self): return self.value.to_string()
    def children(self): return self.value.children()

class NodeKeyPrinter(object):
    'Printer for hash table nodes.'
    @classmethod
    def create(cls, v: gdb.Value) -> typing.Optional['NodeKeyPrinter']:
        if str(v.type.unqualified()) in ('NodeKey', 'struct NodeKey'):
            return cls(types.HashNode(v))
        return None

    def __init__(self, v: types.HashNode):
        self.value = ValuePrinter(v.key_value(), v.key_tt())

    def display_hint(self): return self.value.display_hint()
    def to_string(self): return self.value.to_string()
    def children(self): return self.value.children()

def _lookup_fn_loc(f: types.CFunction) -> typing.Optional[str]:
    ret = gdb.find_pc_line(int(f.v))
    tab, line = ret.symtab, ret.line
    if tab:
        return f'at {tab.filename}:{line}'
    return None

def _getfuncname(
    lua: 'lua.Lua',
    L: types.LuaState,
    i: types.CallInfo,
    tt: types.RawTypeTag,
    v: types.TValue,
) -> typing.Optional[str]:
    if not types.is_lua_closure(tt):
        return None
    ret = types.LClosure(lua, types.tvalue(v)).location(lua)
    if ret is not None:
        return ret
    # TODO funcnamefromcode
    return None

def _iter_array(h: types.Hash, cap: int) \
    -> typing.Iterator[tuple[int, types.TValue]] \
:
    a = h.to_array()
    for i in range(1, cap + 1):
        v = types.TValue(a)
        if types.is_nil(types.ttype(v)):
            break
        yield i, v
        a += 1

def _iter_hash(h: types.Hash, cap: int) -> typing.Iterator[types.HashNode]:
    n = h.to_hash()
    for _ in range(0, cap):
        yield types.HashNode(n)
        n += 1

def iter_call_stack(L: types.LuaState) -> typing.Iterator[types.CallInfo]:
    p, b = L.v['ci'], L.v['base_ci'].address
    while p != b:
        yield types.CallInfo(p.dereference())
        p = p['previous']

def _dump_unknown(_, v: types.Value, _tt: types.RawTypeTag):
    return f'{v.v.type} {repr(v.v)}'

def _dump_nil(*_):
    return 'nil'

def _dump_boolean(lua, v: types.Value, tt: types.RawTypeTag):
    return int(lua.toboolean(v, tt))

def _dump_lightuserdata(_, v: types.Value, _tt: types.RawTypeTag):
    return str(v.v['p'])

def _dump_number(lua, v: types.Value, tt: types.RawTypeTag):
    if lua.isinteger(tt):
        return v.v['i']
    return v.v['n']

def _dump_string(lua, v: types.Value, _tt: types.RawTypeTag):
    return lua.string_contents(lua.gc(v).to_string())

def _dump_table(lua, v: types.Value, _tt: types.RawTypeTag):
    h = lua.gc(v).to_hash()
    cap, hcap = types.array_cap(lua, h), types.hash_cap(h)
    len = sum(1 for _ in _iter_array(h, cap))
    hlen = sum(
        1 for x in _iter_hash(h, hcap)
        if not types.is_nil(types.ttype(x.value())))
    return (
        f'(array_capacity: {cap}, length: {len},'
        f' hash_capacity: {hcap}, hash_length: {hlen})')

def _dump_function(lua, v: types.Value, tt: types.RawTypeTag):
    if types.is_c_closure(tt):
        cl = lua.gc(v).to_cclosure()
        f, nuv = cl['f'], int(cl['nupvalues'])
        if loc := _lookup_fn_loc(types.CFunction(f)):
            return f'cclosure {f} {loc} (nupvalues: {nuv})'
        return f'cclosure {f} (nupvalues: {nuv})'
    p = v.v['p']
    if types.is_lua_closure(tt):
        return f'lclosure {p}'
    if types.is_light_cfunction(tt):
        if loc := _lookup_fn_loc(types.CFunction(p)):
            return f'cfunction {p} {loc}'
        return f'cfunction {p}'
    return f'unknown function {p}'

def _dump_userdata(lua, v: types.Value, _tt: types.RawTypeTag):
    u = lua.gc(v).to_userdata()
    uv, nuv = lua.uv(u)
    ret = [f'{uv} (']
    if nuv:
        ret.append(f'nuvalue: {nuv}, ')
    ret.append(f'size: {u["len"]})')
    return ''.join(ret)

def _dump_thread(lua, v: types.Value, _tt: types.RawTypeTag):
    return str(lua.gc(v).to_thread().address)

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

def dump(lua, v: types.Value, tt: types.RawTypeTag):
    i = min(types.TypeTag(tt).v, len(_DUMP) - 1)
    return _DUMP[i](lua, v, tt)
