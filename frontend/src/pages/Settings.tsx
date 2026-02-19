import { Link } from "react-router-dom";
import { ArrowLeft, Trash2 } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { deleteAccount } from "../lib/api";

export function Settings() {
  const deleteMutation = useMutation({
    mutationFn: deleteAccount,
    onSuccess: () => {
      window.location.href = "/";
    },
  });

  const handleDelete = () => {
    const confirmed = confirm(
      "This will permanently delete your account and all application data, and revoke Gmail access. Are you sure?"
    );
    if (confirmed) deleteMutation.mutate();
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-3">
        <Link
          to="/dashboard"
          className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Dashboard
        </Link>
      </header>

      <div className="max-w-2xl mx-auto px-6 py-10 space-y-8">
        <h1 className="text-xl font-bold text-gray-900">Settings</h1>

        {/* Danger zone */}
        <div className="bg-white rounded-xl border border-red-200 p-6">
          <h2 className="text-sm font-semibold text-red-700 mb-1">Danger Zone</h2>
          <p className="text-sm text-gray-500 mb-4">
            Permanently delete your account, all tracked applications, and revoke
            HireTrace's access to your Gmail.
          </p>
          <button
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
            className="flex items-center gap-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg px-4 py-2 transition-colors disabled:opacity-60"
          >
            <Trash2 className="w-4 h-4" />
            {deleteMutation.isPending ? "Deleting…" : "Delete My Account"}
          </button>
        </div>
      </div>
    </div>
  );
}
