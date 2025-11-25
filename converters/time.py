from datetime import datetime, timedelta


def dt2text(dt: datetime):
    return dt.strftime("%d.%m.%Y %H:%M:%S")


def dt_now_as_text():
    return dt2text(datetime.now())


def td2text(td: timedelta):
    values = []

    if td.days > 1:
        values.append(f"{td.days} days")
    elif td.days == 1:
        values.append("1 day")

    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 1:
        values.append(f"{hours} hours")
    elif hours == 1:
        values.append("1 hour")

    if minutes > 1:
        values.append(f"{minutes} minutes")
    elif minutes == 1:
        values.append("1 minute")

    if seconds > 1:
        values.append(f"{seconds} seconds")
    elif seconds == 1:
        values.append("1 second")

    return values[0] if len(values) == 1 else " and ".join([", ".join(values[:-1]), values[-1]])


TIME_UNITS = ["days", "hours", "minutes", "seconds"]


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

    return time
