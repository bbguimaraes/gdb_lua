gdb_lua
=======

A set of custom GDB commands that are useful when working with Lua programs.
Tested with Lua versions `5.3.6`, `5.4.0`, and `5.4.1`.

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

Versions
--------

Here is a short description of the relevant differences between versions which
are handled by this extension, for documentation purposes.  See the subclasses
of `Lua` in [`lua.py`][[lua.py] for the implementation.  The Lua version is
identified at runtime using the `lua_ident` symbol (see [`lapi.c`][lapi.c] in
the Lua source code).

The lowest version supported is 5.3.6, which understandably differs
significantly from the 5.4 versions in its internal implementation:

- The stack (`StkId`) is a simple array of `TValue` pointers.  In 5.4, it
  becomes a more complex structure to support to-be-closed variables.
- Boolean values had a dedicated `int` field in `union Value`.  In 5.4, they
  become a variant of the `TBOOLEAN` type.
- Integer and float numbers are variants `0` and `1` respectively of the
  `TNUMBER` type.  In 5.4, these values are reversed.
- String and user data content follows the `struct TString` and `struct Udata`
  objects in memory.  In 5.4, the trailing flexible array C idiom is used.
- Table array sizes are indicated by the `sizearray` member of `struct Table`.
  In 5.4, it becomes a more complex calculation based on the `flags` and
  `alimit` members (this extension just uses the `alimit` directly, meaning it
  may overestimate the size of the array part).
- 5.4 introduces user data up-values.
- Hash table nodes are a simple value/key pair of `struct TValue` objects.  In
  5.4, the key is stored first and its fields are broken up so that other node
  fields can be packed together with it.

The following differences are also handled:

- A tail call is represented in the `callstatus` field of `struct CallInfo`
  using the fifth least-significant bit in 5.4.0, while every other version
  (including 5.3.6) uses the sixth.

[lapi.c]: https://github.com/lua/lua/blob/master/lapi.c
[lua.py]: ./gdb_lua/lua.py
