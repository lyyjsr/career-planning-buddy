import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppLayout } from "@/components/AppLayout";
import { HomePage } from "@/pages/HomePage";
import { LoginRoute, RequireAuth } from "@/pages/LoginRoute";
import { OnboardingPage } from "@/pages/OnboardingPage";
import { TodayPage } from "@/pages/TodayPage";
import { PlansPage } from "@/pages/PlansPage";
import { PlanDetailPage } from "@/pages/PlanDetailPage";
import { ReviewsPage } from "@/pages/ReviewsPage";
import { MemoriesPage } from "@/pages/MemoriesPage";
import { DeveloperRunsPage } from "@/pages/DeveloperRunsPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginRoute /> },
  {
    element: <RequireAuth />,
    children: [
      { path: "/onboarding", element: <OnboardingPage /> },
      {
        element: <AppLayout />,
        children: [
          { path: "/today", element: <TodayPage /> },
          { path: "/plans", element: <PlansPage /> },
          { path: "/plans/:planId", element: <PlanDetailPage /> },
          { path: "/reviews", element: <ReviewsPage /> },
          { path: "/memories", element: <MemoriesPage /> },
          { path: "/dev/runs", element: <DeveloperRunsPage /> },
        ],
      },
    ],
  },
  { path: "/", element: <Navigate to="/today" replace /> },
  { path: "*", element: <Navigate to="/today" replace /> },
]);
