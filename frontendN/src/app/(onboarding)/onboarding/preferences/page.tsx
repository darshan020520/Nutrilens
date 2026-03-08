'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Beef, Check, Fish, Leaf, Loader2, Salad } from 'lucide-react';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { onboardingAPI } from '@/lib/api';
import StepTransitionOverlay from '../components/StepTransitionOverlay';
import { getOnboardingFirstName } from '../components/onboardingSession';

const formSchema = z.object({
  dietary_type: z.enum(['vegetarian', 'non_vegetarian', 'vegan', 'pescatarian']),
  allergies: z.array(z.string()).optional(),
  cuisine_preferences: z.array(z.string()).min(1, 'Select at least one cuisine'),
  max_prep_time_weekday: z.number().min(10).max(120),
  max_prep_time_weekend: z.number().min(10).max(180),
});

type FormValues = z.infer<typeof formSchema>;

type CalculatedTargetsResponse = {
  bmr: number;
  tdee: number;
  goal_calories: number;
  macro_targets: {
    protein_g: number;
    carbs_g: number;
    fat_g: number;
  };
  meals_per_day: number;
};

type TargetDraft = {
  goal_calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
};

type PreferencesResponse = {
  redirect_to: string;
};

function getErrorMessage(error: unknown, fallback: string): string {
  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof (error as { response?: { data?: { detail?: { message?: string } | string } } }).response?.data?.detail ===
      'string'
  ) {
    return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail as string;
  }

  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof (error as { response?: { data?: { detail?: { message?: string } } } }).response?.data?.detail?.message ===
      'string'
  ) {
    return (error as { response?: { data?: { detail?: { message?: string } } } }).response?.data?.detail?.message as string;
  }

  return fallback;
}

