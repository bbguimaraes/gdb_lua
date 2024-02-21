#!/usr/bin/env bash
set -euo pipefail

MAKE="make --jobs"
VERSIONS=(5.3.6 5.4.0 5.4.1 5.4.2 5.4.3 5.4.4)
TESTS=(backtrace stack type)

main() {
    [[ "$#" -eq 1 ]] || usage
    local dir=$1 pwd=$PWD v
    for v in "${VERSIONS[@]}"; do
        echo "$v"
        checkout "$dir" "$v"
        build_so "$pwd" "$dir" "$v"
        build "$dir/$v"
        exec_tests "$dir/$v"
    done
}

usage() {
    cat >&2 <<EOF
Usage: $0 DIR
EOF
    return 1
}

checkout() {
    local dir=$1 v=$2
    [[ -d "$dir/$v" ]] && return
    git -C "$dir" worktree add "$v" "v$v"
}

build_so() {
    local src_dir=$1 dir=$2 v=$3
    [[ -e "$dir/$v/liblua.so" ]] && return
    pushd "$dir/$v" > /dev/null
    patch --forward --strip 0 < "$src_dir/scripts/patches/$v.patch"
    $MAKE --no-print-directory liblua.so
    popd
}

build() {
    local dir=$1
    $MAKE --no-print-directory -C "$dir"
    $MAKE --no-print-directory -C test clean
    $MAKE --no-print-directory -C test CPPFLAGS="-I $dir" LDFLAGS="-L $dir"
}

exec_tests() {
    local dir=$1 x
    local name=${1##*/}
    local ld=$dir
    for x in "${TESTS[@]}"; do
        local cmd=(gdb --batch --command "test/$x/$x.gdb" "test/$x/$x")
        echo LD_LIBRARY_PATH="$ld" "${cmd[@]}"
        LD_LIBRARY_PATH="$ld" "${cmd[@]}" # &> "test/$x/output_$name.txt"
    done
}

main "$@"
