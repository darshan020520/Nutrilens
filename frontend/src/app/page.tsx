import Link from 'next/link';
import { Button } from '@/components/ui/button';

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-green-50 to-blue-50">
      <div className="max-w-2xl mx-auto text-center space-y-8 p-8">
        {/* Logo */}
        <div className="flex justify-center">
          <div className="w-20 h-20 bg-gradient-to-br from-green-500 to-blue-500 rounded-2xl flex items-center justify-center text-white text-3xl font-bold">
            NL
          </div>
        </div>

        {/* Title */}
        <div className="space-y-4">
          <h1 className="text-5xl font-bold text-gray-900">
            NutriLens AI
          </h1>
          <p className="text-xl text-gray-600">
            Your AI-powered nutrition coach for personalized meal planning and smart food tracking
          </p>
        </div>

        {/* Features */}
        <div className="grid md:grid-cols-3 gap-4 text-left">
          <div className="bg-white p-6 rounded-lg shadow-sm">
            <div className="text-2xl mb-2">🍽️</div>
            <h3 className="font-semibold mb-1">Smart Meal Plans</h3>
            <p className="text-sm text-gray-600">AI-generated weekly plans tailored to your goals</p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow-sm">
            <div className="text-2xl mb-2">📊</div>
            <h3 className="font-semibold mb-1">Track Progress</h3>
            <p className="text-sm text-gray-600">Real-time macro tracking and insights</p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow-sm">
            <div className="text-2xl mb-2">🤖</div>
            <h3 className="font-semibold mb-1">AI Coaching</h3>
            <p className="text-sm text-gray-600">Personalized recommendations that learn from you</p>
          </div>
        </div>

        {/* CTA Buttons */}
        <div className="flex gap-4 justify-center">
          <Link href="/register">
            <Button size="lg" className="text-lg px-8">
              Get Started Free
            </Button>
          </Link>
          <Link href="/login">
            <Button size="lg" variant="outline" className="text-lg px-8">
              Login
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}