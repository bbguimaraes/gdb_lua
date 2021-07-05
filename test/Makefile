CFLAGS = -g
LDLIBS = -llua -lm
all: backtrace/backtrace stack/stack
backtrace/backtrace: backtrace/backtrace.c
stack/stack: stack/stack.c

.PHONY: check clean
check:
	@for x in backtrace stack; do \
		echo "$$x"; \
		(cd .. && gdb --batch --command test/$$x/$$x.gdb test/$$x/$$x;) \
	done
clean:
	rm -f backtrace/backtrace stack/stack
