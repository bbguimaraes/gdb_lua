CFLAGS = -g
LDLIBS = -llua -lm
all: backtrace/backtrace stack/stack type/type
backtrace/backtrace: backtrace/backtrace.c
stack/stack: stack/stack.c
type/type: type/type.c

.PHONY: check clean
check:
	@for x in backtrace stack type; do \
		echo "$$x"; \
		(cd .. && gdb --batch --command test/$$x/$$x.gdb test/$$x/$$x;) \
	done
clean:
	rm -f backtrace/backtrace stack/stack type/type
