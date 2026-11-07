import type { Metadata } from "next";

import { GuideClient } from "@/components/GuideClient";

export const metadata: Metadata = {
  title: "使用指南",
  description: "从创建 API Key、调用模型，到创建 GPU 实例和接入自有资源的完整使用指南。",
};

export default function GuidePage() {
  return <GuideClient />;
}
