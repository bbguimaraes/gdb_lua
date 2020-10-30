#!/usr/bin/env python3
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

class LuaInitializationFailed(Exception): pass

def ttype(v): return v['tt_'] & TTYPE_MASK
def tvalue(v): return v['value_']
def variant(tt): return (tt >> VARIANT_SHIFT) & VARIANT_MASK

def array_cap(l, h):
    return int(l.alimit(h).cast(l.int_t))
def hash_cap(h):
    return 1 << int(h['lsizenode'])

def is_lua_closure(tt):
    return variant(tt) == VARIANT_LUA_CLOSURE
def is_light_cfunction(tt):
    return variant(tt) == VARIANT_LIGHT_CFUNCTION
def is_c_closure(tt):
    return variant(tt) == VARIANT_C_CLOSURE
