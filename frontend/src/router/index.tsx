import { createBrowserRouter } from "react-router-dom";

import { HomePage } from "../pages/HomePage";
import { DeveloperRunsPage } from "../pages/DeveloperRunsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <HomePage />,
  },
  {
    path: "/dev/runs",
    element: <DeveloperRunsPage />,
  },
]);
