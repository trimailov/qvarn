# This shell script snippet gets prepended to each IMPLEMENTS step
# when it is executed. It can contain shared definitions of shell
# functions and similar stuff.


save_value()
{
    printf 's \$%s$ %s g\n' "$1" "$2" >> "$DATADIR/expand-values.sed"
    printf 's \$%s([^0-9]) %s\\1 g\n' "$1" "$2" >> "$DATADIR/expand-values.sed"
}


expand_values()
{
    touch "$DATADIR/expand-values.sed"
    echo "$1" | sed -r -f "$DATADIR/expand-values.sed"
}
