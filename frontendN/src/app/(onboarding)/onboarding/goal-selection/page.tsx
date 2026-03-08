'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Activity, Dumbbell, Heart, Loader2, Scale, Target, TrendingUp } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { onboardingAPI } from '@/lib/api';
import StepTransitionOverlay from '../components/StepTransitionOverlay';
import { getOnboardingFirstName } from '../components/onboardingSession';

const formSchema = z.object({
  goal_type: z.enum(['muscle_gain', 'fat_loss', 'body_recomp', 'weight_training', 'endurance', 'general_health']),
  target_weight: z.number().min(30).max(300).optional(),
  target_date: z.string().optional(),
});

type FormValues = z.infer<typeof formSchema>;

type GoalSelectionResponse = {
  next_step: string;
};

function getErrorMessage(error: unknown, fallback: string): string {
  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof (error as { response?: { data?: { detail?: { message?: string } } } }).response?.data?.detail
      ?.message === 'string'
  ) {
    return (error as { response?: { data?: { detail?: { message?: string } } } }).response?.data?.detail
      ?.message as string;
  }

  return fallback;
}

const goalOptions = [
  {
    value: 'fat_loss',
    icon: TrendingUp,
    title: 'Fat loss',
    description: 'Reduce body fat while preserving muscle',
    tone: 'text-rose-600 bg-rose-50',
  },
  {
    value: 'muscle_gain',
    icon: Dumbbell,
    title: 'Muscle gain',
    description: 'Build lean mass with higher protein support',
    tone: 'text-blue-600 bg-blue-50',
  },
  {
    value: 'body_recomp',
    icon: Scale,
    title: 'Body recomposition',
    description: 'Progressively lose fat while improving muscle',
    tone: 'text-violet-600 bg-violet-50',
  },
  {
    value: 'weight_training',
    icon: Activity,
    title: 'Training performance',
    description: 'Fuel strength sessions and recovery better',
    tone: 'text-orange-600 bg-orange-50',
  },
  {
    value: 'endurance',
    icon: Target,
    title: 'Endurance',
    description: 'Support higher energy demand for cardio focus',
    tone: 'text-emerald-600 bg-emerald-50',
  },
  {
    value: 'general_health',
    icon: Heart,
    title: 'General health',
    description: 'Maintain a sustainable and balanced routine',
    tone: 'text-pink-600 bg-pink-50',
  },
];

