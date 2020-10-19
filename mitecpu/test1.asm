res result

loop:   ldi 42
        st  result
        ldi -1
        bl  loop
