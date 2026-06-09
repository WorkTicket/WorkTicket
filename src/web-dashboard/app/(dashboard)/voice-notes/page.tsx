import { FutureFeature } from "@/components/future-feature";
import { PageHeader } from "@/components/dashboard/page-header";
import { PermissionGate } from "@/components/dashboard/permission-gate";

export default function VoiceNotesPage() {
  return (
    <PermissionGate permission="media:view">
      <div>
        <PageHeader
          title="Voice Notes"
          description="Record, playback, and upload voice notes from the field. Transcription is not available in the current version."
        />
        <FutureFeature featureId="voice_transcript" />
        <p className="mt-6 text-sm text-muted-foreground">
          Upload voice recordings from the mobile app and associate them with jobs. Playback and
          download are supported; automated transcription is planned for a future release.
        </p>
      </div>
    </PermissionGate>
  );
}
