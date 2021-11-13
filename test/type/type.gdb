python import gdb_lua
break lua_close
command 1
echo \nLua types:\n
python
for i in range(1, 11):
    print(f"{i}: ", end="")
    gdb.execute(f"lua type lua_type(L, {i})")
end
continue
end
run
