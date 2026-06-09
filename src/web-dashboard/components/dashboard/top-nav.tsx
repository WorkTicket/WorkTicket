"use client";

import { OrganizationSwitcher, UserButton } from "@clerk/nextjs";
import { Menu, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { useUiStore } from "@/stores/ui-store";
import { OnboardingBanner } from "./onboarding-banner";

export function TopNav() {
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const { theme, setTheme } = useTheme();

  return (
    <header className="flex flex-col border-b border-border bg-card">
      <div className="flex h-14 items-center justify-between gap-4 px-4">
        <div className="flex items-center gap-3">
          <Button
            variant="secondary"
            size="sm"
            className="lg:hidden"
            onClick={toggleSidebar}
            aria-label="Toggle sidebar"
          >
            <Menu className="h-4 w-4" />
          </Button>
          <OrganizationSwitcher
            hidePersonal
            appearance={{
              elements: {
                rootBox: "flex items-center",
                organizationSwitcherTrigger: "text-sm",
              },
            }}
          />
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label="Toggle theme"
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
          <UserButton afterSignOutUrl="/sign-in" />
        </div>
      </div>
      <OnboardingBanner />
    </header>
  );
}
