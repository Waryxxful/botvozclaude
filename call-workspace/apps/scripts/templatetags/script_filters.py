from django import template

register = template.Library()


@register.filter
def get_dict(dictionary, key):
    """Get a value from a dictionary using a key."""
    if isinstance(dictionary, dict):
        return dictionary.get(key, "")
    return ""
