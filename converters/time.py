from datetime import datetime


def dt2text(dt: datetime):
    return dt.strftime("%d.%m.%Y %H:%M:%S")
