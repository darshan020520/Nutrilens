'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
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
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/hooks/useAuth';
import { authAPI } from '@/lib/api';

const formSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(1, 'Password is required'),
});

type FormValues = z.infer<typeof formSchema>;
type ApiErrorLike = {
  response?: {
    status?: number;
    data?: {
      detail?: string;
    };
  };
};

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [isResending, setIsResending] = useState(false);
  const [serverError, setServerError] = useState('');
  const [unverifiedEmail, setUnverifiedEmail] = useState('');

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  useEffect(() => {
    const email = searchParams.get('email');
    const verifyPending = searchParams.get('verify_pending');
    if (email) {
      form.setValue('email', email);
      setUnverifiedEmail(email);
    }
    if (verifyPending === '1') {
      toast.info('Please verify your email before logging in.');
    }
  }, [form, searchParams]);

  const onSubmit = async (values: FormValues) => {
    setServerError('');
    setIsLoading(true);
    try {
      const onboardingStatus = await login(values.email, values.password);
      const nextPath = searchParams.get("next");
      const safeNext =
        typeof nextPath === "string" && nextPath.startsWith("/dashboard")
          ? nextPath
          : null;
      
      toast.success('Welcome back!');
      
      // Redirect based on onboarding status
      const destination =
        onboardingStatus.redirect_to === "/dashboard" && safeNext
          ? safeNext
          : onboardingStatus.redirect_to;
      router.push(destination);
    } catch (error: unknown) {
      const apiError = error as ApiErrorLike;
      const detail = apiError?.response?.data?.detail;
      const message = typeof detail === 'string' ? detail : 'Login failed';

      if (apiError?.response?.status === 403 && /not verified/i.test(message)) {
        form.setError('email', { type: 'server', message: 'Email is not verified' });
        setUnverifiedEmail(values.email);
        setServerError(message);
      } else if (apiError?.response?.status === 400 && /invalid email format/i.test(message)) {
        form.setError('email', { type: 'server', message: 'Invalid email address' });
        setServerError(message);
      } else {
        setServerError(message);
        toast.error(message);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendVerification = async () => {
    if (!unverifiedEmail) {
      return;
    }

    setIsResending(true);
    try {
      await authAPI.resendVerification(unverifiedEmail);
      toast.success('Verification email sent. Please check your inbox.');
    } catch (error: unknown) {
      const detail = (error as ApiErrorLike)?.response?.data?.detail;
      const message = typeof detail === 'string' ? detail : 'Failed to resend verification email';
      toast.error(message);
    } finally {
      setIsResending(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-green-50 to-blue-50 p-4">
      <div className="w-full max-w-md">
        {/* Card */}
        <div className="bg-white rounded-2xl shadow-xl p-8 space-y-6">
          {/* Logo */}
          <div className="flex justify-center">
            <div className="w-16 h-16 bg-gradient-to-br from-green-500 to-blue-500 rounded-xl flex items-center justify-center text-white text-2xl font-bold">
              NL
            </div>
          </div>

          {/* Title */}
          <div className="text-center space-y-2">
            <h1 className="text-3xl font-bold text-gray-900">Welcome Back</h1>
            <p className="text-gray-600">Login to continue your journey</p>
          </div>

          {/* Form */}
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Email</FormLabel>
                    <FormControl>
                      <Input
                        type="email"
                        placeholder="you@example.com"
                        {...field}
                        disabled={isLoading}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Password</FormLabel>
                    <FormControl>
                      <Input
                        type="password"
                        placeholder="********"
                        {...field}
                        disabled={isLoading}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {serverError ? (
                <p className="text-sm text-red-600">{serverError}</p>
              ) : null}

              {unverifiedEmail && /not verified/i.test(serverError) ? (
                <Button
                  type="button"
                  variant="outline"
                  className="w-full"
                  onClick={handleResendVerification}
                  disabled={isResending}
                >
                  {isResending ? 'Sending verification...' : 'Resend Verification Email'}
                </Button>
              ) : null}

              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Logging in...
                  </>
                ) : (
                  'Login'
                )}
              </Button>
            </form>
          </Form>

          {/* Footer */}
          <div className="text-center text-sm text-gray-600">
            Don&apos;t have an account?{' '}
            <Link href="/register" className="text-green-600 hover:text-green-700 font-medium">
              Sign up
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

function LoginPageFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-green-50 to-blue-50 p-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-xl p-8 text-center">
          <p className="text-gray-600">Loading login...</p>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginPageFallback />}>
      <LoginPageContent />
    </Suspense>
  );
}
