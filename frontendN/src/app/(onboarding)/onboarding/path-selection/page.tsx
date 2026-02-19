'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Loader2, Clock, Utensils, Moon, Sun, Dumbbell as Weight } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from '@/components/ui/form';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { onboardingAPI } from '@/lib/api';

const formSchema = z.object({
  path_type: z.enum(['if_16_8', 'if_18_6', 'omad', 'traditional', 'bodybuilder']),
});

type FormValues = z.infer<typeof formSchema>;

const pathOptions = [
  {
    value: 'traditional',
    icon: Utensils,
    title: 'Traditional Eating',
    description: 'Breakfast, lunch, dinner, and snacks',
    meals: '4 meals/day',
    timing: 'Spread throughout the day',
    color: 'text-blue-500 bg-blue-50',
  },
  {
    value: 'if_16_8',
    icon: Clock,
    title: 'Intermittent Fasting 16:8',
    description: '16 hours fasting, 8 hours eating',
    meals: '2-3 meals/day',
    timing: '12 PM - 8 PM',
    color: 'text-green-500 bg-green-50',
  },
  {
    value: 'if_18_6',
    icon: Moon,
    title: 'Intermittent Fasting 18:6',
    description: '18 hours fasting, 6 hours eating',
    meals: '2 meals/day',
    timing: '2 PM - 8 PM',
    color: 'text-purple-500 bg-purple-50',
  },
  {
    value: 'omad',
    icon: Sun,
    title: 'One Meal A Day (OMAD)',
    description: 'Single large meal per day',
    meals: '1 meal/day',
    timing: 'Flexible timing',
    color: 'text-orange-500 bg-orange-50',
  },
  {
    value: 'bodybuilder',
    icon: Weight,
    title: 'Bodybuilder Split',
    description: 'Frequent small meals for muscle building',
    meals: '5-6 meals/day',
    timing: 'Every 2-3 hours',
    color: 'text-red-500 bg-red-50',
  },
];

export default function PathSelectionPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      path_type: 'traditional',
    },
  });

  const onSubmit = async (values: FormValues) => {
    setIsLoading(true);
    try {
      const response = await onboardingAPI.submitPath(values);
      
      toast.success('Eating path set successfully!');
      router.push(response.next_step);
    } catch (error: any) {
      toast.error(error.response?.data?.detail?.message || 'Failed to save path');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl shadow-lg p-8 space-y-6">
      <div className="space-y-2">
        <h2 className="text-2xl font-bold text-gray-900">Choose your eating pattern</h2>
        <p className="text-gray-600">Select a meal timing strategy that fits your lifestyle</p>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          <FormField
            control={form.control}
            name="path_type"
            render={({ field }) => (
              <FormItem>
                <FormControl>
                  <RadioGroup
                    onValueChange={field.onChange}
                    defaultValue={field.value}
                    className="space-y-4"
                  >
                    {pathOptions.map((path) => {
                      const Icon = path.icon;
                      const isSelected = field.value === path.value;
                      
                      return (
                        <div key={path.value} className="relative">
                          <RadioGroupItem
                            value={path.value}
                            id={path.value}
                            className="peer sr-only"
                          />
                          <Label
                            htmlFor={path.value}
                            className={`flex items-start space-x-4 rounded-lg border-2 p-4 cursor-pointer transition-all hover:shadow-md ${
                              isSelected
                                ? 'border-green-500 bg-green-50'
                                : 'border-gray-200 hover:border-gray-300'
                            }`}
                          >
                            <div className={`p-3 rounded-lg ${path.color} flex-shrink-0`}>
                              <Icon className="w-6 h-6" />
                            </div>
                            <div className="flex-1 space-y-1">
                              <div className="font-semibold text-gray-900">{path.title}</div>
                              <div className="text-sm text-gray-600">{path.description}</div>
                              <div className="flex gap-4 mt-2 text-xs text-gray-500">
                                <span className="font-medium">{path.meals}</span>
                                <span>•</span>
                                <span>{path.timing}</span>
                              </div>
                            </div>
                          </Label>
                        </div>
                      );
                    })}
                  </RadioGroup>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

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
                  Saving...
                </>
              ) : (
                'Continue'
              )}
            </Button>
          </div>
        </form>
      </Form>
    </div>
  );
}