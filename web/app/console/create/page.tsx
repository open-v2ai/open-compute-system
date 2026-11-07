"use client";

import { Suspense } from "react";
import { CreateInstanceClient } from "@/components/CreateInstanceClient";
import { usePreferences } from "@/components/PreferencesProvider";
export default function CreatePage(){const{t}=usePreferences();return <Suspense fallback={<div className="workspace-content">{t("正在加载创建流程…")}</div>}><CreateInstanceClient/></Suspense>}
