from django import template

register = template.Library()


@register.filter
def subtract(value, arg):
    """Subtracts arg from value."""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter(name="getattr")
def attr(obj, field_name):
    """Read dynamic attribute value in templates."""
    return getattr(obj, field_name, None)
