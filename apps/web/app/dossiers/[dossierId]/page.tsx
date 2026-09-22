import { DossierView } from "@/components/DossierView";

export default async function DossierPage({ params }: { params: Promise<{ dossierId: string }> }) { const { dossierId } = await params; return <DossierView dossierId={dossierId} />; }

