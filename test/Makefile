CFLAGS = -g
LDLIBS = -llua -lm
all: backtrace/backtrace stack/stack
backtrace/backtrace: backtrace/backtrace.c
stack/stack: stack/stack.c

.PHONY: clean
clean:
	rm -f backtrace/backtrace stack/stack
