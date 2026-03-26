import { ReportDetail } from "@/components/report-detail";

export default async function ReportPage({
  params
}: {
  params: Promise<{ companyId: string; reportId: string }>;
}) {
  const { companyId, reportId } = await params;
  return <ReportDetail companyId={companyId} reportId={reportId} />;
}
