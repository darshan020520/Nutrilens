"""
Manual test runner for value objects (no pytest required).

This script validates that our new value objects produce IDENTICAL results
to the existing OnboardingService calculations.
"""
import sys
sys.path.insert(0, '.')

from domain.user.value_objects import BMI, BMR, TDEE, ActivityLevel


def test_bmr_male_30_years():
    """Test BMR calculation for 30-year-old male."""
    bmr = BMR.calculate(weight_kg=70, height_cm=175, age=30, sex="male")
    expected = 1648.75
    assert bmr.value == expected, f"FAIL: Expected {expected}, got {bmr.value}"
    print(f"[PASS] BMR male 30 years: {bmr.value} (expected {expected})")


def test_bmr_female_30_years():
    """Test BMR calculation for 30-year-old female."""
    bmr = BMR.calculate(weight_kg=60, height_cm=165, age=30, sex="female")
    expected = 1320.25
    assert bmr.value == expected, f"FAIL: Expected {expected}, got {bmr.value}"
    print(f"[PASS] BMR female 30 years: {bmr.value} (expected {expected})")


def test_bmr_matches_onboarding_service():
    """
    CRITICAL TEST: Verify BMR matches OnboardingService.calculate_bmr() exactly.

    This uses the EXACT formula from onboarding.py:70-81
    """
    # Test case 1: Male
    weight_kg = 75.0
    height_cm = 180.0
    age = 28
    sex = "male"

    bmr = BMR.calculate(weight_kg, height_cm, age, sex)

    # Expected from OnboardingService: 10 * 75 + 6.25 * 180 - 5 * 28 + 5 = 1740.0
    expected = 1740.0
    assert bmr.value == expected, f"FAIL: Expected {expected}, got {bmr.value}"
    print(f"[PASS] BMR backward compatibility (male): {bmr.value} (expected {expected})")

    # Test case 2: Female
    bmr_female = BMR.calculate(weight_kg=60, height_cm=165, age=25, sex="female")
    expected_female = 1345.25
    assert bmr_female.value == expected_female, f"FAIL: Expected {expected_female}, got {bmr_female.value}"
    print(f"[PASS] BMR backward compatibility (female): {bmr_female.value} (expected {expected_female})")


def test_tdee_sedentary():
    """Test TDEE calculation for sedentary activity."""
    bmr = BMR(value=1648.75)
    tdee = TDEE.calculate(bmr, ActivityLevel.SEDENTARY)
    expected = 1978.5
    assert tdee.value == expected, f"FAIL: Expected {expected}, got {tdee.value}"
    print(f"[PASS] TDEE sedentary: {tdee.value} (expected {expected})")


def test_tdee_moderately_active():
    """Test TDEE calculation for moderately active."""
    bmr = BMR(value=1648.75)
    tdee = TDEE.calculate(bmr, ActivityLevel.MODERATELY_ACTIVE)
    expected = 2555.56
    assert tdee.value == expected, f"FAIL: Expected {expected}, got {tdee.value}"
    print(f"[PASS] TDEE moderately active: {tdee.value} (expected {expected})")


def test_tdee_matches_onboarding_service():
    """
    CRITICAL TEST: Verify TDEE matches OnboardingService.calculate_tdee() exactly.
    """
    bmr = BMR(value=1740.0)
    tdee = TDEE.calculate(bmr, ActivityLevel.SEDENTARY)
    expected = 2088.0
    assert tdee.value == expected, f"FAIL: Expected {expected}, got {tdee.value}"
    print(f"[PASS] TDEE backward compatibility: {tdee.value} (expected {expected})")


def test_bmi_normal_weight():
    """Test BMI calculation for normal weight."""
    bmi = BMI.from_measurements(weight_kg=70, height_cm=175)
    expected = 22.86
    assert bmi.value == expected, f"FAIL: Expected {expected}, got {bmi.value}"
    assert bmi.category() == "normal", f"FAIL: Expected 'normal', got '{bmi.category()}'"
    print(f"[PASS] BMI normal weight: {bmi.value} (expected {expected}), category: {bmi.category()}")


