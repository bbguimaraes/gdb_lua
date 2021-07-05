#include <stdio.h>

#include <lauxlib.h>

static int c_obj;
static int c_function(lua_State *L) { (void)L; }

int main() {
    lua_State *L = luaL_newstate();
    luaL_dostring(L, "function lua_function() end");
    lua_pushnil(L);
    lua_pushboolean(L, 0);
    lua_pushboolean(L, 1);
    lua_pushlightuserdata(L, &c_obj);
    lua_pushinteger(L, 42);
    lua_pushnumber(L, 3.14159f);
    lua_pushstring(L, "abc");
    lua_createtable(L, 8, 8);
    for(int i = 1; i <= 8; ++i) {
        lua_pushinteger(L, 42 + i);
        lua_rawseti(L, -2, i);
    }
    for(int i = 0; i < 6; ++i) {
        const char c = 'A' + i;
        lua_pushlstring(L, &c, 1);
        lua_pushinteger(L, 42 + 16 + i);
        lua_rawset(L, -3);
    }
    lua_pushliteral(L, "G");
    lua_createtable(L, 0, 1);
    lua_pushliteral(L, "nested");
    lua_pushliteral(L, "table");
    lua_rawset(L, -3);
    lua_rawset(L, -3);
    lua_pushcfunction(L, c_function);
    lua_pushinteger(L, 42);
    lua_pushcclosure(L, c_function, 1);
    lua_getglobal(L, "lua_function");
#if LUA_VERSION_NUM == 503
    lua_newuserdata(L, 42);
#else
    lua_newuserdatauv(L, 42, 43);
#endif
    lua_pushthread(L);
    lua_close(L);
}
