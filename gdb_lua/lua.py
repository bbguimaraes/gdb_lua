#!/usr/bin/env python3
import re
import typing

import gdb

from . import printing
from . import types

VERSION_RE = re.compile(r'^"\$LuaVersion: Lua (\d+)\.(\d+)\.(\d+)')

G: typing.Optional['Lua'] = None

def idx_or_none(v: typing.Sequence[typing.Any], i: int):
    return v[i] if (0 <= i and i < len(v)) else None

def _version() -> tuple[int, int, int]:
    ss, _ = gdb.lookup_symbol('lua_ident')
    if ss is None:
        raise types.LuaInitializationFailed('failed to lookup `lua_ident`')
    s = str(ss.value())
    m = VERSION_RE.match(s)
    if m is None:
        raise types.LuaInitializationFailed(
            f'`lua_ident` does not match expected format: {s}')
    ret = m.groups()
    if len(ret) != 3:
        raise types.LuaInitializationFailed(
            f'`lua_ident` does not match expected format: {s}')
    return int(ret[0]), int(ret[1]), int(ret[2])

def _stack(lua: 'Lua', L: types.LuaState) -> types.StkId:
    return lua.stkidrel_to_stkid(types.StkIdRel(L.v['stack']))

def _stack_top(lua: 'Lua', L: types.LuaState) -> types.StkId:
    return lua.stkidrel_to_stkid(types.StkIdRel(L.v['top']))

def _iter_stack(lua: 'Lua', L: types.LuaState) -> typing.Iterator[types.StkId]:
    s, t = _stack(lua, L).v + 1, _stack_top(lua, L).v
    while s != t:
        yield types.StkId(s)
        s += 1

def _stack_idx(lua: 'Lua', L: types.LuaState, i: int) \
    -> typing.Optional[types.StkId] \
:
    s, t = _stack(lua, L), _stack_top(lua, L)
    if i < 0:
        return types.StkId(t.v + i)
    if 0 < i and i < t.v - s.v:
        return types.StkId(s.v + i)
    return None

def _iter_call_stack(L: types.LuaState) -> typing.Iterator[types.CallInfo]:
    p, b = L.v['ci'], L.v['base_ci'].address
    while p != b:
        yield types.CallInfo(p.dereference())
        p = p['previous']