function useAnimatedValue(target: number, triggerKey: number, delayMs: number): number {
  const [value, setValue] = useState(target);
  const previousTriggerRef = useRef(triggerKey);

  useEffect(() => {
    if (triggerKey === previousTriggerRef.current) {
      setValue(target);
      return;
    }

    previousTriggerRef.current = triggerKey;
    let frameId: number | null = null;
    let delayTimer: number | null = null;
    const startValue = 0;
    const duration = 800;

    delayTimer = window.setTimeout(() => {
      const startTime = performance.now();
      const animate = (now: number) => {
        const progress = Math.min((now - startTime) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const next = startValue + (target - startValue) * eased;
        setValue(Math.round(next));
        if (progress < 1) {
          frameId = window.requestAnimationFrame(animate);
        }
      };
      frameId = window.requestAnimationFrame(animate);
    }, delayMs);

    return () => {
      if (delayTimer) window.clearTimeout(delayTimer);
      if (frameId) window.cancelAnimationFrame(frameId);
    };
  }, [delayMs, target, triggerKey]);

  return value;
}

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
  const DASHBOARD_WELCOME_KEY = 'nutrilens:onboarding:dashboard-welcome';
  const router = useRouter();
  const [firstName, setFirstName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showProcessing, setShowProcessing] = useState(false);
  const [targetsReady, setTargetsReady] = useState(false);
  const [showReveal, setShowReveal] = useState(false);
  const [showCards, setShowCards] = useState(false);
  const [counterTrigger, setCounterTrigger] = useState(0);
  const [pendingPreferences, setPendingPreferences] = useState<FormValues | null>(null);
  const [targetDraft, setTargetDraft] = useState<TargetDraft | null>(null);
  const [isLocking, setIsLocking] = useState(false);
  const [lockButtonSuccess, setLockButtonSuccess] = useState(false);
  const [showCompletionPanel, setShowCompletionPanel] = useState(false);
  const [completionVisibleCount, setCompletionVisibleCount] = useState(0);
  const [isExitingToDashboard, setIsExitingToDashboard] = useState(false);
  const transitionTimersRef = useRef<number[]>([]);

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

  useEffect(() => {
    setFirstName(getOnboardingFirstName());
  }, []);

  useEffect(() => {
    return () => {
      transitionTimersRef.current.forEach((timerId) => window.clearTimeout(timerId));
      transitionTimersRef.current = [];
    };
  }, []);

  useEffect(() => {
    if (!showCompletionPanel) {
      setCompletionVisibleCount(0);
      return;
    }

    setCompletionVisibleCount(0);
    let visible = 0;
    const intervalId = window.setInterval(() => {
      visible += 1;
      setCompletionVisibleCount(Math.min(3, visible));
      if (visible >= 3) {
        window.clearInterval(intervalId);
      }
    }, 150);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [showCompletionPanel]);

  const onSubmit = async (values: FormValues) => {
    setIsSubmitting(true);
    setTargetsReady(false);
    setPendingPreferences(values);
    setShowReveal(false);
    setShowCards(false);
    setLockButtonSuccess(false);
    setShowCompletionPanel(false);
    setCompletionVisibleCount(0);
    setIsExitingToDashboard(false);

    const openTimer = window.setTimeout(() => {
      setShowProcessing(true);
    }, 300);

    try {
      const targets = (await onboardingAPI.getCalculatedTargets()) as CalculatedTargetsResponse;
      setTargetDraft({
        goal_calories: Math.round(targets.goal_calories),
        protein_g: Math.round(targets.macro_targets.protein_g),
        carbs_g: Math.round(targets.macro_targets.carbs_g),
        fat_g: Math.round(targets.macro_targets.fat_g),
      });
      setTargetsReady(true);
    } catch (error: unknown) {
      window.clearTimeout(openTimer);
      setShowProcessing(false);
      setIsSubmitting(false);
      toast.error(getErrorMessage(error, 'Failed to generate personalized targets'));
    }
  };

  const caloriesAnimated = useAnimatedValue(targetDraft?.goal_calories ?? 0, counterTrigger, 0);
  const proteinAnimated = useAnimatedValue(targetDraft?.protein_g ?? 0, counterTrigger, 150);
  const carbsAnimated = useAnimatedValue(targetDraft?.carbs_g ?? 0, counterTrigger, 300);
  const fatAnimated = useAnimatedValue(targetDraft?.fat_g ?? 0, counterTrigger, 450);

  const handleDraftChange = (field: keyof TargetDraft, value: number) => {
    if (!targetDraft) return;
    setTargetDraft({
      ...targetDraft,
      [field]: Number.isFinite(value) ? Math.max(0, Math.round(value)) : 0,
    });
  };

  const handleFinalize = async () => {
    if (!pendingPreferences || !targetDraft) return;

    setIsLocking(true);
    try {
      await onboardingAPI.lockTargets(targetDraft);
      const response = (await onboardingAPI.submitPreferences({
        ...pendingPreferences,
        disliked_ingredients: [],
      })) as PreferencesResponse;

      if (typeof window !== 'undefined') {
        window.sessionStorage.setItem(
          DASHBOARD_WELCOME_KEY,
          JSON.stringify({
            firstName: firstName.trim(),
            calories: targetDraft.goal_calories,
            source: 'onboarding-complete',
            timestamp: Date.now(),
          })
        );
      }

      setLockButtonSuccess(true);
      setIsLocking(false);

      transitionTimersRef.current.forEach((timerId) => window.clearTimeout(timerId));
      transitionTimersRef.current = [];

      const phaseOneTimer = window.setTimeout(() => {
        setShowCompletionPanel(true);

        const bridgeTransitionTimer = window.setTimeout(() => {
          setIsExitingToDashboard(true);
          const routeTimer = window.setTimeout(() => {
            router.push(response.redirect_to);
          }, 350);
          transitionTimersRef.current.push(routeTimer);
        }, 1100);

        transitionTimersRef.current.push(bridgeTransitionTimer);
      }, 300);
      transitionTimersRef.current.push(phaseOneTimer);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, 'Failed to complete onboarding'));
      setLockButtonSuccess(false);
      setShowCompletionPanel(false);
      setIsExitingToDashboard(false);
      setIsLocking(false);
    }
  };

  return (
    <div
      className={cn(
        'transition-[opacity,transform] duration-[350ms] ease-[cubic-bezier(0.4,0,0.2,1)]',
        isExitingToDashboard ? 'scale-[0.98] opacity-0' : 'scale-100 opacity-100'
      )}
    >
      <div
        className={cn(
          'relative overflow-hidden rounded-[18px] border border-white/75 bg-white/92 p-7 shadow-[0_24px_60px_-42px_rgba(15,23,42,0.45)] transition-[transform,opacity] duration-400 md:p-8',
          showProcessing ? 'scale-[0.98] opacity-85' : 'scale-100 opacity-100'
        )}
      >
        <div className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500" />

        {showReveal && targetDraft ? (
          <div className="space-y-6">
            <div className="space-y-2">
              <h2 className="text-2xl font-semibold tracking-[-0.015em] text-slate-900">
                {firstName ? `${firstName}, your plan is ready.` : 'Your plan is ready.'}
              </h2>
              <p className="text-sm leading-6 text-slate-600">Here&apos;s your personalized starting point.</p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div
                className={cn(
                  'rounded-[18px] border border-emerald-200/80 bg-emerald-50/70 p-4 transition-[opacity,transform] duration-400',
                  showCards ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0'
                )}
              >
                <p className="text-xs font-medium uppercase tracking-[0.1em] text-emerald-700/80">Calories</p>
                <p className="mt-1 text-3xl font-semibold text-emerald-900">{caloriesAnimated}</p>
                <p className="text-xs text-emerald-700/80">per day</p>
              </div>

              <div
                className={cn(
                  'rounded-[18px] border border-slate-200 bg-white p-4 transition-[opacity,transform] duration-400 delay-150',
                  showCards ? 'translate-x-0 opacity-100' : '-translate-x-4 opacity-0'
                )}
              >
                <p className="text-xs font-medium uppercase tracking-[0.1em] text-slate-500">Protein</p>
                <p className="mt-1 text-2xl font-semibold text-slate-900">{proteinAnimated}g</p>
              </div>

              <div
                className={cn(
                  'rounded-[18px] border border-slate-200 bg-white p-4 transition-[opacity,transform] duration-400 delay-300',
                  showCards ? 'translate-x-0 opacity-100' : 'translate-x-4 opacity-0'
                )}
              >
                <p className="text-xs font-medium uppercase tracking-[0.1em] text-slate-500">Carbs</p>
                <p className="mt-1 text-2xl font-semibold text-slate-900">{carbsAnimated}g</p>
              </div>

              <div
                className={cn(
                  'rounded-[18px] border border-slate-200 bg-white p-4 transition-opacity duration-400 delay-500',
                  showCards ? 'opacity-100' : 'opacity-0'
                )}
              >
                <p className="text-xs font-medium uppercase tracking-[0.1em] text-slate-500">Fat</p>
                <p className="mt-1 text-2xl font-semibold text-slate-900">{fatAnimated}g</p>
              </div>
            </div>

            <div className="rounded-[18px] border border-slate-200 bg-white/85 p-5">
              <p className="text-sm text-slate-600">You can fine-tune these before locking them in.</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <div>
                  <Label className="text-xs font-medium uppercase tracking-[0.1em] text-slate-500">Calories</Label>
                  <Input
                    type="number"
                    value={targetDraft.goal_calories}
                    onChange={(event) => handleDraftChange('goal_calories', event.target.valueAsNumber)}
                    className="mt-1 h-11 rounded-[14px] border-slate-200"
                  />
                </div>
                <div>
                  <Label className="text-xs font-medium uppercase tracking-[0.1em] text-slate-500">Protein (g)</Label>
                  <Input
                    type="number"
                    value={targetDraft.protein_g}
                    onChange={(event) => handleDraftChange('protein_g', event.target.valueAsNumber)}
                    className="mt-1 h-11 rounded-[14px] border-slate-200"
                  />
                </div>
                <div>
                  <Label className="text-xs font-medium uppercase tracking-[0.1em] text-slate-500">Carbs (g)</Label>
                  <Input
                    type="number"
                    value={targetDraft.carbs_g}
                    onChange={(event) => handleDraftChange('carbs_g', event.target.valueAsNumber)}
                    className="mt-1 h-11 rounded-[14px] border-slate-200"
                  />
                </div>
                <div>
                  <Label className="text-xs font-medium uppercase tracking-[0.1em] text-slate-500">Fat (g)</Label>
                  <Input
                    type="number"
                    value={targetDraft.fat_g}
                    onChange={(event) => handleDraftChange('fat_g', event.target.valueAsNumber)}
                    className="mt-1 h-11 rounded-[14px] border-slate-200"
                  />
                </div>
              </div>

              <div className="mt-5 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
                <Button
                  type="button"
                  variant="outline"
                  disabled={isLocking}
                  onClick={() => {
                    setShowReveal(false);
                    setShowCards(false);
                    setIsSubmitting(false);
                  }}
                  className="h-11 rounded-[14px] border-slate-200 px-5"
                >
                  Back to preferences
                </Button>
                <Button
                  type="button"
                  disabled={isLocking}
                  onClick={handleFinalize}
                  className={cn(
                    'relative h-11 min-w-[188px] overflow-hidden rounded-[14px] bg-gradient-to-r from-emerald-600 to-teal-600 px-5 text-white transition-all duration-300 hover:scale-[1.03] hover:shadow-[0_16px_30px_-18px_rgba(5,150,105,0.75)]',
                    lockButtonSuccess
                      ? 'from-emerald-500 to-teal-500 shadow-[0_0_0_8px_rgba(16,185,129,0.14)]'
                      : ''
                  )}
                >
                  <span
                    className={cn(
                      'absolute inset-0 flex items-center justify-center gap-2 transition-opacity duration-200',
                      !isLocking && !lockButtonSuccess ? 'opacity-100' : 'opacity-0'
                    )}
                  >
                    Lock in my targets
                  </span>
                  <span
                    className={cn(
                      'absolute inset-0 flex items-center justify-center gap-2 transition-opacity duration-200',
                      isLocking ? 'opacity-100' : 'opacity-0'
                    )}
                  >
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Locking...
                  </span>
                  <span
                    className={cn(
                      'absolute inset-0 flex items-center justify-center gap-2 transition-[opacity,transform] duration-300',
                      lockButtonSuccess ? 'scale-100 opacity-100' : 'scale-[0.8] opacity-0'
                    )}
                  >
                    <Check className="h-4 w-4" />
                    Targets locked
                  </span>
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="space-y-2">
              <h2 className="text-2xl font-semibold tracking-[-0.015em] text-slate-900">Final step: Your preferences</h2>
              <p className="text-sm leading-6 text-slate-600">Help us fine-tune your nutrition plan.</p>
            </div>

            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="mt-7 space-y-6">
                <div className="space-y-4 rounded-[18px] border border-slate-200 bg-white/85 p-5">
                  <FormField
                    control={form.control}
                    name="dietary_type"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs font-medium uppercase tracking-[0.1em] text-slate-500">
                          Dietary preference
                        </FormLabel>
                        <Select onValueChange={field.onChange} value={field.value} disabled={isSubmitting}>
                          <FormControl>
                            <SelectTrigger className="h-12 w-full rounded-[16px] border-slate-200 bg-white/90">
                              <SelectValue placeholder="Select dietary type" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent className="rounded-[14px] border-slate-200 bg-white/96">
                            <SelectItem value="non_vegetarian">
                              <div className="flex items-center gap-2">
                                <Beef className="h-4 w-4" />
                                Non-vegetarian
                              </div>
                            </SelectItem>
                            <SelectItem value="vegetarian">
                              <div className="flex items-center gap-2">
                                <Salad className="h-4 w-4" />
                                Vegetarian
                              </div>
                            </SelectItem>
                            <SelectItem value="vegan">
                              <div className="flex items-center gap-2">
                                <Leaf className="h-4 w-4" />
                                Vegan
                              </div>
                            </SelectItem>
                            <SelectItem value="pescatarian">
                              <div className="flex items-center gap-2">
                                <Fish className="h-4 w-4" />
                                Pescatarian
                              </div>
                            </SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="allergies"
                    render={() => (
                      <FormItem>
                        <FormLabel className="text-xs font-medium uppercase tracking-[0.1em] text-slate-500">
                          Allergies (optional)
                        </FormLabel>
                        <div className="mt-2 grid gap-2 sm:grid-cols-2">
                          {allergyOptions.map((allergy) => (
                            <FormField
                              key={allergy.value}
                              control={form.control}
                              name="allergies"
                              render={({ field }) => (
                                <FormItem className="flex items-center gap-2 rounded-[12px] border border-slate-200/80 bg-white/80 px-3 py-2.5">
                                  <FormControl>
                                    <Checkbox
                                      checked={field.value?.includes(allergy.value)}
                                      onCheckedChange={(checked) => {
                                        const current = field.value ?? [];
                                        const next = checked
                                          ? [...current, allergy.value]
                                          : current.filter((value) => value !== allergy.value);
                                        field.onChange(next);
                                      }}
                                    />
                                  </FormControl>
                                  <FormLabel className="cursor-pointer font-normal text-slate-700">{allergy.label}</FormLabel>
                                </FormItem>
                              )}
                            />
                          ))}
                        </div>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <div className="space-y-4 rounded-[18px] border border-slate-200 bg-white/85 p-5">
                  <FormField
                    control={form.control}
                    name="cuisine_preferences"
                    render={() => (
                      <FormItem>
                        <FormLabel className="text-xs font-medium uppercase tracking-[0.1em] text-slate-500">
                          Favorite cuisines
                        </FormLabel>
                        <div className="mt-2 grid gap-2 sm:grid-cols-2">
                          {cuisineOptions.map((cuisine) => (
                            <FormField
                              key={cuisine.value}
                              control={form.control}
                              name="cuisine_preferences"
                              render={({ field }) => (
                                <FormItem className="flex items-center gap-2 rounded-[12px] border border-slate-200/80 bg-white/80 px-3 py-2.5">
                                  <FormControl>
                                    <Checkbox
                                      checked={field.value?.includes(cuisine.value)}
                                      onCheckedChange={(checked) => {
                                        const current = field.value ?? [];
                                        const next = checked
                                          ? [...current, cuisine.value]
                                          : current.filter((value) => value !== cuisine.value);
                                        field.onChange(next);
                                      }}
                                    />
                                  </FormControl>
                                  <FormLabel className="cursor-pointer font-normal text-slate-700">{cuisine.label}</FormLabel>
                                </FormItem>
                              )}
                            />
                          ))}
                        </div>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <div className="grid gap-4 sm:grid-cols-2">
                    <FormField
                      control={form.control}
                      name="max_prep_time_weekday"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="text-xs font-medium uppercase tracking-[0.1em] text-slate-500">
                            Weekday prep time (min)
                          </FormLabel>
                          <FormControl>
                            <Input
                              type="number"
                              value={field.value}
                              onChange={(event) => field.onChange(event.target.valueAsNumber)}
                              disabled={isSubmitting}
                              className="h-12 rounded-[14px] border-slate-200"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="max_prep_time_weekend"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="text-xs font-medium uppercase tracking-[0.1em] text-slate-500">
                            Weekend prep time (min)
                          </FormLabel>
                          <FormControl>
                            <Input
                              type="number"
                              value={field.value}
                              onChange={(event) => field.onChange(event.target.valueAsNumber)}
                              disabled={isSubmitting}
                              className="h-12 rounded-[14px] border-slate-200"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                </div>

                <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => router.back()}
                    disabled={isSubmitting}
                    className="h-12 rounded-[16px] border-slate-200 px-6"
                  >
                    Back
                  </Button>

                  <Button
                    type="submit"
                    size="lg"
                    disabled={isSubmitting}
                    className="relative h-12 w-full overflow-hidden rounded-[16px] bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-[0_16px_30px_-20px_rgba(5,150,105,0.7)] transition-all duration-200 hover:from-emerald-500 hover:to-teal-500 hover:shadow-[0_20px_34px_-20px_rgba(5,150,105,0.82)] sm:w-[286px]"
                  >
                    <span className={cn('transition-opacity duration-200', isSubmitting ? 'opacity-0' : 'opacity-100')}>
                      Generate my personalized targets
                    </span>
                    <span
                      className={cn(
                        'pointer-events-none absolute inset-0 flex items-center justify-center gap-2 transition-opacity duration-200',
                        isSubmitting ? 'opacity-100' : 'opacity-0'
                      )}
                    >
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Processing...
                    </span>
                  </Button>
                </div>
              </form>
            </Form>
          </>
        )}
      </div>

      <StepTransitionOverlay
        open={showProcessing}
        ready={targetsReady}
        title="Creating your personalized nutrition blueprint..."
        description="Analyzing your goals, lifestyle, and preferences."
        checkpoints={[
          'Understanding your profile',
          'Balancing calories intelligently',
          'Optimizing macro distribution',
          'Applying safety safeguards',
        ]}
        completionTitle={firstName ? `${firstName}, your plan is ready.` : 'Your plan is ready.'}
        completionDescription="Here's your personalized starting point."
        onComplete={() => {
          setShowProcessing(false);
          setShowReveal(true);
          setIsSubmitting(false);
          setCounterTrigger((previous) => previous + 1);
          window.requestAnimationFrame(() => {
            setShowCards(true);
          });
        }}
      />

      <div
        className={cn(
          'fixed inset-0 z-[95] flex items-center justify-center bg-slate-950/15 px-6 backdrop-blur-[2px] transition-opacity duration-300',
          showCompletionPanel ? (isExitingToDashboard ? 'opacity-0' : 'opacity-100') : 'pointer-events-none opacity-0'
        )}
      >
        <div className="pointer-events-none absolute h-64 w-64 rounded-full bg-emerald-300/20 blur-3xl" />
        <div className="relative w-full max-w-md rounded-[18px] border border-white/75 bg-white/95 p-6 shadow-[0_30px_60px_-35px_rgba(15,23,42,0.45)]">
          <div className="relative mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
            {showCompletionPanel ? (
              <span
                className="pointer-events-none absolute inset-0 rounded-full border border-emerald-300/70"
                style={{ animation: 'ping 700ms cubic-bezier(0, 0, 0.2, 1) 1' }}
              />
            ) : null}
            <Check className="h-6 w-6" />
          </div>

          <h3 className="text-center text-2xl font-semibold tracking-[-0.015em] text-slate-900">
            {firstName ? `You're all set, ${firstName}.` : "You're all set."}
          </h3>
          <p className="mt-2 text-center text-sm text-slate-600">
            Your personalized nutrition plan is ready to go.
          </p>

          <div className="mt-5 space-y-2">
            {['Targets locked', 'Profile calibrated', 'Ready to start tracking'].map((line, index) => (
              <div
                key={line}
                className={cn(
                  'flex items-center gap-2 rounded-[12px] border border-slate-200/90 bg-white/90 px-3 py-2 text-sm text-slate-700 transition-[opacity,transform] duration-300',
                  completionVisibleCount > index ? 'translate-y-0 opacity-100' : 'translate-y-2.5 opacity-0'
                )}
              >
                <Check className="h-4 w-4 text-emerald-600" />
                <span>{line}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
