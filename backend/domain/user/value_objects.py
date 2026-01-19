"""
User domain value objects.

These are immutable value objects representing user-related domain concepts.
All calculations are copied EXACTLY from the existing codebase to preserve behavior.
"""
from dataclasses import dataclass
from typing import Literal
from enum import Enum


class ActivityLevel(str, Enum):
    """Activity level enumeration (copied from database.py)."""
    SEDENTARY = "sedentary"
    LIGHTLY_ACTIVE = "lightly_active"
    MODERATELY_ACTIVE = "moderately_active"
    VERY_ACTIVE = "very_active"
    EXTRA_ACTIVE = "extra_active"


@dataclass(frozen=True)
class BMI:
    """
    Body Mass Index value object.

    BMI = weight (kg) / height (m)^2

    Immutable value object that represents a calculated BMI.
    """
    value: float

    @classmethod
    def from_measurements(cls, weight_kg: float, height_cm: float) -> "BMI":
        """
        Calculate BMI from weight and height measurements.

        Args:
            weight_kg: Weight in kilograms
            height_cm: Height in centimeters

        Returns:
            BMI value object

        Raises:
            ValueError: If weight or height is invalid
        """
        if weight_kg <= 0:
            raise ValueError("Weight must be positive")
        if height_cm <= 0:
            raise ValueError("Height must be positive")

        height_m = height_cm / 100.0
        bmi_value = weight_kg / (height_m ** 2)

        return cls(value=round(bmi_value, 2))

    def category(self) -> str:
        """
        Get BMI category according to WHO standards.

        Returns:
            Category name: underweight, normal, overweight, or obese
        """
        if self.value < 18.5:
            return "underweight"
        elif self.value < 25.0:
            return "normal"
        elif self.value < 30.0:
            return "overweight"
        else:
            return "obese"


@dataclass(frozen=True)
class BMR:
    """
    Basal Metabolic Rate value object.

    BMR represents the number of calories burned at rest.
    Calculated using Mifflin-St Jeor Formula.

    Men: BMR = 10 × weight(kg) + 6.25 × height(cm) - 5 × age(years) + 5
    Women: BMR = 10 × weight(kg) + 6.25 × height(cm) - 5 × age(years) - 161

    This calculation is COPIED EXACTLY from backend/app/services/onboarding.py:70-81
    """
    value: float

    @classmethod
    def calculate(
        cls,
        weight_kg: float,
        height_cm: float,
        age: int,
        sex: Literal["male", "female"]
    ) -> "BMR":
        """
        Calculate Basal Metabolic Rate using Mifflin-St Jeor Formula.

        This is the EXACT logic from OnboardingService.calculate_bmr() (onboarding.py:70-81).

        Args:
            weight_kg: Weight in kilograms
            height_cm: Height in centimeters
            age: Age in years
            sex: Biological sex ("male" or "female")

        Returns:
            BMR value object

        Raises:
            ValueError: If any parameter is invalid
        """
        if weight_kg <= 0:
            raise ValueError("Weight must be positive")
        if height_cm <= 0:
            raise ValueError("Height must be positive")
        if age <= 0:
            raise ValueError("Age must be positive")
        if sex not in ("male", "female"):
            raise ValueError("Sex must be 'male' or 'female'")

        # EXACT COPY from onboarding.py lines 76-81
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age
        if sex == "male":
            bmr += 5
        else:
            bmr -= 161

        return cls(value=round(bmr, 2))


@dataclass(frozen=True)
class TDEE:
    """
    Total Daily Energy Expenditure value object.

    TDEE represents total calories burned per day including activity.
    Calculated as: BMR × Activity Level Multiplier

    This calculation is COPIED EXACTLY from backend/app/services/onboarding.py:84-87
    """
    value: float

    # Activity level multipliers (COPIED from OnboardingService.ACTIVITY_MULTIPLIERS)
    ACTIVITY_MULTIPLIERS = {
        ActivityLevel.SEDENTARY: 1.2,
        ActivityLevel.LIGHTLY_ACTIVE: 1.375,
        ActivityLevel.MODERATELY_ACTIVE: 1.55,
        ActivityLevel.VERY_ACTIVE: 1.725,
        ActivityLevel.EXTRA_ACTIVE: 1.9
    }

    @classmethod
    def calculate(cls, bmr: BMR, activity_level: ActivityLevel) -> "TDEE":
        """
        Calculate Total Daily Energy Expenditure.

        This is the EXACT logic from OnboardingService.calculate_tdee() (onboarding.py:84-87).

        Args:
            bmr: Basal Metabolic Rate value object
            activity_level: Activity level enum

        Returns:
            TDEE value object

        Raises:
            ValueError: If activity level is invalid
        """
        if activity_level not in cls.ACTIVITY_MULTIPLIERS:
            raise ValueError(f"Invalid activity level: {activity_level}")

        # EXACT COPY from onboarding.py lines 86-87
        multiplier = cls.ACTIVITY_MULTIPLIERS[activity_level]
        tdee_value = bmr.value * multiplier

        return cls(value=round(tdee_value, 2))

    @classmethod
    def from_measurements(
        cls,
        weight_kg: float,
        height_cm: float,
        age: int,
        sex: Literal["male", "female"],
        activity_level: ActivityLevel
    ) -> "TDEE":
        """
        Convenience method to calculate TDEE directly from measurements.

        Args:
            weight_kg: Weight in kilograms
            height_cm: Height in centimeters
            age: Age in years
            sex: Biological sex ("male" or "female")
            activity_level: Activity level enum

        Returns:
            TDEE value object
        """
        bmr = BMR.calculate(weight_kg, height_cm, age, sex)
        return cls.calculate(bmr, activity_level)
