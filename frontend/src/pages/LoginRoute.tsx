import { useEffect } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useGuestLogin, useMe } from "@/api/auth";
import { getAuthToken, setAuthToken } from "@/api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export function LoginRoute(): JSX.Element {
  const guestLogin = useGuestLogin();
  const me = useMe();
  const hasStoredToken = getAuthToken() !== null;

  // 首次进入：自动 guest 登录
  useEffect(() => {
    if (!hasStoredToken && guestLogin.isIdle) {
      guestLogin.mutate();
    }
  }, [guestLogin.isIdle, guestLogin.mutate, hasStoredToken]);

  useEffect(() => {
    if (hasStoredToken && me.isError && guestLogin.isIdle) {
      setAuthToken(null);
      guestLogin.mutate();
    }
  }, [guestLogin.isIdle, guestLogin.mutate, hasStoredToken, me.isError]);

  if (me.data !== undefined && me.data !== null) {
    return <Navigate to={me.data.profile_complete ? "/today" : "/onboarding"} replace />;
  }

  if (guestLogin.isError) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>无法登录</CardTitle>
            <CardDescription>游客登录失败，请检查后端是否在线。</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => guestLogin.mutate()}>重试</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>正在以游客身份登录…</CardTitle>
          <CardDescription>请稍候，我们正在为你准备求职规划伙伴。</CardDescription>
        </CardHeader>
      </Card>
    </div>
  );
}

interface RequireAuthProps {
  requireProfile?: boolean;
}

/**
 * 守卫：触发 guest 登录（若没 token），并按 profile 完整度定向。
 * - requireProfile=true：profile 不完整 → /onboarding
 * - 所有受保护路由无 token → /login
 */
export function RequireAuth({ requireProfile = false }: RequireAuthProps): JSX.Element {
  const location = useLocation();
  const me = useMe();
  const guestLogin = useGuestLogin();
  const hasStoredToken = getAuthToken() !== null;

  // 没 token 就触发 guest 登录
  useEffect(() => {
    if (!hasStoredToken && guestLogin.isIdle) {
      guestLogin.mutate();
    }
  }, [guestLogin.isIdle, guestLogin.mutate, hasStoredToken]);

  const hasToken = getAuthToken() !== null || guestLogin.data?.access_token !== undefined;

  // 登录失败的兜底
  if (me.isError && me.error !== null) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (!hasToken || me.isLoading || guestLogin.isPending || me.data === undefined) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        正在加载…
      </div>
    );
  }

  // profile 是否完整决定是否能进 requireProfile 页
  if (requireProfile && me.data !== undefined && !me.data.profile_complete) {
    return <Navigate to="/onboarding" replace />;
  }

  return <Outlet />;
}

export function RequireProfile(): JSX.Element {
  const me = useMe();

  if (me.isLoading || me.data === undefined || me.data === null) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        正在准备你的工作台…
      </div>
    );
  }
  if (!me.data.profile_complete) {
    return <Navigate to="/onboarding" replace />;
  }
  return <Outlet />;
}

export function RequireDev(): JSX.Element {
  const me = useMe();

  if (me.isLoading || me.data === undefined || me.data === null) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        正在验证开发者权限…
      </div>
    );
  }
  if (me.data.user.role !== "dev") {
    return <Navigate to="/me" replace />;
  }
  return <Outlet />;
}
