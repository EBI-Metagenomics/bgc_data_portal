from django import template

register = template.Library()


@register.filter
def getattr_tag(obj, attr):
    if isinstance(obj, dict):
        return obj.get(attr, "")
    return getattr(obj, attr, "")


@register.filter
def is_list(value):
    """Return True if the given value is a Python list."""
    return isinstance(value, list)
