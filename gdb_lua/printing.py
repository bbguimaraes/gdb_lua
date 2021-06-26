#!/usr/bin/env python3
import gdb

from . import lua
from . import types

class TValuePrinter(object):
    'Printer for tagged values.'
    @classmethod
    def create(cls, v):
        if str(v.type.unqualified()) in ('TValue', 'struct TValue'):
            return cls(v)

    def __init__(self, v):
        self.v = v

    def display_hint(self):
        tt = types.ttype(self.v)
        if tt == types.LUA_TSTRING:
            return 'string'

    def to_string(self):
        return dump(lua.lua(), self.v['value_'], self.v['tt_'])

def _lookup_fn_loc(f):
    ret = gdb.find_pc_line(int(f))
    tab, line = ret.symtab, ret.line
    if tab:
        return f'at {tab.filename}:{line}'
    return None

def _iter_array(h, cap):
    a = h['array']
    for i in range(1, cap + 1):
        if types.ttype(a.dereference()) == types.LUA_TNIL:
            break
        yield i, a
        a += 1

def _iter_hash(h, cap):
    n = h['node']
    for _ in range(0, cap):
        yield n
        n += 1

def _dump_unknown(_, v, _tt):
    return f'{v.type} {repr(v)}'

def _dump_nil(*_):
    return 'nil'

def _dump_boolean(lua, v, tt):
    return int(lua.toboolean(v, tt))

def _dump_lightuserdata(_, v, _tt):
    return str(v['p'])

def _dump_number(lua, v, tt):
    if lua.isinteger(tt):
        return v['i']
    return v['n']

def _dump_string(lua, v, _tt):
    return lua.string_contents(lua.gc(v)['ts'])

def _dump_table(lua, v, _tt):
    h = lua.gc(v)['h']
    cap, hcap = types.array_cap(lua, h), types.hash_cap(h)
    len = sum(1 for _ in _iter_array(h, cap))
    hlen = sum(
        1 for x in _iter_hash(h, hcap)
        if types.ttype(x['i_val']) != types.LUA_TNIL)
    return (
        f'(array_capacity: {cap}, length: {len},'
        f' hash_capacity: {hcap}, hash_length: {hlen})')

def _dump_function(lua, v, tt):
    if types.is_c_closure(tt):
        cl = lua.gc(v)['cl']['c']
        f, nuv = cl['f'], int(cl['nupvalues'])
        if loc := _lookup_fn_loc(f):
            return f'cclosure {f} {loc} (nupvalues: {nuv})'
        return f'cclosure {f} (nupvalues: {nuv})'
    p = v['p']
    if types.is_lua_closure(tt):
        return f'lclosure {p}'
    if types.is_light_cfunction(tt):
        if loc := _lookup_fn_loc(p):
            return f'cfunction {p} {loc}'
        return f'cfunction {p}'
    return f'unknown function {p}'

def _dump_userdata(lua, v, _tt):
    u = lua.gc(v)['u']
    uv, nuv = lua.uv(u)
    ret = [f'{uv} (']
    if nuv:
        ret.append(f'nuvalue: {nuv}, ')
    ret.append(f'size: {u["len"]})')
    return ''.join(ret)

def _dump_thread(lua, v, _tt):
    return str(lua.gc(v)['th'].address)

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

def dump(lua, v, tt):
    i = min(tt & types.TTYPE_MASK, len(_DUMP) - 1)
    return _DUMP[i](lua, v, tt)
