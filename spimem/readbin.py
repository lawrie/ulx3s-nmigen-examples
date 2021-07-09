def readbin(filename):
    f = open(filename,"r")
    l = []
    while True:
        s = f.readline()
        if s:
            if s[0] != "/":
                l.append(int(s,2))
        else:
            break
    f.close()
    return l

