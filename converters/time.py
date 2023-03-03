from datetime import datetime


def dt2text(dt: datetime):
    return dt.strftime("%d.%m.%Y %H:%M:%S")


def dt_now_as_text():
    dt2text(datetime.utcnow())
