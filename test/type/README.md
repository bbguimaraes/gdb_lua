lua type
========

```
$ make -C test
make: Entering directory 'test'
cc -g    type/type.c  -llua -lm -o type/type
make: Leaving directory 'test'
Breakpoint 1 at 0x1040

Breakpoint 1, lua_close (L=0x5555555592a8) at lstate.c:413
413	  L = G(L)->mainthread;  /* only the main thread can be closed */

Lua types:
1: nil
2: boolean
3: lightuserdata
4: number
5: string
6: table
7: function
8: userdata
9: thread
10: none
[Inferior 1 (process 23810) exited normally]
```
