#!/bin/bash
set -euo pipefail

TESTS='backtrace stack type'

main() {
    local dir
    for dir; do
        echo "$dir"
        build "$dir"
        exec_tests "$dir"
    done
}

build() {
    local dir=$1
    make --no-print-directory -C test clean
    make --no-print-directory -C test \
        CPPFLAGS="-I $dir/src" LDFLAGS="-L $dir/src"
}

exec_tests() {
    local dir=$1 x
    local name=${1##*/}
    local ld="$dir/src"
    for x in $TESTS; do
        local cmd=(gdb --batch --command "test/$x/$x.gdb" "test/$x/$x")
        echo LD_LIBRARY_PATH="$ld" "${cmd[@]}"
        LD_LIBRARY_PATH="$ld" "${cmd[@]}" &> "test/$x/output_$name.txt"
    done
}

main "$@"
