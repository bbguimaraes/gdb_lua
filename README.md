gdb_lua
=======

A set of custom GDB commands that are useful when working with Lua programs.
Tested with Lua versions `5.4.0` and `5.4.1`.  The internal structures have
changed significantly from previous versions, including `5.3`, this script will
not work with those.

Usage
-----

The `gdb_lua.py` can be sourced to create all commands in the current session
(see the GDB documentation for details on Python extensions, particularly the
[Python](https://sourceware.org/gdb/current/onlinedocs/gdb/Python.html)
section).

```
(gdb) source gdb_lua.py
(gdb) help lua
Commands to inspect Lua states.

List of lua subcommands:

lua stack -- Print the values on the stack associated with a Lua state.
…
```

See the [test](./test) directory for samples of each command.
