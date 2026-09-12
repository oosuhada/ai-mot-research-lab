import { BibliometricIntelligence } from "@/components/BibliometricIntelligence";
import {
  getBibliometricRelations,
  getResearchSignalLift,
} from "@/lib/api";

export default async function BibliometricsPage() {
  const [relations, signals] = await Promise.all([
    getBibliometricRelations(),
    getResearchSignalLift(12),
  ]);

  return (
    <BibliometricIntelligence
      relations={relations}
      signals={signals}
    />
  );
}
