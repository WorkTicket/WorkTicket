import { ApiTokenSync } from "@/components/dashboard/api-token-sync";
import { RegistrationGate } from "@/components/dashboard/registration-gate";
import { Sidebar } from "@/components/dashboard/sidebar";
import { TopNav } from "@/components/dashboard/top-nav";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <RegistrationGate>
    <div className="flex h-screen overflow-hidden bg-background">
      <ApiTokenSync />
      <div className="hidden lg:block">
        <Sidebar />
      </div>
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <TopNav />
        <main id="main-content" className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          {children}
        </main>
      </div>
    </div>
    </RegistrationGate>
  );
}
