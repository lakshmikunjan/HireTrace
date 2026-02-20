import { Mail, Zap, Shield } from "lucide-react";

export function Auth() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-900 to-brand-600 flex items-center justify-center px-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-10 text-center">
        <div className="w-14 h-14 bg-brand-600 rounded-2xl flex items-center justify-center mx-auto mb-6">
          <Zap className="w-7 h-7 text-white" />
        </div>

        <h1 className="text-2xl font-bold text-gray-900 mb-2">HireTrace</h1>
        <p className="text-gray-500 text-sm mb-8">
          Automatically track every job application from your Gmail inbox.
          No spreadsheets. No manual entry.
        </p>

        <a
          href="http://localhost:8000/auth/google"
          className="flex items-center justify-center gap-3 w-full bg-brand-600 hover:bg-brand-700 text-white font-medium rounded-lg px-5 py-3 transition-colors"
        >
          <Mail className="w-5 h-5" />
          Connect Gmail
        </a>

        <div className="mt-8 space-y-3 text-xs text-gray-400 text-left">
          <div className="flex items-start gap-2">
            <Shield className="w-4 h-4 shrink-0 mt-0.5 text-green-500" />
            <span>Read-only access — we never modify, send, or delete your emails.</span>
          </div>
          <div className="flex items-start gap-2">
            <Shield className="w-4 h-4 shrink-0 mt-0.5 text-green-500" />
            <span>We only scan emails matching job application keywords.</span>
          </div>
          <div className="flex items-start gap-2">
            <Shield className="w-4 h-4 shrink-0 mt-0.5 text-green-500" />
            <span>Delete your account anytime to wipe all data and revoke access.</span>
          </div>
        </div>
      </div>
    </div>
  );
}
