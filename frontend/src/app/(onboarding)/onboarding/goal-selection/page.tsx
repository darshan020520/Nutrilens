'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Loader2, Target, TrendingUp, Activity, Heart, Dumbbell, Scale } from 'lucide-react';
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
import { Input } from '@/components/ui/input';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { onboardingAPI } from '@/lib/api';
import { Label } from '@/components/ui/label';

const formSchema = z.object({
  goal_type: z.enum(['muscle_gain', 'fat_loss', 'body_recomp', 'weight_training', 'endurance', 'general_health']),
  target_weight: z.coerce.number().min(30).max(300).optional(),
  target_date: z.string().optional(),
});

type FormValues = z.infer<typeof formSchema>;

const goalOptions = [
  {
    value: 'fat_loss',
    icon: TrendingUp,
    title: 'Fat Loss',
    description: 'Reduce body fat while preserving muscle',
    color: 'text-red-500 bg-red-50',
  },
  {
    value: 'muscle_gain',
    icon: Dumbbell,
    title: 'Muscle Gain',
    description: 'Build lean muscle mass with proper nutrition',
    color: 'text-blue-500 bg-blue-50',
  },
  {
    value: 'body_recomp',
    icon: Scale,
    title: 'Body Recomposition',
    description: 'Lose fat and gain muscle simultaneously',
    color: 'text-purple-500 bg-purple-50',
  },
  {
    value: 'weight_training',
    icon: Activity,
    title: 'Weight Training Support',
    description: 'Optimize nutrition for strength training',
    color: 'text-orange-500 bg-orange-50',
  },
  {
    value: 'endurance',
    icon: Target,
    title: 'Endurance',
    description: 'Fuel for cardio and endurance activities',
    color: 'text-green-500 bg-green-50',
  },
  {
    value: 'general_health',
    icon: Heart,
    title: 'General Health',
    description: 'Maintain a balanced, healthy lifestyle',
    color: 'text-pink-500 bg-pink-50',
  },
];

export default function GoalSelectionPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      goal_type: 'fat_loss',
    },
  });

  const selectedGoal = form.watch('goal_type');

  const onSubmit = async (values: FormValues) => {
    setIsLoading(true);
    try {
      const response = await onboardingAPI.submitGoal(values);
      
      toast.success('Goal set successfully!');
      router.push(response.next_step);
    } catch (error: any) {
      toast.error(error.response?.data?.detail?.message || 'Failed to save goal');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl shadow-lg p-8 space-y-6">
      <div className="space-y-2">
        <h2 className="text-2xl font-bold text-gray-900">What's your goal?</h2>
        <p className="text-gray-600">Choose the goal that best fits your nutrition journey</p>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          <FormField
            control={form.control}
            name="goal_type"
            render={({ field }) => (
              <FormItem>
                <FormControl>
                  <RadioGroup
                    onValueChange={field.onChange}
                    defaultValue={field.value}
                    className="grid grid-cols-1 md:grid-cols-2 gap-4"
                  >
                    {goalOptions.map((goal) => {
                      const Icon = goal.icon;
                      const isSelected = field.value === goal.value;
                      
                      return (
                        <div key={goal.value} className="relative">
                          <RadioGroupItem
                            value={goal.value}
                            id={goal.value}
                            className="peer sr-only"
                          />
                          <Label
                            htmlFor={goal.value}
                            className={`flex flex-col items-start space-y-2 rounded-lg border-2 p-4 cursor-pointer transition-all hover:shadow-md ${
                              isSelected
                                ? 'border-green-500 bg-green-50'
                                : 'border-gray-200 hover:border-gray-300'
                            }`}
                          >
                            <div className={`p-2 rounded-lg ${goal.color}`}>
                              <Icon className="w-6 h-6" />
                            </div>
                            <div className="space-y-1">
                              <div className="font-semibold text-gray-900">{goal.title}</div>
                              <div className="text-sm text-gray-600">{goal.description}</div>
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

          {/* Optional target weight */}
          {(selectedGoal === 'fat_loss' || selectedGoal === 'body_recomp') && (
            <FormField
              control={form.control}
              name="target_weight"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Target Weight (Optional)</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      placeholder="65"
                      {...field}
                      disabled={isLoading}
                    />
                  </FormControl>
                  <FormDescription>Your target weight in kilograms</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          )}

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