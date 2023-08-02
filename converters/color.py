def dec2rgba(value: int, a: float = 1):
    b = value & 255
    g = (value >> 8) & 255
    r = (value >> 16) & 255
    return f'rgba({r}, {g}, {b}, {a})'


def dec2hex(value: int):
    return f'#{hex(value)[2:]}'
