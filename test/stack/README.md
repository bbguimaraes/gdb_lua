lua stack
=========

```
$ make -C .. && gdb --batch --command stack.gdb stack
make: Entering directory 'gdb_lua/test'
cc -g    stack/stack.c  '-llua -lm' -o stack/stack
make: Leaving directory 'gdb_lua/test'
Breakpoint 1 at 0x150bc: file lstate.c, line 443.

Breakpoint 1, lua_close (L=0x5555555592a8) at lstate.c:443
443	  L = G(L)->mainthread;  /* only the main thread can be closed */

Lua stack:

1: 0x555555559910 nil nil
2: 0x555555559920 boolean 0
3: 0x555555559930 boolean 1
4: 0x555555559940 lightuserdata <c_obj>
5: 0x555555559950 number 42
6: 0x555555559960 number 3.1415901184082031
7: 0x555555559970 string "abc"
8: 0x555555559980 table (array_capacity: 16, length: 16, hash_capacity: 8, hash_length: 7)
9: 0x555555559990 function cfunction 0x555555555229 <c_function>
10: 0x5555555599a0 function cclosure 0x555555555229 <c_function> (nupvalues: 1)
11: 0x5555555599b0 userdata 0x55555555ade8 (nuvalue: 43, size: 42)
12: 0x5555555599c0 thread 0x5555555592a8

Individual indices:

nil nil
boolean 0
boolean 1
lightuserdata <c_obj>
number 42
number 3.1415901184082031
string "abc"
table (array_capacity: 16, length: 16, hash_capacity: 8, hash_length: 7)
function cfunction 0x555555555229 <c_function>
function cclosure 0x555555555229 <c_function> (nupvalues: 1)
userdata 0x55555555ade8 (nuvalue: 43, size: 42)
thread 0x5555555592a8
[Inferior 1 (process 226832) exited normally]
```
