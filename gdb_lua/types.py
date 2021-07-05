#!/usr/bin/env python3
import typing

import gdb

if typing.TYPE_CHECKING:
    from . import lua

TTYPE_MASK = 0b1111
VARIANT_SHIFT = 4
VARIANT_MASK = 0b11

LUA_TNIL = 0
LUA_TBOOLEAN = 1
LUA_TLIGHTUSERDATA = 2
LUA_TNUMBER = 3
LUA_TSTRING = 4
LUA_TTABLE = 5
LUA_TFUNCTION = 6
LUA_TUSERDATA = 7
LUA_TTHREAD = 8

VARIANT_LUA_CLOSURE = 0
VARIANT_LIGHT_CFUNCTION = 1
VARIANT_C_CLOSURE = 2

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

class GDBValue(object):
    __slots__ = ('v',)
    def __init__(self, v: gdb.Value):
        self.v = v

class LuaInitializationFailed(Exception): pass
class CFunction(GDBValue): pass
class LuaState(GDBValue): pass
class StkId(GDBValue): pass
class TValue(GDBValue): pass
class Value(GDBValue): pass
class TString(GDBValue): pass
class CallStatus(GDBValue): pass

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
        self.v = (tt.v >> VARIANT_SHIFT) & VARIANT_MASK

class GC(GDBValue):
    def to_string(self) -> TString: return TString(self.v['ts'])
    def to_hash(self) -> 'Hash': return Hash(self.v['h'])
    def to_lclosure(self) -> gdb.Value: return self.v['cl']['l']
    def to_cclosure(self) -> gdb.Value: return self.v['cl']['c']
    def to_userdata(self) -> gdb.Value: return self.v['u']
    def to_thread(self) -> gdb.Value: return self.v['th']

class Hash(GDBValue):
    def to_array(self) -> gdb.Value: return self.v['array']
    def to_hash(self) -> gdb.Value: return self.v['node']

class HashNode(GDBValue):
    __slots__ = ('v',)
    def __init__(self, v): self.v = v
    def key_tt(self) -> RawTypeTag: return RawTypeTag(int(self.v['key_tt']))
    def key_value(self) -> Value: return Value(self.v['key_val'])
    def value(self) -> TValue: return TValue(self.v['i_val'])

class LClosure(GDBValue):
    def __init__(self, lua: 'lua.Lua', v: Value):
       self.v = lua.gc(v).to_lclosure()

    def location(self, lua: 'lua.Lua') -> typing.Optional[str]:
        proto = self.v['p']
        src = lua.string_contents(
            TString(proto['source'].dereference())).string()
        if src and src[0] == '@':
            ret = src[1:]
        else:
            ret = '[string "{}"]'.format(src.replace('\n', '\\n'))
        line = proto['linedefined']
        if line == 0:
            ret += ' in main chunk'
        else:
            # TODO getcurrentline
            ret += ':' + str(line)
        return ret

class CallInfo(GDBValue):
    def callstatus(self) -> CallStatus:
        return CallStatus(self.v['callstatus'])

def tt(v: TValue) -> RawTypeTag: return RawTypeTag(int(v.v['tt_']))
def ttype(v: TValue) -> TypeTag: return TypeTag(tt(v))
def tvalue(v: TValue) -> Value: return Value(v.v['value_'])
def variant(tt: RawTypeTag) -> TypeVariant: return TypeVariant(tt)

def array_cap(l: 'lua.Lua', h: Hash) -> int:
    return int(l.alimit(h).cast(l.int_t))
def hash_cap(h: Hash) -> int:
    return 1 << int(h.v['lsizenode'])

def is_nil(tt: TypeTag): return tt.v == LUA_TNIL
def is_string(tt: TypeTag): return tt.v == LUA_TSTRING
def is_table(tt: TypeTag): return tt.v == LUA_TTABLE

def is_lua_closure(tt: RawTypeTag) -> bool:
    return variant(tt).v == VARIANT_LUA_CLOSURE
def is_light_cfunction(tt: RawTypeTag) -> bool:
    return variant(tt).v == VARIANT_LIGHT_CFUNCTION
def is_c_closure(tt: RawTypeTag) -> bool:
    return variant(tt).v == VARIANT_C_CLOSURE
