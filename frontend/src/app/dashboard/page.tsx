'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2, Home, UtensilsCrossed, Package, TrendingUp, Settings, LogOut } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/hooks/useAuth';

export default function DashboardPage() {
  const router = useRouter();
  const { user, logout, checkAuth } = useAuth();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Verify user is authenticated and onboarding is complete
    const verifyAccess = async () => {
      try {
        await checkAuth();
        setIsLoading(false);
      } catch (error) {
        router.push('/login');
      }
    };

    verifyAccess();
  }, []);

  const handleLogout = () => {
    logout();
    router.push('/');
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-green-500" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 to-blue-50">
      {/* Header */}
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-green-500 to-blue-500 rounded-lg flex items-center justify-center text-white text-lg font-bold">
              NL
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">NutriLens AI</h1>
              <p className="text-sm text-gray-600">Welcome back, {user?.email}!</p>
            </div>
          </div>
          <Button variant="outline" onClick={handleLogout}>
            <LogOut className="w-4 h-4 mr-2" />
            Logout
          </Button>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Success Message */}
        <div className="bg-white rounded-2xl shadow-lg p-8 mb-8 text-center">
          <div className="w-20 h-20 bg-gradient-to-br from-green-500 to-blue-500 rounded-full flex items-center justify-center text-white text-4xl mx-auto mb-4">
            🎉
          </div>
          <h2 className="text-3xl font-bold text-gray-900 mb-2">
            Profile Setup Complete!
          </h2>
          <p className="text-lg text-gray-600 mb-6">
            Your personalized nutrition journey starts now
          </p>
          <div className="inline-flex items-center gap-2 bg-green-100 text-green-800 px-4 py-2 rounded-full">
            <span className="font-semibold">Onboarding Status:</span>
            <span className="text-green-600">✓ Completed</span>
          </div>
        </div>

        {/* Coming Soon Cards */}
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="bg-white rounded-xl shadow-sm p-6 text-center">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-3">
              <Home className="w-6 h-6 text-blue-600" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-1">Home Dashboard</h3>
            <p className="text-sm text-gray-600 mb-3">Overview of your nutrition journey</p>
            <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded">Coming Soon</span>
          </div>

          <div className="bg-white rounded-xl shadow-sm p-6 text-center">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mx-auto mb-3">
              <UtensilsCrossed className="w-6 h-6 text-green-600" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-1">Meal Dashboard</h3>
            <p className="text-sm text-gray-600 mb-3">Plan and track your meals</p>
            <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded">Coming Soon</span>
          </div>

          <div className="bg-white rounded-xl shadow-sm p-6 text-center">
            <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center mx-auto mb-3">
              <Package className="w-6 h-6 text-purple-600" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-1">Inventory</h3>
            <p className="text-sm text-gray-600 mb-3">Manage your pantry</p>
            <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded">Coming Soon</span>
          </div>

          <div className="bg-white rounded-xl shadow-sm p-6 text-center">
            <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center mx-auto mb-3">
              <TrendingUp className="w-6 h-6 text-orange-600" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-1">Progress</h3>
            <p className="text-sm text-gray-600 mb-3">Track your achievements</p>
            <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded">Coming Soon</span>
          </div>
        </div>

        {/* Info Box */}
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-6 mt-8">
          <h3 className="font-semibold text-blue-900 mb-2">🚀 What's Next?</h3>
          <p className="text-blue-800 mb-4">
            You've successfully completed the onboarding process! Your profile has been saved and your nutrition targets have been calculated.
          </p>
          <div className="grid md:grid-cols-2 gap-3 text-sm text-blue-800">
            <div>✓ BMR & TDEE calculated</div>
            <div>✓ Goal-based macro targets set</div>
            <div>✓ Eating pattern configured</div>
            <div>✓ Dietary preferences saved</div>
          </div>
        </div>
      </div>
    </div>
  );
}