#include <lauxlib.h>

static int c_function(lua_State *L) { (void)L; }

int main(void) {
    lua_State *const L = luaL_newstate();
    lua_pushnil(L);
    lua_pushboolean(L, 0);
    lua_pushlightuserdata(L, NULL);
    lua_pushnumber(L, 0);
    lua_pushliteral(L, "");
    lua_newtable(L);
    lua_pushcfunction(L, c_function);
#if LUA_VERSION_NUM < 504
    lua_newuserdata(L, 0);
#else
    lua_newuserdatauv(L, 0, 0);
#endif
    lua_pushthread(L);
    lua_close(L);
}
