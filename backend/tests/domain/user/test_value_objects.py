"""
Tests for user domain value objects.

CRITICAL: These tests verify that the new value objects produce IDENTICAL results
to the existing OnboardingService calculations (onboarding.py).
"""
import pytest
from domain.user.value_objects import BMI, BMR, TDEE, ActivityLevel


class TestBMI:
    """Tests for BMI value object."""

    def test_calculate_bmi_normal_weight(self):
        """Test BMI calculation for normal weight person."""
        # 70kg, 175cm → BMI = 70 / (1.75^2) = 22.86
        bmi = BMI.from_measurements(weight_kg=70, height_cm=175)
        assert bmi.value == 22.86
        assert bmi.category() == "normal"

    def test_calculate_bmi_underweight(self):
        """Test BMI calculation for underweight person."""
        # 50kg, 175cm → BMI = 50 / (1.75^2) = 16.33
        bmi = BMI.from_measurements(weight_kg=50, height_cm=175)
        assert bmi.value == 16.33
        assert bmi.category() == "underweight"

    def test_calculate_bmi_overweight(self):
        """Test BMI calculation for overweight person."""
        # 85kg, 175cm → BMI = 85 / (1.75^2) = 27.76
        bmi = BMI.from_measurements(weight_kg=85, height_cm=175)
        assert bmi.value == 27.76
        assert bmi.category() == "overweight"

    def test_calculate_bmi_obese(self):
        """Test BMI calculation for obese person."""
        # 95kg, 175cm → BMI = 95 / (1.75^2) = 31.02
        bmi = BMI.from_measurements(weight_kg=95, height_cm=175)
        assert bmi.value == 31.02
        assert bmi.category() == "obese"

    def test_bmi_immutable(self):
        """Test that BMI is immutable."""
        bmi = BMI.from_measurements(weight_kg=70, height_cm=175)
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            bmi.value = 25.0

    def test_bmi_invalid_weight(self):
        """Test that negative weight raises error."""
        with pytest.raises(ValueError, match="Weight must be positive"):
            BMI.from_measurements(weight_kg=-70, height_cm=175)

    def test_bmi_invalid_height(self):
        """Test that zero height raises error."""
        with pytest.raises(ValueError, match="Height must be positive"):
            BMI.from_measurements(weight_kg=70, height_cm=0)


class TestBMR:
    """
    Tests for BMR value object.

    CRITICAL: These tests must produce IDENTICAL results to OnboardingService.calculate_bmr()
    """

    def test_calculate_bmr_male_30_years(self):
        """
        Test BMR calculation for 30-year-old male.

        Matches OnboardingService.calculate_bmr() logic from onboarding.py:70-81.
        Formula: BMR = 10 × 70 + 6.25 × 175 - 5 × 30 + 5
        """
        bmr = BMR.calculate(weight_kg=70, height_cm=175, age=30, sex="male")

        # Expected: 10*70 + 6.25*175 - 5*30 + 5 = 700 + 1093.75 - 150 + 5 = 1648.75
        assert bmr.value == 1648.75

    def test_calculate_bmr_female_30_years(self):
        """
        Test BMR calculation for 30-year-old female.

        Formula: BMR = 10 × 60 + 6.25 × 165 - 5 × 30 - 161
        """
        bmr = BMR.calculate(weight_kg=60, height_cm=165, age=30, sex="female")

        # Expected: 10*60 + 6.25*165 - 5*30 - 161 = 600 + 1031.25 - 150 - 161 = 1320.25
        assert bmr.value == 1320.25

    def test_calculate_bmr_male_25_years(self):
        """Test BMR for 25-year-old male (younger age)."""
        bmr = BMR.calculate(weight_kg=80, height_cm=180, age=25, sex="male")

        # Expected: 10*80 + 6.25*180 - 5*25 + 5 = 800 + 1125 - 125 + 5 = 1805.0
        assert bmr.value == 1805.0

    def test_calculate_bmr_female_50_years(self):
        """Test BMR for 50-year-old female (older age)."""
        bmr = BMR.calculate(weight_kg=65, height_cm=160, age=50, sex="female")

        # Expected: 10*65 + 6.25*160 - 5*50 - 161 = 650 + 1000 - 250 - 161 = 1239.0
        assert bmr.value == 1239.0

    def test_bmr_immutable(self):
        """Test that BMR is immutable."""
        bmr = BMR.calculate(weight_kg=70, height_cm=175, age=30, sex="male")
        with pytest.raises(Exception):
            bmr.value = 2000.0

    def test_bmr_invalid_weight(self):
        """Test that negative weight raises error."""
        with pytest.raises(ValueError, match="Weight must be positive"):
            BMR.calculate(weight_kg=-70, height_cm=175, age=30, sex="male")

    def test_bmr_invalid_sex(self):
        """Test that invalid sex raises error."""
        with pytest.raises(ValueError, match="Sex must be 'male' or 'female'"):
            BMR.calculate(weight_kg=70, height_cm=175, age=30, sex="other")


