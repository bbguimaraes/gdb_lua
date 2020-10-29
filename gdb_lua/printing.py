#!/usr/bin/env python3
import pipes

import gdb

from . import types

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
    gdb.write(f'{v.type} {repr(v)}')

def _dump_nil(*_):
    gdb.write('nil')

def _dump_boolean(_, _v, tt):
    gdb.write(f'{int(types.toboolean(tt))}')

def _dump_lightuserdata(_, v, _tt):
    gdb.write(str(v['p']))

def _dump_number(_, v, tt):
    if types.isinteger(tt):
        return gdb.write(str(v['i']))
    gdb.write(str(v['n']))

def _dump_string(lua, v, _tt):
    s = lua.gc(v)['ts']['contents'].cast(lua.char_p)
    gdb.write('"')
    gdb.write(pipes.quote(s.string()))
    gdb.write('"')

def _dump_table(lua, v, _tt):
    h = lua.gc(v)['h']
    cap, hcap = types.array_cap(lua, h), types.hash_cap(h)
    len = sum(1 for _ in _iter_array(h, cap))
    hlen = sum(
        1 for x in _iter_hash(h, hcap)
        if types.ttype(x['i_val']) != types.LUA_TNIL)
    s = (
        f'(array_capacity: {cap}, length: {len},'
        f' hash_capacity: {hcap}, hash_length: {hlen})')
    gdb.write(f'{s}')

def _dump_function(lua, v, tt):
    if types.is_c_closure(tt):
        cl = lua.gc(v)['cl']['c']
        nuv = int(cl['nupvalues'])
        return gdb.write(f'cclosure {cl["f"]} (nupvalues: {nuv})')
    p = v['p']
    if types.is_lua_closure(tt):
        return gdb.write(f'lclosure {p}')
    if types.is_light_cfunction(tt):
        return gdb.write(f'cfunction {p}')
    gdb.write(f'unknown function {p}')

def _dump_userdata(lua, v, _tt):
    u = lua.gc(v)['u']
    uv = u['uv']['uv'].address.cast(lua.void_p)
    gdb.write(f'{uv} (nuvalue: {u["nuvalue"]}, size: {u["len"]})')

def _dump_thread(lua, v, _tt):
    gdb.write(str(lua.gc(v)['th'].address))

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

def dump(lua, tt, v):
    i = min(tt & types.TTYPE_MASK, len(_DUMP) - 1)
    _DUMP[i](lua, v, tt)
