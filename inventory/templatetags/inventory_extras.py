from django import template

"""
This module registers custom template filters for the Inventory templates.
"""

register = template.Library()


@register.filter
def subtract(value, arg):
    """
    Template filter that subtracts the second argument from the first value.
    Returns 0 on invalid conversion values.
    """
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter(name="getattr")
def attr(obj, field_name):
    """
    Template filter enabling dynamic attribute retrieval on object instances in HTML templates.
    """
    return getattr(obj, field_name, None)