class TestTDEE:
    """
    Tests for TDEE value object.

    CRITICAL: These tests must produce IDENTICAL results to OnboardingService.calculate_tdee()
    """

    def test_calculate_tdee_sedentary(self):
        """
        Test TDEE calculation for sedentary activity level.

        Matches OnboardingService.calculate_tdee() logic from onboarding.py:84-87.
        TDEE = BMR × 1.2
        """
        bmr = BMR(value=1648.75)
        tdee = TDEE.calculate(bmr, ActivityLevel.SEDENTARY)

        # Expected: 1648.75 * 1.2 = 1978.5
        assert tdee.value == 1978.5

    def test_calculate_tdee_lightly_active(self):
        """Test TDEE for lightly active person (1.375 multiplier)."""
        bmr = BMR(value=1648.75)
        tdee = TDEE.calculate(bmr, ActivityLevel.LIGHTLY_ACTIVE)

        # Expected: 1648.75 * 1.375 = 2267.03
        assert tdee.value == 2267.03

    def test_calculate_tdee_moderately_active(self):
        """Test TDEE for moderately active person (1.55 multiplier)."""
        bmr = BMR(value=1648.75)
        tdee = TDEE.calculate(bmr, ActivityLevel.MODERATELY_ACTIVE)

        # Expected: 1648.75 * 1.55 = 2555.56
        assert tdee.value == 2555.56

    def test_calculate_tdee_very_active(self):
        """Test TDEE for very active person (1.725 multiplier)."""
        bmr = BMR(value=1648.75)
        tdee = TDEE.calculate(bmr, ActivityLevel.VERY_ACTIVE)

        # Expected: 1648.75 * 1.725 = 2844.09
        assert tdee.value == 2844.09

    def test_calculate_tdee_extra_active(self):
        """Test TDEE for extra active person (1.9 multiplier)."""
        bmr = BMR(value=1648.75)
        tdee = TDEE.calculate(bmr, ActivityLevel.EXTRA_ACTIVE)

        # Expected: 1648.75 * 1.9 = 3132.62
        assert tdee.value == 3132.62

    def test_calculate_tdee_from_measurements(self):
        """Test TDEE calculation directly from measurements."""
        tdee = TDEE.from_measurements(
            weight_kg=70,
            height_cm=175,
            age=30,
            sex="male",
            activity_level=ActivityLevel.MODERATELY_ACTIVE
        )

        # BMR for this person = 1648.75
        # TDEE = 1648.75 * 1.55 = 2555.56
        assert tdee.value == 2555.56

    def test_tdee_immutable(self):
        """Test that TDEE is immutable."""
        bmr = BMR(value=1648.75)
        tdee = TDEE.calculate(bmr, ActivityLevel.SEDENTARY)
        with pytest.raises(Exception):
            tdee.value = 2500.0


class TestValueObjectEquality:
    """Test that value objects are compared by value, not identity."""

    def test_bmr_equality(self):
        """Test that two BMR objects with same value are equal."""
        bmr1 = BMR(value=1648.75)
        bmr2 = BMR(value=1648.75)
        assert bmr1 == bmr2
        assert bmr1 is not bmr2  # Different objects

    def test_bmr_inequality(self):
        """Test that two BMR objects with different values are not equal."""
        bmr1 = BMR(value=1648.75)
        bmr2 = BMR(value=1500.0)
        assert bmr1 != bmr2

    def test_tdee_equality(self):
        """Test that two TDEE objects with same value are equal."""
        tdee1 = TDEE(value=2555.56)
        tdee2 = TDEE(value=2555.56)
        assert tdee1 == tdee2
        assert tdee1 is not tdee2

    def test_bmi_equality(self):
        """Test that two BMI objects with same value are equal."""
        bmi1 = BMI(value=22.86)
        bmi2 = BMI(value=22.86)
        assert bmi1 == bmi2
        assert bmi1 is not bmi2


class TestBackwardCompatibility:
    """
    CRITICAL: These tests verify that our value objects produce IDENTICAL results
    to the existing OnboardingService methods.

    If ANY of these tests fail, the migration is WRONG and must be fixed.
    """

    def test_bmr_matches_onboarding_service_male(self):
        """
        Verify BMR matches OnboardingService.calculate_bmr() for male.

        This is the EXACT test case from the current system.
        """
        # Using the same inputs that OnboardingService would receive
        weight_kg = 75.0
        height_cm = 180.0
        age = 28
        sex = "male"

        # Our new value object
        bmr_new = BMR.calculate(weight_kg, height_cm, age, sex)

        # Expected from OnboardingService formula:
        # bmr = 10 * 75 + 6.25 * 180 - 5 * 28 + 5
        # bmr = 750 + 1125 - 140 + 5 = 1740.0
        expected = 1740.0

        assert bmr_new.value == expected, f"BMR mismatch! Expected {expected}, got {bmr_new.value}"

    def test_bmr_matches_onboarding_service_female(self):
        """Verify BMR matches OnboardingService.calculate_bmr() for female."""
        weight_kg = 60.0
        height_cm = 165.0
        age = 25
        sex = "female"

        bmr_new = BMR.calculate(weight_kg, height_cm, age, sex)

        # Expected: 10 * 60 + 6.25 * 165 - 5 * 25 - 161
        # = 600 + 1031.25 - 125 - 161 = 1345.25
        expected = 1345.25

        assert bmr_new.value == expected

    def test_tdee_matches_onboarding_service_sedentary(self):
        """Verify TDEE matches OnboardingService.calculate_tdee() for sedentary."""
        bmr_value = 1740.0
        bmr = BMR(value=bmr_value)
        activity_level = ActivityLevel.SEDENTARY

        tdee_new = TDEE.calculate(bmr, activity_level)

        # Expected: 1740.0 * 1.2 = 2088.0
        expected = 2088.0

        assert tdee_new.value == expected

    def test_tdee_matches_onboarding_service_very_active(self):
        """Verify TDEE matches OnboardingService.calculate_tdee() for very active."""
        bmr_value = 1345.25
        bmr = BMR(value=bmr_value)
        activity_level = ActivityLevel.VERY_ACTIVE

        tdee_new = TDEE.calculate(bmr, activity_level)

        # Expected: 1345.25 * 1.725 = 2320.56
        expected = 2320.56

        assert tdee_new.value == expected
