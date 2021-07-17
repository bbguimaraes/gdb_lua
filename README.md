gdb_lua
=======

A set of custom GDB commands that are useful when working with Lua programs.
Tested with Lua versions `5.3.6` and `5.4.0` to `5.4.3`.

Usage
-----

`gdb_lua.py` can be sourced to create all commands in the current session and
register all pretty printers (see the GDB documentation for details on Python
extensions, particularly the Python
[section](https://sourceware.org/gdb/current/onlinedocs/gdb/Python.html).

```
(gdb) source gdb_lua.py
(gdb) help lua
Commands to inspect Lua states.

List of lua subcommands:

lua bt -- Prints the current call stack associated with a Lua state.
lua stack -- Print the values on the stack associated with a Lua state.
…
```

Pretty printers are automatically registered.  Values can still be visualized
unchanged using the `-raw-values` argument for `print` or by setting the `print
raw-values` option.

See the [test](./test) directory for samples of each command.
