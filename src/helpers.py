import math


def deg_to_dms(deg, type='lat'):
    """Converts a latitude or longitude coordinate from Decimal Degrees (DD) to Degrees Minutes Seconds (DMS)."""
    decimals, number = math.modf(deg)
    d = int(number)
    m = int(decimals * 60)
    s = (deg - d - m / 60) * 3600.00
    compass = {
        'lat': ('N', 'S'),
        'lon': ('W', 'E')
    }
    compass_str = compass[type][0 if d >= 0 else 1]
    return '{}º{}\'{:.2f}"{}'.format(abs(d), abs(m), abs(s), compass_str)


def nested_key_exists(dictionary, nested_keys):
    """Checks if a nested key exists in a dictionary."""
    nested_dict = dictionary

    for key in nested_keys:
        try:
            nested_dict = nested_dict[key]
        except KeyError:
            return False
    return True


def replace_all_whitespaces(string, replace_char=" "):
    """Replaces all whitespace characters such as tabs, newlines and spaces with a given character."""
    return replace_char.join(string.split())
