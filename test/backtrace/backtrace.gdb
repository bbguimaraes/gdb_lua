source gdb_lua.py
break c_closure
command 1
echo \nLua backtrace:\n\n
lua bt
echo \n
continue
end
run
