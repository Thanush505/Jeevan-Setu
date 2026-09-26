"""
utils/helpers.py — General utility helper functions.
"""

from datetime import datetime, timedelta
import json


def format_datetime(dt, fmt='%Y-%m-%d %H:%M'):
    """Format a datetime object to string."""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except ValueError:
            return dt
    return dt.strftime(fmt) if dt else 'N/A'


def time_ago(dt):
    """Return a human-readable 'time ago' string."""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except ValueError:
            return dt

    now = datetime.now()
    diff = now - dt

    if diff < timedelta(minutes=1):
        return 'Just now'
    elif diff < timedelta(hours=1):
        mins = int(diff.total_seconds() / 60)
        return f'{mins} min{"s" if mins > 1 else ""} ago'
    elif diff < timedelta(days=1):
        hours = int(diff.total_seconds() / 3600)
        return f'{hours} hour{"s" if hours > 1 else ""} ago'
    elif diff < timedelta(days=30):
        days = diff.days
        return f'{days} day{"s" if days > 1 else ""} ago'
    else:
        return format_datetime(dt, '%b %d, %Y')


def safe_json_loads(text, default=None):
    """Safely parse a JSON string."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def paginate(items, page=1, per_page=20):
    """Simple list pagination."""
    start = (page - 1) * per_page
    end = start + per_page
    return {
        'items': items[start:end],
        'total': len(items),
        'page': page,
        'per_page': per_page,
        'pages': (len(items) + per_page - 1) // per_page
    }


def generate_bed_id(ward_type, number):
    """Generate a bed ID string."""
    prefix = {'ICU': 'I', 'HDU': 'H', 'General': 'G'}
    return f"{prefix.get(ward_type, 'X')}-{number:03d}"
