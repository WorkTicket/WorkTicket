import { Calendar, Camera, ClipboardList, FileText, Mic, Users } from "lucide-react";

const features = [
  {
    icon: ClipboardList,
    title: "Job Management",
    description: "Track every job from lead to invoice with status updates, notes, and activity timelines.",
  },
  {
    icon: FileText,
    title: "Estimates & Quotes",
    description: "Build professional estimates with line items, tax, discounts, and PDF export.",
  },
  {
    icon: Calendar,
    title: "Scheduling",
    description: "Assign technicians and manage your calendar with drag-and-drop scheduling.",
  },
  {
    icon: Camera,
    title: "Photos & Attachments",
    description: "Capture job site photos from the field and associate them with the right job.",
  },
  {
    icon: Mic,
    title: "Voice Notes",
    description: "Record and attach voice notes on site. Optional transcription planned for a future release.",
  },
  {
    icon: Users,
    title: "Team & Permissions",
    description: "Invite your team with role-based access for owners, office staff, and technicians.",
  },
];

export function FeatureGrid({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`grid gap-6 ${compact ? "sm:grid-cols-2 lg:grid-cols-3" : "sm:grid-cols-2 lg:grid-cols-3"}`}>
      {features.map((feature) => (
        <article
          key={feature.title}
          className="rounded-2xl border border-surface-border bg-white p-6 shadow-sm transition-shadow hover:shadow-md"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
            <feature.icon className="h-5 w-5" aria-hidden />
          </div>
          <h3 className="mt-4 text-lg font-semibold text-slate-900">{feature.title}</h3>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">{feature.description}</p>
        </article>
      ))}
    </div>
  );
}