def _getfuncname(
    lua: 'Lua',
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

class Lua(object):
    def __init__(self):
        self.lua_state = gdb.lookup_type('lua_State')
        self.tvalue = gdb.lookup_type('TValue')
        gc_union = gdb.lookup_type('union GCUnion')
        self.gc_union_p = gc_union.pointer()
        self.int_t = gdb.lookup_type('int')
        self.void_p = gdb.lookup_type('void').pointer()
        self.char_p = gdb.lookup_type('char').pointer()

    @staticmethod
    def stkidrel_to_stkid(v: types.StkIdRel) -> types.StkId:
        return types.StkId(v.v['p'])
    def stkid_to_value(_self, _v: types.StkId) -> types.TValue:
        raise NotImplementedError()
    def toboolean(_self, _v, _tt) -> bool: raise NotImplementedError()
    def isinteger(_self, _tt: types.RawTypeTag) -> bool:
        raise NotImplementedError()
    def string_contents(_self, _s: types.TString) -> gdb.Value:
        raise NotImplementedError()
    def alimit(self, _h: types.Hash) -> gdb.Value: raise NotImplementedError()
    def uv(_self, _v: gdb.Value) -> tuple[gdb.Value, typing.Optional[int]]:
        raise NotImplementedError()
    @staticmethod
    def hash_kv(n: types.HashNode) -> typing.Optional[
        tuple[types.TValue, types.TValue]
    ]:
        raise NotImplementedError()
    @staticmethod
    def is_tail(s: types.CallStatus) -> bool:
        raise NotImplementedError()

    def type(_self, t: gdb.Value) -> str:
        i = int(t)
        if i == -1:
            return 'none'
        return idx_or_none(types.TYPE_NAMES, i) or 'unknown'

    def gc(self, v: types.Value) -> types.GC:
        return types.GC(v.v['gc'].cast(self.gc_union_p))

    def _dump_stack_idx(self, i: int, v: types.StkId):
        val = self.stkid_to_value(v)
        tt = types.ttype(val)
        gdb.write(f'{types.TYPE_NAMES[tt.v]} {val.v}\n')

    def dump_stack_idx(self, L: types.LuaState, i: int):
        v = _stack_idx(self, L, i)
        if v is None:
            raise Exception(f'invalid stack index: {i}')
        self._dump_stack_idx(i, v)

    def dump_stack(self, L: types.LuaState, i: typing.Optional[int]=None):
        if i is not None:
            return self.dump_stack_idx(L, int(i))
        for i, v in enumerate(_iter_stack(self, L)):
            gdb.write(f'{i + 1}: {v.v} ')
            self._dump_stack_idx(i, v)

    def dump_call_stack(self, L: types.LuaState):
        l = lua()
        for i, info in enumerate(_iter_call_stack(L)):
            if f := self.stkidrel_to_stkid(types.StkIdRel(info.v['func'])):
                v = l.stkid_to_value(f)
                tt = types.RawTypeTag(int(v.v['tt_']))
                gdb.write(f'#{i}  {v.v}')
                lua_name = _getfuncname(self, L, info, tt, v)
                if lua_name is not None:
                    gdb.write(' ')
                    gdb.write(lua_name)
                gdb.write('\n')
            if l.is_tail(info.callstatus()):
                gdb.write('(... tail calls ...)\n')

class LuaWithoutStkIdRel(object):
    @staticmethod
    def stkidrel_to_stkid(v: types.StkIdRel) -> types.StkId:
        return types.StkId(v.v)

class Lua53(LuaWithoutStkIdRel, Lua):
    def __init__(self):
        super(Lua53, self).__init__()
        max_align = gdb.lookup_type('L_Umaxalign')
        tstring = gdb.lookup_type('TString')
        udata = gdb.lookup_type('Udata')
        self.tstring_size = max(tstring.sizeof, max_align.sizeof)
        self.udata_size = max(udata.sizeof, max_align.sizeof)

    def stkid_to_value(self, v: types.StkId) -> types.TValue:
        return types.TValue(v.v.dereference())
    def toboolean(self, v: types.Value, _tt: types.RawTypeTag) -> bool:
        return bool(v.v['b'])
    def isinteger(self, tt: types.RawTypeTag) -> bool:
        return bool(types.variant(tt).v)
    def string_contents(self, s: types.TString) -> gdb.Value:
        return self.data_suffix(s.v.address, self.tstring_size) \
            .cast(self.char_p)
    def alimit(self, h: types.Hash) -> gdb.Value:
        return h.v['sizearray']
    def uv(self, v: gdb.Value) -> tuple[gdb.Value, typing.Optional[int]]:
        return (self.data_suffix(v.address, self.udata_size), None)
    def data_suffix(self, ptr, size):
        return (ptr.cast(self.char_p) + size).cast(self.void_p)
    @staticmethod
    def is_tail(s: types.CallStatus) -> bool:
        return bool(s.v & (1 << 5))

    @staticmethod
    def hash_kv(n: types.HashNode) -> typing.Optional[
        tuple[types.TValue, types.TValue]
    ]:
        v = n.value()
        if not types.is_nil(types.ttype(v)):
            return types.TValue(n.v['i_key']['tvk']), v
        return None

class Lua54(Lua):
    def stkid_to_value(self, v: types.StkId) -> types.TValue:
        return types.TValue(v.v['val'])
    def toboolean(self, _v: types.Value, tt: types.RawTypeTag) -> bool:
        return bool(types.variant(tt).v)
    def isinteger(self, tt: types.RawTypeTag) -> bool:
        return not bool(types.variant(tt).v)
    def string_contents(self, s: types.TString) -> gdb.Value:
        return s.v['contents'].cast(self.char_p)
    def alimit(self, h: types.Hash) -> gdb.Value:
        # TODO isrealasize
        return h.v['alimit']
    @staticmethod
    def is_tail(s: types.CallStatus) -> bool:
        return bool(s.v & (1 << 5))

    def uv(self, v: gdb.Value) -> tuple[gdb.Value, typing.Optional[int]]:
        return (
            v['uv']['uv'].address.cast(self.void_p),
            int(v['nuvalue']),
        )

    @staticmethod
    def hash_kv(n: types.HashNode) -> typing.Optional[
        tuple[types.TValue, types.TValue]
    ]:
        v = n.value()
        if not types.is_nil(types.ttype(v)):
            return types.TValue(n.v['u']), v
        return None

class Lua54_le1(LuaWithoutStkIdRel, Lua54):
    @staticmethod
    def is_tail(s: types.CallStatus) -> bool:
        return bool(s.v & (1 << 4))

class Lua54_lt5(LuaWithoutStkIdRel, Lua54): pass

def lua() -> Lua:
    global G
    if G is None:
        v = _version()
        if v[0] == 5:
            if v[1] == 3:
                G = Lua53()
            elif v[1] == 4:
                if v[2] <= 1:
                    G = Lua54_le1()
                elif v[2] <= 4:
                    G = Lua54_lt5()
                else:
                    G = Lua54()
        if G is None:
            raise types.LuaInitializationFailed(
                'unsupported Lua version: ' + '.'.join(map(str, v)))
    return G