export default function GoalSelectionPage() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showTransition, setShowTransition] = useState(false);
  const [requestReady, setRequestReady] = useState(false);
  const [nextStep, setNextStep] = useState<string | null>(null);
  const [firstName, setFirstName] = useState('');

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      goal_type: 'fat_loss',
    },
  });

  useEffect(() => {
    setFirstName(getOnboardingFirstName());
  }, []);

  const selectedGoal = form.watch('goal_type');

  const onSubmit = async (values: FormValues) => {
    setIsSubmitting(true);
    setRequestReady(false);
    setNextStep(null);

    const openTimer = window.setTimeout(() => {
      setShowTransition(true);
    }, 300);

    try {
      const response = (await onboardingAPI.submitGoal(values)) as GoalSelectionResponse;
      setNextStep(response.next_step);
      setRequestReady(true);
    } catch (error: unknown) {
      window.clearTimeout(openTimer);
      setShowTransition(false);
      setIsSubmitting(false);
      setRequestReady(false);
      toast.error(getErrorMessage(error, 'Failed to save goal'));
    }
  };

  const disableInputs = isSubmitting;

  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-[18px] border border-white/75 bg-white/92 p-7 shadow-[0_24px_60px_-42px_rgba(15,23,42,0.45)] transition-transform duration-300 md:p-8',
        showTransition ? 'scale-[0.995]' : 'scale-100'
      )}
    >
      <div className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500" />

      <div className="space-y-2">
        <h2 className="text-2xl font-semibold tracking-[-0.015em] text-slate-900">What&apos;s your main goal?</h2>
        <p className="text-sm leading-6 text-slate-600">Choose what matters most right now.</p>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="mt-7 space-y-6">
          <FormField
            control={form.control}
            name="goal_type"
            render={({ field }) => (
              <FormItem>
                <FormControl>
                  <RadioGroup onValueChange={field.onChange} value={field.value} className="grid gap-4 md:grid-cols-2">
                    {goalOptions.map((goal) => {
                      const Icon = goal.icon;
                      const isSelected = field.value === goal.value;

                      return (
                        <div key={goal.value}>
                          <RadioGroupItem value={goal.value} id={goal.value} className="sr-only" />
                          <Label
                            htmlFor={goal.value}
                            className={cn(
                              'group flex min-h-[158px] cursor-pointer flex-col justify-between rounded-[18px] border p-5 transition-[transform,box-shadow,border-color,background-color] duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]',
                              isSelected
                                ? 'border-emerald-400/80 bg-emerald-50/70 shadow-[0_16px_34px_-24px_rgba(16,185,129,0.65)]'
                                : 'border-slate-200 bg-white hover:-translate-y-[1px] hover:border-slate-300 hover:shadow-[0_14px_30px_-24px_rgba(15,23,42,0.3)]'
                            )}
                          >
                            <div
                              className={cn(
                                'inline-flex h-10 w-10 items-center justify-center rounded-[14px] transition-transform duration-300',
                                goal.tone,
                                isSelected ? 'scale-105' : 'scale-100'
                              )}
                            >
                              <Icon className="h-5 w-5" />
                            </div>
                            <div className="space-y-1.5">
                              <p className="text-base font-semibold text-slate-900">{goal.title}</p>
                              <p className="text-sm leading-6 text-slate-600">{goal.description}</p>
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

          {(selectedGoal === 'fat_loss' || selectedGoal === 'body_recomp') ? (
            <FormField
              control={form.control}
              name="target_weight"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-xs font-medium uppercase tracking-[0.1em] text-slate-500">
                    Optional target weight (kg)
                  </FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      inputMode="decimal"
                      value={field.value ?? ''}
                      onChange={(event) => {
                        const parsed = event.target.valueAsNumber;
                        field.onChange(Number.isNaN(parsed) ? undefined : parsed);
                      }}
                      disabled={disableInputs}
                      className="h-12 rounded-[16px] border-slate-200 bg-white/90 transition-[border-color,box-shadow] duration-200 focus-visible:border-emerald-400 focus-visible:ring-4 focus-visible:ring-emerald-100"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          ) : null}

          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
            <Button
              type="button"
              variant="outline"
              onClick={() => router.back()}
              disabled={disableInputs}
              className="h-12 rounded-[16px] border-slate-200 px-6"
            >
              Back
            </Button>

            <Button
              type="submit"
              size="lg"
              disabled={disableInputs}
              className="relative h-12 w-full overflow-hidden rounded-[16px] bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-[0_16px_30px_-20px_rgba(5,150,105,0.7)] transition-all duration-200 hover:from-emerald-500 hover:to-teal-500 hover:shadow-[0_20px_34px_-20px_rgba(5,150,105,0.82)] sm:w-[210px]"
            >
              <span className={cn('transition-opacity duration-200', disableInputs ? 'opacity-0' : 'opacity-100')}>
                Continue
              </span>
              <span
                className={cn(
                  'pointer-events-none absolute inset-0 flex items-center justify-center gap-2 transition-opacity duration-200',
                  disableInputs ? 'opacity-100' : 'opacity-0'
                )}
              >
                <Loader2 className="h-4 w-4 animate-spin" />
                Saving...
              </span>
            </Button>
          </div>
        </form>
      </Form>

      <StepTransitionOverlay
        open={showTransition}
        ready={requestReady}
        title="Aligning your goal..."
        description="Understanding your goal profile and setting the right direction."
        checkpoints={[
          'Understanding goal intensity',
          'Setting calorie direction',
          'Preparing macro balance',
        ]}
        completionTitle={firstName ? `Great choice, ${firstName}.` : 'Great choice.'}
        completionDescription="Now let's shape your eating pattern."
        onComplete={() => {
          if (nextStep) router.push(nextStep);
        }}
      />
    </div>
  );
}
