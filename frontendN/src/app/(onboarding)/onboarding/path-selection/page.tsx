'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Clock, Dumbbell, Loader2, Moon, Sun, Utensils } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from '@/components/ui/form';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { cn } from '@/lib/utils';
import { onboardingAPI } from '@/lib/api';
import StepTransitionOverlay from '../components/StepTransitionOverlay';
import { getOnboardingFirstName } from '../components/onboardingSession';

const formSchema = z.object({
  path_type: z.enum(['if_16_8', 'if_18_6', 'omad', 'traditional', 'bodybuilder']),
});

type FormValues = z.infer<typeof formSchema>;

type PathSelectionResponse = {
  next_step: string;
};

type ApiErrorLike = {
  response?: {
    data?: {
      detail?: {
        message?: string;
      };
    };
  };
};

function getErrorMessage(error: unknown, fallback: string): string {
  const message = (error as ApiErrorLike)?.response?.data?.detail?.message;
  return typeof message === 'string' ? message : fallback;
}

const pathOptions = [
  {
    value: 'traditional',
    icon: Utensils,
    title: 'Traditional eating',
    description: 'Breakfast, lunch, dinner, and optional snacks',
    meals: '4 meals/day',
    timing: 'Spread through the day',
    tone: 'text-blue-600 bg-blue-50',
  },
  {
    value: 'if_16_8',
    icon: Clock,
    title: 'Intermittent fasting 16:8',
    description: '16 hours fasting, 8-hour eating window',
    meals: '2-3 meals/day',
    timing: '12 PM - 8 PM',
    tone: 'text-emerald-600 bg-emerald-50',
  },
  {
    value: 'if_18_6',
    icon: Moon,
    title: 'Intermittent fasting 18:6',
    description: 'Longer fasting with tighter feeding window',
    meals: '2 meals/day',
    timing: '2 PM - 8 PM',
    tone: 'text-violet-600 bg-violet-50',
  },
  {
    value: 'omad',
    icon: Sun,
    title: 'One meal a day',
    description: 'Single consolidated meal in a chosen window',
    meals: '1 meal/day',
    timing: 'Flexible',
    tone: 'text-orange-600 bg-orange-50',
  },
  {
    value: 'bodybuilder',
    icon: Dumbbell,
    title: 'Bodybuilder split',
    description: 'Frequent meals for high training recovery',
    meals: '5-6 meals/day',
    timing: 'Every 2-3 hours',
    tone: 'text-rose-600 bg-rose-50',
  },
];

export default function PathSelectionPage() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showTransition, setShowTransition] = useState(false);
  const [requestReady, setRequestReady] = useState(false);
  const [nextStep, setNextStep] = useState<string | null>(null);
  const [firstName, setFirstName] = useState('');

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      path_type: 'traditional',
    },
  });

  useEffect(() => {
    setFirstName(getOnboardingFirstName());
  }, []);

  const onSubmit = async (values: FormValues) => {
    setIsSubmitting(true);
    setRequestReady(false);
    setNextStep(null);

    const openTimer = window.setTimeout(() => {
      setShowTransition(true);
    }, 300);

    try {
      const response = (await onboardingAPI.submitPath(values)) as PathSelectionResponse;
      setNextStep(response.next_step);
      setRequestReady(true);
    } catch (error: unknown) {
      window.clearTimeout(openTimer);
      setShowTransition(false);
      setIsSubmitting(false);
      setRequestReady(false);
      toast.error(getErrorMessage(error, 'Failed to save path'));
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
        <h2 className="text-2xl font-semibold tracking-[-0.015em] text-slate-900">Choose your eating pattern</h2>
        <p className="text-sm leading-6 text-slate-600">Pick what fits your lifestyle.</p>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="mt-7 space-y-6">
          <FormField
            control={form.control}
            name="path_type"
            render={({ field }) => (
              <FormItem>
                <FormControl>
                  <RadioGroup onValueChange={field.onChange} value={field.value} className="space-y-4">
                    {pathOptions.map((path) => {
                      const Icon = path.icon;
                      const isSelected = field.value === path.value;

                      return (
                        <div key={path.value}>
                          <RadioGroupItem value={path.value} id={path.value} className="sr-only" />
                          <Label
                            htmlFor={path.value}
                            className={cn(
                              'flex min-h-[146px] cursor-pointer items-start gap-4 rounded-[18px] border p-5 transition-[transform,box-shadow,border-color,background-color] duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]',
                              isSelected
                                ? 'border-emerald-400/80 bg-emerald-50/65 shadow-[0_16px_34px_-24px_rgba(16,185,129,0.62)]'
                                : 'border-slate-200 bg-white hover:-translate-y-[1px] hover:border-slate-300 hover:shadow-[0_14px_30px_-24px_rgba(15,23,42,0.3)]'
                            )}
                          >
                            <div
                              className={cn(
                                'mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px] transition-transform duration-300',
                                path.tone,
                                isSelected ? 'scale-105' : 'scale-100'
                              )}
                            >
                              <Icon className="h-5 w-5" />
                            </div>
                            <div className="space-y-2">
                              <p className="text-base font-semibold text-slate-900">{path.title}</p>
                              <p className="text-sm leading-6 text-slate-600">{path.description}</p>
                              <div className="inline-flex items-center gap-2 rounded-full border border-slate-200/85 bg-white/80 px-3 py-1 text-xs text-slate-500">
                                <span className="font-medium text-slate-700">{path.meals}</span>
                                <span>&bull;</span>
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
        title="Designing your daily rhythm..."
        description="Mapping your preferred pattern into a routine that stays practical."
        checkpoints={[
          'Validating feeding windows',
          'Matching meal cadence',
          'Syncing daily structure',
        ]}
        completionTitle={firstName ? `That fits your routine well, ${firstName}.` : 'That fits your routine well.'}
        completionDescription="Now we will fine-tune your preferences."
        onComplete={() => {
          if (nextStep) router.push(nextStep);
        }}
      />
    </div>
  );
}
