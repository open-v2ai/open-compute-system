"use client";

import { FlaskConical } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { isPublicDemo } from "@/lib/deployment";
import { usePreferences } from "./PreferencesProvider";

export function PublicDemoNotice() {
  const { t } = usePreferences();
  if (!isPublicDemo()) return null;
  return (
    <Alert variant="warning" className="rounded-none border-x-0 border-t-0">
      <FlaskConical />
      <AlertDescription>
        {t("公开 Mock 演示 · 数据由访客共享，请勿输入个人信息或真实密钥。")}
      </AlertDescription>
    </Alert>
  );
}
