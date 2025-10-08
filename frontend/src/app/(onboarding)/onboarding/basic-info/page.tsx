'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Loader2 } from 'lucide-react';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { onboardingAPI } from '@/lib/api';

const formSchema = z.object({
  name: z.string().min(2, 'Name must be at least 2 characters'),
  age: z.coerce.number().min(13, 'Must be at least 13 years old').max(100, 'Invalid age'),
  height_cm: z.coerce.number().min(100, 'Height must be at least 100cm').max(250, 'Height must be less than 250cm'),
  weight_kg: z.coerce.number().min(30, 'Weight must be at least 30kg').max(300, 'Weight must be less than 300kg'),
  sex: z.enum(['male', 'female']),
  activity_level: z.enum(['sedentary', 'lightly_active', 'moderately_active', 'very_active', 'extra_active']),
});

type FormValues = z.infer<typeof formSchema>;

export default function BasicInfoPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      age: 25,
      height_cm: 170,
      weight_kg: 70,
      sex: 'male',
      activity_level: 'moderately_active',
    },
  });

  const onSubmit = async (values: FormValues) => {
    setIsLoading(true);
    try {
      const response = await onboardingAPI.submitBasicInfo({
        ...values,
        medical_conditions: [],
      });
      
      toast.success('Basic information saved!');
      router.push(response.next_step);
    } catch (error: any) {
      toast.error(error.response?.data?.detail?.message || 'Failed to save information');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl shadow-lg p-8 space-y-6">
      <div className="space-y-2">
        <h2 className="text-2xl font-bold text-gray-900">Tell us about yourself</h2>
        <p className="text-gray-600">We'll use this information to personalize your nutrition plan</p>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          <FormField
            control={form.control}
            name="name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Full Name</FormLabel>
                <FormControl>
                  <Input placeholder="John Doe" {...field} disabled={isLoading} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <div className="grid grid-cols-2 gap-4">
            <FormField
              control={form.control}
              name="age"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Age</FormLabel>
                  <FormControl>
                    <Input type="number" placeholder="25" {...field} disabled={isLoading} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="sex"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Sex</FormLabel>
                  <Select onValueChange={field.onChange} defaultValue={field.value} disabled={isLoading}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select sex" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="male">Male</SelectItem>
                      <SelectItem value="female">Female</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <FormField
              control={form.control}
              name="height_cm"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Height (cm)</FormLabel>
                  <FormControl>
                    <Input type="number" placeholder="170" {...field} disabled={isLoading} />
                  </FormControl>
                  <FormDescription>Your height in centimeters</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="weight_kg"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Weight (kg)</FormLabel>
                  <FormControl>
                    <Input type="number" placeholder="70" {...field} disabled={isLoading} />
                  </FormControl>
                  <FormDescription>Your current weight in kilograms</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>

          <FormField
            control={form.control}
            name="activity_level"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Activity Level</FormLabel>
                <Select onValueChange={field.onChange} defaultValue={field.value} disabled={isLoading}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Select activity level" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    <SelectItem value="sedentary">
                      <div>
                        <div className="font-medium">Sedentary</div>
                        <div className="text-xs text-gray-500">Little or no exercise</div>
                      </div>
                    </SelectItem>
                    <SelectItem value="lightly_active">
                      <div>
                        <div className="font-medium">Lightly Active</div>
                        <div className="text-xs text-gray-500">Exercise 1-3 times/week</div>
                      </div>
                    </SelectItem>
                    <SelectItem value="moderately_active">
                      <div>
                        <div className="font-medium">Moderately Active</div>
                        <div className="text-xs text-gray-500">Exercise 4-5 times/week</div>
                      </div>
                    </SelectItem>
                    <SelectItem value="very_active">
                      <div>
                        <div className="font-medium">Very Active</div>
                        <div className="text-xs text-gray-500">Intense exercise 6-7 times/week</div>
                      </div>
                    </SelectItem>
                    <SelectItem value="extra_active">
                      <div>
                        <div className="font-medium">Extra Active</div>
                        <div className="text-xs text-gray-500">Very intense exercise daily</div>
                      </div>
                    </SelectItem>
                  </SelectContent>
                </Select>
                <FormDescription>How active are you on a typical week?</FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          <Button type="submit" className="w-full" size="lg" disabled={isLoading}>
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              'Continue'
            )}
          </Button>
        </form>
      </Form>
    </div>
  );
}