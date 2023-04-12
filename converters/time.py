from datetime import datetime, timezone


def dt2text(dt: datetime):
    return dt.strftime("%d.%m.%Y %H:%M:%S")


def utcnow():
    return datetime.now(timezone.utc)


def dt_now_as_text():
    return dt2text(utcnow())
