# Notification Templates

This directory contains notification templates for all channels.

## Directory Structure

```
notifications/
├── email/          # HTML email templates (Jinja2)
├── sms/            # Plain text SMS templates (Jinja2)
└── push/           # JSON push notification templates (Jinja2)
```

## Template Naming Convention

Format: `{notification_type}.{extension}`

Examples:
- `achievement.html` - Achievement notification email
- `meal_reminder.txt` - Meal reminder SMS
- `daily_summary.json` - Daily summary push notification

## Available Variables

Templates have access to these variables:

### Common Variables (all templates)
- `user_name` - User's display name
- `user_email` - User's email address
- `notification_type` - Type of notification
- `created_at` - When notification was created

### Notification-Specific Variables

#### Achievement
- `achievement_type` - Type of achievement (e.g., "streak_7day")
- `message` - Achievement message

#### Meal Reminder
- `meal_type` - Type of meal (breakfast, lunch, dinner)
- `recipe_name` - Name of the recipe
- `time_until` - Minutes until meal time

#### Daily Summary
- `meals_consumed` - Number of meals logged
- `compliance_rate` - Percentage of meal plan followed
- `calories_consumed` - Total calories
- `protein_g` - Total protein in grams

#### Weekly Report
- `total_meals_consumed` - Total meals this week
- `average_compliance` - Average compliance rate
- `top_nutrients` - List of nutrients met

#### Inventory Alert
- `alert_type` - "low_stock" or "expiring"
- `items` - List of item names
- `item_count` - Number of items

## Jinja2 Syntax

Templates use Jinja2 syntax:

### Variables
```jinja2
Hello {{ user_name }}!
```

### Conditionals
```jinja2
{% if achievement_type == "streak_7day" %}
    🔥 7-day streak!
{% endif %}
```

### Loops
```jinja2
{% for item in items %}
    - {{ item }}
{% endfor %}
```

### Filters
```jinja2
{{ created_at | date("%B %d, %Y") }}
```

## Version Control

Templates are versioned via Git:
- All changes tracked in Git history
- Use meaningful commit messages
- Easy rollback with `git revert`

## Testing Templates

To test a template:

```python
from app.infrastructure.notifications.templates.template_loader import TemplateLoader

loader = TemplateLoader()
template = loader.load_template("email", "achievement")
rendered = template.render({
    "user_name": "John",
    "achievement_type": "streak_7day",
    "message": "7-day meal logging streak!"
})
print(rendered)
```
