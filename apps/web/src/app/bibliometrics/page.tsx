import { BibliometricIntelligence } from "@/components/BibliometricIntelligence";
import {
  getBibliometricRelations,
  getLandscape,
  getResearchSignalLift,
} from "@/lib/api";

export default async function BibliometricsPage() {
  const [landscape, relations, signals] = await Promise.all([
    getLandscape(),
    getBibliometricRelations(),
    getResearchSignalLift(12),
  ]);

  return (
    <BibliometricIntelligence
      landscape={landscape}
      relations={relations}
      signals={signals}
    />
  );
}
