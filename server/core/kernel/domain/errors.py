class KernelError(Exception):
    pass


class DagError(KernelError, ValueError):
    pass
