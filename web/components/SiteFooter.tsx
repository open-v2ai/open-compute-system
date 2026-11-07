"use client";

import Link from "next/link";
import { isPublicDemo } from "@/lib/deployment";
import { Brand } from "./Brand";
import { usePreferences } from "./PreferencesProvider";

export function SiteFooter() {
  const { locale, t } = usePreferences();
  return (
    <footer className="footer">
      <div className="container">
        <div className="footer-grid">
          <div>
            <Brand />
            <p>{t("自托管 AI 推理商业化基础设施。把自有 GPU 发布成可计费的模型 API。")}</p>
          </div>
          <div>
            <h4>{t("模型 API")}</h4>
            <div className="footer-links">
              <Link href="/models">{t("模型目录")}</Link>
              <Link href="/console/keys">API Keys</Link>
              <Link href="/console/usage">{t("Token 用量")}</Link>
            </div>
          </div>
          <div>
            <h4>{t("GPU 控制面")}</h4>
            <div className="footer-links">
              <Link href="/market">{t("GPU 资源")}</Link>
              <Link href="/console/instances">{t("实例控制台")}</Link>
              {!isPublicDemo() && <Link href="/admin/login">{t("运营后台")}</Link>}
            </div>
          </div>
          <div>
            <h4>{t("说明")}</h4>
            <div className="footer-links">
              <Link href="/guide">{locale === "en-US" ? "Guide" : "使用指南"}</Link>
              <Link href="/guide#faq">FAQ</Link>
            </div>
          </div>
          <div><h4>{t("体验与边界")}</h4><div className="footer-links"><Link href="/chat">{t("网页 Chat")}</Link><Link href="/legal/terms">{t("协议占位")}</Link></div></div>
        </div>
        <div className="footer-bottom">
          <span>© 2026 Open Compute System</span>
          <span>{t("协议页是模板，不是正式法律文本")}</span>
        </div>
      </div>
    </footer>
  );
}
