import gc

def print_mem_usage():
    gc.collect()
    f=gc.mem_free()
    a=gc.mem_alloc()
    print('mem_usage {}+{}={}'.format(f, a, f+a))
