'use client';

import { usePathname } from 'next/navigation';
import { Check } from 'lucide-react';

const steps = [
  { number: 1, name: 'Basic Info', path: '/onboarding/basic-info' },
  { number: 2, name: 'Goals', path: '/onboarding/goal-selection' },
  { number: 3, name: 'Eating Path', path: '/onboarding/path-selection' },
  { number: 4, name: 'Preferences', path: '/onboarding/preferences' },
];

export default function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  
  const currentStepIndex = steps.findIndex(step => pathname.includes(step.path));
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 to-blue-50">
      {/* Header */}
      <div className="bg-white border-b">
        <div className="max-w-4xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-green-500 to-blue-500 rounded-lg flex items-center justify-center text-white text-lg font-bold">
                NL
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">Profile Setup</h1>
                <p className="text-sm text-gray-600">Let's personalize your experience</p>
              </div>
            </div>
          </div>

          {/* Progress Stepper */}
          <div className="flex items-center justify-between">
            {steps.map((step, index) => {
              const isCompleted = index < currentStepIndex;
              const isCurrent = index === currentStepIndex;
              
              return (
                <div key={step.number} className="flex items-center flex-1">
                  {/* Step Circle */}
                  <div className="flex flex-col items-center">
                    <div
                      className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold transition-colors ${
                        isCompleted
                          ? 'bg-green-500 text-white'
                          : isCurrent
                          ? 'bg-blue-500 text-white'
                          : 'bg-gray-200 text-gray-500'
                      }`}
                    >
                      {isCompleted ? <Check className="w-5 h-5" /> : step.number}
                    </div>
                    <p
                      className={`mt-2 text-xs font-medium ${
                        isCurrent ? 'text-blue-600' : isCompleted ? 'text-green-600' : 'text-gray-500'
                      }`}
                    >
                      {step.name}
                    </p>
                  </div>

                  {/* Connector Line */}
                  {index < steps.length - 1 && (
                    <div
                      className={`h-1 flex-1 mx-2 rounded transition-colors ${
                        index < currentStepIndex ? 'bg-green-500' : 'bg-gray-200'
                      }`}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-2xl mx-auto px-4 py-8">
        {children}
      </div>
    </div>
  );
}