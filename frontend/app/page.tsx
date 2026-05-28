import LeadTable from "@/components/LeadTable";
import ScrapeForm from "@/components/ScrapeForm";
import MapsSearch from "@/components/MapsSearch";

export default function HomePage() {
  return (
    <div className="space-y-8">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ScrapeForm />
        <MapsSearch />
      </div>
      <section>
        <h1 className="mb-4 text-2xl font-bold text-gray-900">Lead Pipeline</h1>
        <LeadTable />
      </section>
    </div>
  );
}
