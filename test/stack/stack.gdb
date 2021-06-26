python import gdb_lua
break lua_close
run
echo \nLua stack:\n\n
lua stack
echo \nIndividual indices:\n\n
lua stack L 1
lua stack L 2
lua stack L 3
lua stack L 4
lua stack L 5
lua stack L 6
lua stack L 7
lua stack L 8
lua stack L 9
lua stack L 10
lua stack L 11
lua stack L 12
lua stack L 13
continue
