#include <stdio.h>

#include <lauxlib.h>
#include <lualib.h>

#if LUA_VERSION_NUM == 503
#define CLOSE_STR \
    "function lua_file() getmetatable(new_close_obj()).__close() end"
#else
#define CLOSE_STR "function lua_file() local o <close> = new_close_obj() end"
#endif

static int msgh(lua_State *L) {
    const char *const msg = lua_tostring(L, -1);
    luaL_traceback(L, L, NULL, 0);
    fprintf(stderr, "msgh: %s\n%s\n", msg, lua_tostring(L, -1));
    lua_pop(L, 1);
    return 0;
}

static int c_fn(lua_State *L) {
    lua_getglobal(L, "lua_c_closure");
    lua_call(L, 0, 0);
    return 0;
}

static int c_intermediary(lua_State *L) {
    return c_fn(L);
}

static int c_closure(lua_State *L) {
    luaL_error(L, "Lua error backtrace for comparison:");
    return 0;
}

int main(int argc, char **argv) {
    lua_State *const L = luaL_newstate();
    luaL_openlibs(L);
    luaL_dofile(L, "test/backtrace/backtrace.lua");
    lua_pushinteger(L, 42);
    lua_pushcclosure(L, c_closure, 1);
    lua_setglobal(L, "lua_c_closure");
    lua_pushcfunction(L, c_intermediary);
    lua_setglobal(L, "lua_c_intermediary");
    lua_pushcfunction(L, c_fn);
    lua_setglobal(L, "lua_c_fn");
    luaL_dostring(L,
        "-- empty\n-- lines\n--\n"
        "function lua_string()\n    print(lua_file())\nend\n"
        CLOSE_STR);
    lua_pushcfunction(L, msgh);
    lua_getglobal(L, "lua_string");
    lua_pcall(L, 0, LUA_MULTRET, 1);
    lua_close(L);
}
