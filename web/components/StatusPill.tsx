"use client";

import { Badge } from "@/components/ui/badge";
import { usePreferences } from "./PreferencesProvider";

const labels: Record<string, string> = {
  running: "运行中", stopped: "已关机", pending: "待处理", provisioning: "创建中",
  starting: "开机中", stopping: "关机中", releasing: "释放中", released: "已释放",
  failed: "失败", queued: "等待中", succeeded: "成功", published: "已上架",
  unpublished: "已下架", draft: "草稿", fulfilled: "已履约", active: "正常",
  unverified: "未实名", new: "新线索", contacting: "跟进中", qualified: "已确认",
  proposal: "方案中", won: "已成交", lost: "已流失",
};

export function StatusPill({ status }: { status: string }) {
  const { t } = usePreferences();
  const variant = ["running", "succeeded", "published", "fulfilled", "active", "healthy"].includes(status)
    ? "success"
    : ["failed", "released", "unpublished", "lost"].includes(status)
      ? "destructive"
      : ["pending", "queued", "provisioning", "starting", "stopping", "releasing", "new", "manual_review"].includes(status)
        ? "warning"
        : "secondary";
  return <Badge variant={variant}>{t(labels[status] ?? status)}</Badge>;
}
