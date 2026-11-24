# strkit - string/record toolkit used by the config loader.
CC      ?= clang
CFLAGS  ?= -std=c11 -Wall -Wextra -Wpedantic -g -O1
SAN     := -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer
SRCS    := $(filter-out tests/%,$(wildcard *.c))
OBJS    := $(SRCS:.c=.o)

all: libstrkit.a

libstrkit.a: $(OBJS)
	ar rcs $@ $^

%.o: %.c $(wildcard *.h)
	$(CC) $(CFLAGS) -c $< -o $@

tests/visible: tests/visible.c $(SRCS) $(wildcard *.h)
	$(CC) $(CFLAGS) $(SAN) -I. tests/visible.c $(SRCS) -o $@

test: tests/visible
	./tests/visible

clean:
	rm -f $(OBJS) libstrkit.a tests/visible
	rm -rf tests/visible.dSYM

.PHONY: all test clean
