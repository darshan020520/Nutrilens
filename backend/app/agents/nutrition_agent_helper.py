# Helper method to add to nutrition_agent.py

    def _generate_why_explanation(self, recipe: Recipe, score_obj: SuggestionScore,
                                  meal_targets: Dict[str, float], context: Optional[MealContext]) -> str:
        """
        Generate natural language "WHY" explanation for recipe suggestion

        This is UNIQUE intelligence that explains to the user why this recipe was suggested
        """
        reasons = []

        # Macro fit explanation
        if score_obj.macro_fit > 80:
            calories_match = abs(recipe.macros_per_serving.get("calories", 0) - meal_targets.get("calories", 0))
            protein_match = abs(recipe.macros_per_serving.get("protein_g", 0) - meal_targets.get("protein_g", 0))

            if calories_match < 100:
                reasons.append(f"Perfectly fits your remaining {int(meal_targets.get('calories', 0))} calories")
            if protein_match < 10:
                reasons.append(f"Provides the {int(meal_targets.get('protein_g', 0))}g protein you need")
        elif score_obj.macro_fit > 60:
            reasons.append("Good macro balance for your remaining targets")

        # Context relevance
        if context:
            if context == MealContext.PRE_WORKOUT:
                reasons.append("Light and energizing - perfect before your workout")
            elif context == MealContext.POST_WORKOUT:
                reasons.append("High protein for muscle recovery after training")
            elif context == MealContext.QUICK_MEAL:
                reasons.append(f"Quick to prepare ({recipe.prep_time_min} min) for your busy schedule")
            elif context == MealContext.LOW_ENERGY:
                reasons.append("Balanced energy without causing a crash")

        # Inventory availability
        if score_obj.inventory_coverage == 100:
            reasons.append("You have all ingredients in your inventory")
        elif score_obj.inventory_coverage >= 70:
            reasons.append("You have most ingredients already")

        # Goal alignment
        if score_obj.goal_alignment > 80:
            reasons.append("Optimized for your fitness goal")

        # Nutritional quality
        if score_obj.nutritional_quality > 75:
            macros = recipe.macros_per_serving
            if macros.get("fiber_g", 0) > 8:
                reasons.append("High fiber for satiety and digestion")
            if macros.get("protein_g", 0) > 30:
                reasons.append("High protein content")

        # Combine into natural sentence
        if len(reasons) == 0:
            return "This recipe matches your general nutritional needs"
        elif len(reasons) == 1:
            return reasons[0]
        elif len(reasons) == 2:
            return f"{reasons[0]}, and {reasons[1].lower()}"
        else:
            return f"{', '.join(reasons[:-1])}, and {reasons[-1].lower()}"
