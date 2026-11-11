from django import template

# Template library ko register karein
register = template.Library()

@register.filter
def get_timeline_time(timeline_step):
    """
    Ek timeline step (dictionary) se 'time' key ki value nikalta hai.
    """
    if isinstance(timeline_step, dict) and 'time' in timeline_step:
        return timeline_step['time']
    return ""