def test_bmi_underweight():
    """Test BMI calculation for underweight."""
    bmi = BMI.from_measurements(weight_kg=50, height_cm=175)
    expected = 16.33
    assert bmi.value == expected, f"FAIL: Expected {expected}, got {bmi.value}"
    assert bmi.category() == "underweight", f"FAIL: Expected 'underweight', got '{bmi.category()}'"
    print(f"[PASS] BMI underweight: {bmi.value} (expected {expected}), category: {bmi.category()}")


def test_bmi_obese():
    """Test BMI calculation for obese."""
    bmi = BMI.from_measurements(weight_kg=95, height_cm=175)
    expected = 31.02
    assert bmi.value == expected, f"FAIL: Expected {expected}, got {bmi.value}"
    assert bmi.category() == "obese", f"FAIL: Expected 'obese', got '{bmi.category()}'"
    print(f"[PASS] BMI obese: {bmi.value} (expected {expected}), category: {bmi.category()}")


def test_immutability():
    """Test that value objects are immutable."""
    bmr = BMR(value=1648.75)
    try:
        bmr.value = 2000.0
        print("[FAIL] FAIL: BMR is not immutable!")
        sys.exit(1)
    except Exception:
        print("[PASS] BMR is immutable (cannot modify)")

    tdee = TDEE(value=2555.56)
    try:
        tdee.value = 3000.0
        print("[FAIL] FAIL: TDEE is not immutable!")
        sys.exit(1)
    except Exception:
        print("[PASS] TDEE is immutable (cannot modify)")


def test_value_equality():
    """Test that value objects are compared by value."""
    bmr1 = BMR(value=1648.75)
    bmr2 = BMR(value=1648.75)
    assert bmr1 == bmr2, "FAIL: Value objects with same value should be equal"
    assert bmr1 is not bmr2, "FAIL: Value objects should be different objects"
    print("[PASS] Value objects compared by value (not identity)")


def test_validation():
    """Test that invalid inputs are rejected."""
    try:
        BMR.calculate(weight_kg=-70, height_cm=175, age=30, sex="male")
        print("[FAIL] FAIL: Negative weight should raise ValueError!")
        sys.exit(1)
    except ValueError as e:
        print(f"[PASS] Validation works: {e}")

    try:
        BMI.from_measurements(weight_kg=70, height_cm=0)
        print("[FAIL] FAIL: Zero height should raise ValueError!")
        sys.exit(1)
    except ValueError as e:
        print(f"[PASS] Validation works: {e}")


def main():
    """Run all tests."""
    print("=" * 80)
    print("WAVE 1 VALUE OBJECTS - VALIDATION TESTS")
    print("=" * 80)
    print()

    tests = [
        ("BMR Male 30 Years", test_bmr_male_30_years),
        ("BMR Female 30 Years", test_bmr_female_30_years),
        ("BMR Backward Compatibility", test_bmr_matches_onboarding_service),
        ("TDEE Sedentary", test_tdee_sedentary),
        ("TDEE Moderately Active", test_tdee_moderately_active),
        ("TDEE Backward Compatibility", test_tdee_matches_onboarding_service),
        ("BMI Normal Weight", test_bmi_normal_weight),
        ("BMI Underweight", test_bmi_underweight),
        ("BMI Obese", test_bmi_obese),
        ("Immutability", test_immutability),
        ("Value Equality", test_value_equality),
        ("Validation", test_validation),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] FAIL: {name} - {e}")
            failed += 1
        except Exception as e:
            print(f"[FAIL] ERROR: {name} - {e}")
            failed += 1

    print()
    print("=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)

    if failed > 0:
        print("\n[X] TESTS FAILED - Value objects do NOT match existing logic!")
        print("Migration CANNOT proceed until all tests pass.")
        sys.exit(1)
    else:
        print("\n[OK] ALL TESTS PASSED - Value objects match existing logic exactly!")
        print("Safe to proceed with migration.")


if __name__ == "__main__":
    main()
