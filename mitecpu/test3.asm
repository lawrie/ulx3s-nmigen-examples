res result

loop:   ldi -1
        add result
        st  result
        ldi -1
        bl  loop
