import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppLayout } from "@/components/AppLayout";
import { LoginRoute, RequireAuth, RequireProfile } from "@/pages/LoginRoute";
import { OnboardingPage } from "@/pages/OnboardingPage";
import { TodayPage } from "@/pages/TodayPage";
import { PlansPage } from "@/pages/PlansPage";
import { PlanDetailPage } from "@/pages/PlanDetailPage";
import { ReviewsPage } from "@/pages/ReviewsPage";
import { MemoriesPage } from "@/pages/MemoriesPage";
import { DeveloperRunsPage } from "@/pages/DeveloperRunsPage";
import { MyPage } from "@/pages/MyPage";
import { ProfileSettingsPage } from "@/pages/ProfileSettingsPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginRoute /> },
  {
    element: <RequireAuth />,
    children: [
      { path: "/onboarding", element: <OnboardingPage /> },
      {
        element: <RequireProfile />,
        children: [
          {
            element: <AppLayout />,
            children: [
              { path: "/today", element: <TodayPage /> },
              { path: "/journey", element: <PlansPage /> },
              { path: "/journey/:planId", element: <PlanDetailPage /> },
              { path: "/plans", element: <Navigate to="/journey" replace /> },
              { path: "/plans/:planId", element: <PlanDetailPage /> },
              { path: "/reviews", element: <ReviewsPage /> },
              { path: "/me", element: <MyPage /> },
              { path: "/settings/profile", element: <ProfileSettingsPage /> },
              { path: "/memories", element: <MemoriesPage /> },
              { path: "/dev/runs", element: <DeveloperRunsPage /> },
            ],
          },
        ],
      },
    ],
  },
  { path: "/", element: <Navigate to="/today" replace /> },
  { path: "*", element: <Navigate to="/today" replace /> },
]);
