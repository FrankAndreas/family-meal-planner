from datetime import date, timedelta


def week_start_of(day: date, week_start: int) -> date:
    """The first day of the week `day` is in; week_start is a Python weekday (0 = Monday)."""
    return day - timedelta(days=(day.weekday() - week_start) % 7)


def week_days(start: date) -> list[date]:
    return [start + timedelta(days=n) for n in range(7)]
