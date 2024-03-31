#!/usr/bin/env bash
set -euo pipefail

MAKE="make --jobs"
VERSIONS=(5.3.6 5.4.0 5.4.1 5.4.2 5.4.3 5.4.4 5.4.5 5.4.6)
TESTS=(backtrace stack type)

main() {
    [[ "$#" -lt 1 ]] && usage
    local dir=$1; shift
    [[ "$#" -eq 0 ]] && set -- "${VERSIONS[@]}"
    local pwd=$PWD v
    for v; do
        echo "$v"
        checkout "$dir" "$v"
        build_so "$pwd" "$dir" "$v"
        build "$dir/$v"
        exec_tests "$dir" "$v"
    done
}

usage() {
    cat >&2 <<EOF
Usage: $0 DIR [VERSION...]
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
    local dir=$1 v=$2 test output ret
    local name=${1##*/}
    for test in "${TESTS[@]}"; do
        local cmd=(
            gdb
            --batch
            --command "test/$test/$test.gdb"
            "test/$test/$test"
        )
        local cmp=test/$test/output/$v.txt
        echo "$v" "${cmd[@]}"
        if ! \
            output=$( \
                exec_with_version "$dir" "$v" "${cmd[@]}" \
                |& process_output)
        then
            ret=$PIPESTATUS
            echo "$output"
            return "$ret"
        fi
        # XXX
        if [[ "$test" == stack ]]; then
            cmp=$(<$cmp)
            output=$(perl \
                -e '$/ = undef; $_ = <>; s/([^,])(\n})/\1,\2/mg; print' \
                <<< $output)
            colordiff -u <(sort <<< $cmp) <(sort <<< $output)
        else
            colordiff -u "$cmp" - <<< $output
        fi
    done
}

exec_with_version() {
    local dir=$1 v=$2; shift 2
    local ld=$dir/$v
    LD_LIBRARY_PATH=$ld "$@"
}

process_output() {
    sed \
        --expression 's/\b0x[a-f0-9]\{12\}\b/0x0/g' \
        --expression '/^Breakpoint 1 at 0x[0-9]\+/d' \
        --expression '/^\[Thread debugging using libthread_db enabled\]$/d' \
        --expression '/^Using host libthread_db library /d' \
        --expression '/^\[Inferior 1 (process [0-9]\+) exited normally\]$/d'
}

main "$@"
