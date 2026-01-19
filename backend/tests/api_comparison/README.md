# API Comparison Tests

This directory contains tests that compare old and new implementations.

## Purpose

Ensure new implementation produces EXACT same results as old implementation.

## Test Strategy

For EACH migrated endpoint:

1. **Setup**: Create identical test data
2. **Execute**: Call both old and new endpoints
3. **Compare**: Verify responses are identical
4. **Verify**: Check database state is identical

## Example Test

```python
def test_log_meal_old_vs_new():
    """Verify new log-meal endpoint matches old exactly."""

    # Setup
    user = create_test_user()
    meal_log = create_test_meal_log(user.id)

    # Execute old
    old_response = client.post("/tracking/log-meal", json={
        "meal_log_id": meal_log.id,
        "portion_multiplier": 1.0
    })

    # Execute new
    new_response = client.post("/tracking/v2/log-meal", json={
        "meal_log_id": meal_log.id,
        "portion_multiplier": 1.0
    })

    # Compare
    assert old_response.status_code == new_response.status_code
    assert old_response.json() == new_response.json()

    # Verify database state
    verify_database_state_identical()
```

## Running Comparison Tests

```bash
# Run all comparison tests
pytest tests/api_comparison/ -v

# Run specific comparison test
pytest tests/api_comparison/test_tracking_comparison.py -v
```
