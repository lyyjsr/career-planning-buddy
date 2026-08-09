import { lazy } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppLayout } from "@/components/AppLayout";
import { LoginRoute, RequireAuth, RequireDev, RequireProfile } from "@/pages/LoginRoute";

const OnboardingPage = lazy(async () => ({
  default: (await import("@/pages/OnboardingPage")).OnboardingPage,
}));
const TodayPage = lazy(async () => ({
  default: (await import("@/pages/TodayPage")).TodayPage,
}));
const PlansPage = lazy(async () => ({
  default: (await import("@/pages/PlansPage")).PlansPage,
}));
const PlanDetailPage = lazy(async () => ({
  default: (await import("@/pages/PlanDetailPage")).PlanDetailPage,
}));
const ReviewsPage = lazy(async () => ({
  default: (await import("@/pages/ReviewsPage")).ReviewsPage,
}));
const MemoriesPage = lazy(async () => ({
  default: (await import("@/pages/MemoriesPage")).MemoriesPage,
}));
const DeveloperRunsPage = lazy(async () => ({
  default: (await import("@/pages/DeveloperRunsPage")).DeveloperRunsPage,
}));
const DeveloperEvalsPage = lazy(async () => ({
  default: (await import("@/pages/DeveloperEvalsPage")).DeveloperEvalsPage,
}));
const MyPage = lazy(async () => ({
  default: (await import("@/pages/MyPage")).MyPage,
}));
const ProfileSettingsPage = lazy(async () => ({
  default: (await import("@/pages/ProfileSettingsPage")).ProfileSettingsPage,
}));

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
              {
                element: <RequireDev />,
                children: [
                  { path: "/dev/runs", element: <DeveloperRunsPage /> },
                  { path: "/dev/evals", element: <DeveloperEvalsPage /> },
                ],
              },
            ],
          },
        ],
      },
    ],
  },
  { path: "/", element: <Navigate to="/today" replace /> },
  { path: "*", element: <Navigate to="/today" replace /> },
]);
