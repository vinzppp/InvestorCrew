import { CompanyWorkspace } from "@/components/company-workspace";

export default async function CompanyPage({ params }: { params: Promise<{ companyId: string }> }) {
  const { companyId } = await params;
  return <CompanyWorkspace companyId={companyId} />;
}
