'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Loader2, Leaf, Fish, Beef, Salad } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  FormDescription,
} from '@/components/ui/form';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { onboardingAPI } from '@/lib/api';

const formSchema = z.object({
  dietary_type: z.enum(['vegetarian', 'non_vegetarian', 'vegan', 'pescatarian']),
  allergies: z.array(z.string()).optional(),
  cuisine_preferences: z.array(z.string()).min(1, 'Select at least one cuisine'),
  max_prep_time_weekday: z.coerce.number().min(10).max(120),
  max_prep_time_weekend: z.coerce.number().min(10).max(180),
});

type FormValues = z.infer<typeof formSchema>;

const cuisineOptions = [
  { value: 'indian', label: 'Indian' },
  { value: 'continental', label: 'Continental' },
  { value: 'asian', label: 'Asian' },
  { value: 'mediterranean', label: 'Mediterranean' },
  { value: 'mexican', label: 'Mexican' },
  { value: 'italian', label: 'Italian' },
];

const allergyOptions = [
  { value: 'nuts', label: 'Nuts' },
  { value: 'dairy', label: 'Dairy' },
  { value: 'gluten', label: 'Gluten' },
  { value: 'soy', label: 'Soy' },
  { value: 'eggs', label: 'Eggs' },
  { value: 'shellfish', label: 'Shellfish' },
];

export default function PreferencesPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      dietary_type: 'non_vegetarian',
      allergies: [],
      cuisine_preferences: ['indian'],
      max_prep_time_weekday: 30,
      max_prep_time_weekend: 60,
    },
  });

  const onSubmit = async (values: FormValues) => {
    setIsLoading(true);
    try {
      const response = await onboardingAPI.submitPreferences({
        ...values,
        disliked_ingredients: [], // Can add UI for this later
      });
      
      toast.success('🎉 Profile setup complete! Welcome to NutriLens AI!');
      setTimeout(() => {
        router.push(response.redirect_to);
      }, 1000);
    } catch (error: any) {
      toast.error(error.response?.data?.detail?.message || 'Failed to save preferences');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl shadow-lg p-8 space-y-6">
      <div className="space-y-2">
        <h2 className="text-2xl font-bold text-gray-900">Final step: Your preferences</h2>
        <p className="text-gray-600">Help us personalize your meal recommendations</p>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          {/* Dietary Type */}
          <FormField
            control={form.control}
            name="dietary_type"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Dietary Preference</FormLabel>
                <Select onValueChange={field.onChange} defaultValue={field.value} disabled={isLoading}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Select dietary type" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    <SelectItem value="non_vegetarian">
                      <div className="flex items-center gap-2">
                        <Beef className="w-4 h-4" />
                        Non-Vegetarian
                      </div>
                    </SelectItem>
                    <SelectItem value="vegetarian">
                      <div className="flex items-center gap-2">
                        <Salad className="w-4 h-4" />
                        Vegetarian
                      </div>
                    </SelectItem>
                    <SelectItem value="vegan">
                      <div className="flex items-center gap-2">
                        <Leaf className="w-4 h-4" />
                        Vegan
                      </div>
                    </SelectItem>
                    <SelectItem value="pescatarian">
                      <div className="flex items-center gap-2">
                        <Fish className="w-4 h-4" />
                        Pescatarian
                      </div>
                    </SelectItem>
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Allergies */}
          <FormField
            control={form.control}
            name="allergies"
            render={() => (
              <FormItem>
                <FormLabel>Allergies (Optional)</FormLabel>
                <FormDescription>Select any food allergies you have</FormDescription>
                <div className="grid grid-cols-2 gap-2 mt-2">
                  {allergyOptions.map((allergy) => (
                    <FormField
                      key={allergy.value}
                      control={form.control}
                      name="allergies"
                      render={({ field }) => (
                        <FormItem className="flex items-center space-x-2 space-y-0">
                          <FormControl>
                            <Checkbox
                              checked={field.value?.includes(allergy.value)}
                              onCheckedChange={(checked) => {
                                const current = field.value || [];
                                const updated = checked
                                  ? [...current, allergy.value]
                                  : current.filter((v) => v !== allergy.value);
                                field.onChange(updated);
                              }}
                            />
                          </FormControl>
                          <FormLabel className="font-normal cursor-pointer">
                            {allergy.label}
                          </FormLabel>
                        </FormItem>
                      )}
                    />
                  ))}
                </div>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Cuisine Preferences */}
          <FormField
            control={form.control}
            name="cuisine_preferences"
            render={() => (
              <FormItem>
                <FormLabel>Favorite Cuisines *</FormLabel>
                <FormDescription>Select at least one cuisine type</FormDescription>
                <div className="grid grid-cols-2 gap-2 mt-2">
                  {cuisineOptions.map((cuisine) => (
                    <FormField
                      key={cuisine.value}
                      control={form.control}
                      name="cuisine_preferences"
                      render={({ field }) => (
                        <FormItem className="flex items-center space-x-2 space-y-0">
                          <FormControl>
                            <Checkbox
                              checked={field.value?.includes(cuisine.value)}
                              onCheckedChange={(checked) => {
                                const current = field.value || [];
                                const updated = checked
                                  ? [...current, cuisine.value]
                                  : current.filter((v) => v !== cuisine.value);
                                field.onChange(updated);
                              }}
                            />
                          </FormControl>
                          <FormLabel className="font-normal cursor-pointer">
                            {cuisine.label}
                          </FormLabel>
                        </FormItem>
                      )}
                    />
                  ))}
                </div>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Prep Time */}
          <div className="grid grid-cols-2 gap-4">
            <FormField
              control={form.control}
              name="max_prep_time_weekday"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Max Prep Time (Weekday)</FormLabel>
                  <FormControl>
                    <Input type="number" placeholder="30" {...field} disabled={isLoading} />
                  </FormControl>
                  <FormDescription>Minutes per meal</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="max_prep_time_weekend"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Max Prep Time (Weekend)</FormLabel>
                  <FormControl>
                    <Input type="number" placeholder="60" {...field} disabled={isLoading} />
                  </FormControl>
                  <FormDescription>Minutes per meal</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>

          <div className="flex gap-4">
            <Button
              type="button"
              variant="outline"
              className="flex-1"
              onClick={() => router.back()}
              disabled={isLoading}
            >
              Back
            </Button>
            <Button type="submit" className="flex-1" disabled={isLoading}>
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Completing setup...
                </>
              ) : (
                'Complete Setup'
              )}
            </Button>
          </div>
        </form>
      </Form>
    </div>
  );
}