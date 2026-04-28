import { createBrowserRouter } from "react-router-dom";
import { AdminLayout } from "@/components/AdminDashboard";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AdminLayout />,
    children: [
      { index: true, lazy: () => import("@/components/admin/pages/ProjectManagementPage").then((m) => ({ Component: m.ProjectManagementPage })) },
      { path: "create", lazy: () => import("@/components/admin/pages/CreateProjectPage").then((m) => ({ Component: m.CreateProjectPage })) },
      { path: "queue", lazy: () => import("@/components/admin/pages/QueuePage").then((m) => ({ Component: m.QueuePage })) },
      { path: "review", lazy: () => import("@/components/admin/pages/ReviewPage").then((m) => ({ Component: m.ReviewPage })) },
      { path: "assets", lazy: () => import("@/components/admin/pages/AssetsPage").then((m) => ({ Component: m.AssetsPage })) },
      { path: "assets/:taskId/:segmentId/commerce", lazy: () => import("@/components/admin/pages/CommerceWorkbenchPage").then((m) => ({ Component: m.CommerceWorkbenchPage })) },
      { path: "music", lazy: () => import("@/components/admin/pages/MusicPage").then((m) => ({ Component: m.AdminMusicPage })) },
      { path: "diagnostics", lazy: () => import("@/components/admin/pages/DiagnosticsPage").then((m) => ({ Component: m.DiagnosticsPage })) },
      { path: "settings", lazy: () => import("@/components/admin/pages/SettingsPage").then((m) => ({ Component: m.AdminSettingsPage })) },
    ],
  },
]);
