from datetime import datetime, timedelta, timezone


def dt2text(dt: datetime):
    return dt.strftime("%d.%m.%Y %H:%M:%S")


def utcnow():
    return datetime.now(timezone.utc)


def dt_now_as_text():
    return dt2text(utcnow())


def transform_time(time_amount: int, time_unit: str) -> timedelta | None:
    if time_unit == 'days':
        time = timedelta(days=time_amount)
    elif time_unit == 'hours':
        time = timedelta(hours=time_amount)
    elif time_unit == 'minutes':
        time = timedelta(minutes=time_amount)
    elif time_unit == 'seconds':
        time = timedelta(seconds=time_amount)
    else:
        return None

    return time if time > timedelta() else None
