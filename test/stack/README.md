lua stack
=========

```
$ make -C .. && gdb --batch --command stack.gdb stack
make: Entering directory 'gdb_lua/test'
cc -g    stack/stack.c  '-llua -lm' -o stack/stack
make: Leaving directory 'gdb_lua/test'
Breakpoint 1 at 0x150bc: file lstate.c, line 443.

Breakpoint 1, lua_close (L=0x55555558b2a8) at lstate.c:443
443	  L = G(L)->mainthread;  /* only the main thread can be closed */
1: 0x55555558b910 nil
2: 0x55555558b920 boolean 0
3: 0x55555558b930 boolean 1
4: 0x55555558b940 lightuserdata 0x55555558a18c <c_obj>
5: 0x55555558b950 number 42
6: 0x55555558b960 number 3.1415901184082031
7: 0x55555558b970 string 0x55555558bbe8 "abc"
8: 0x55555558b980 table (array_capacity: 16, length: 16, hash_capacity: 8, hash_length: 7)
9: 0x55555558b990 function cfunction 0x555555556399 <c_function>
10: 0x55555558b9a0 function cclosure 0x555555556399 <c_function> (nupvalues: 1)
11: 0x55555558b9b0 userdata 0x55555558cde8 (nuvalue: 43, size: 42)
12: 0x55555558b9c0 thread 0x55555558b2a8
[Inferior 1 (process 226832) exited normally]
```
