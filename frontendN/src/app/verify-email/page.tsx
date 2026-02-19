'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';

import { authAPI } from '@/lib/api';
import { Button } from '@/components/ui/button';

export default function VerifyEmailPage() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('Verifying your email...');

  useEffect(() => {
    const token = searchParams.get('token');
    if (!token) {
      setStatus('error');
      setMessage('Invalid verification link.');
      return;
    }

    const run = async () => {
      try {
        const response = await authAPI.verifyEmail(token);
        setStatus('success');
        setMessage(response.message || 'Email verified successfully. You can now log in.');
      } catch (error: any) {
        const detail = error?.response?.data?.detail;
        setStatus('error');
        setMessage(typeof detail === 'string' ? detail : 'Email verification failed.');
      }
    };

    run();
  }, [searchParams]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-green-50 to-blue-50 p-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-8 space-y-6 text-center">
        <div className="flex justify-center">
          <div className="w-16 h-16 bg-gradient-to-br from-green-500 to-blue-500 rounded-xl flex items-center justify-center text-white text-2xl font-bold">
            NL
          </div>
        </div>

        <div className="space-y-2">
          <h1 className="text-2xl font-bold text-gray-900">
            {status === 'loading' ? 'Verifying Email' : status === 'success' ? 'Email Verified' : 'Verification Failed'}
          </h1>
          <p className={status === 'error' ? 'text-red-600' : 'text-gray-600'}>{message}</p>
        </div>

        <Button asChild className="w-full" disabled={status === 'loading'}>
          <Link href="/login">Go to Login</Link>
        </Button>
      </div>
    </div>
  );
}

