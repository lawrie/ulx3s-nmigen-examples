def readhex(filename):
    f = open(filename,"r")
    l = []
    while True:
        s = f.readline()
        if s:
            if s[0] != "/":
                ss = s.split()
                for t in ss:
                    l.append(int(t,16))
        else:
            break
    f.close()
    return l

