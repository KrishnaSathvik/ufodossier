const PROCESSING_STATE_LABELS: Record<string, string> = {
  pdf_processed: "Text read",
  pdf_source_only: "File only, no case written up",
  video_metadata_only: "Video listed, no transcript",
  audio_metadata_only: "Audio listed, no transcript",
  image_metadata_only: "Image listed",
  unrecoverable: "File could not be read",
};

const DOCUMENT_CLASS_LABELS: Record<string, string> = {
  historical_case_file: "Historical case file",
  research_paper: "Research paper",
  incident_report: "Incident report",
  transcript: "Transcript",
  correspondence: "Correspondence",
  contract: "Contract",
  analysis: "Analysis",
  administrative: "Administrative",
  personnel_record: "Personnel record",
  media_metadata: "Media details",
  other: "Other",
};

const ROLE_LABELS: Record<string, string> = {
  primary_narrative: "Written report",
  analysis_of_event: "Later analysis",
  media_for_event: "Photo or video",
};

const ROLE_PHRASES: Record<string, string> = {
  primary_narrative: "Written report of this sighting",
  analysis_of_event: "Later analysis of this sighting",
  media_for_event: "Photo or video of this sighting",
};

const PRECISION_LABELS: Record<string, string> = {
  day: "Known to the day",
  month: "Known to the month",
  year: "Known to the year",
  unknown: "Not exact",
};

const TYPE_LABELS: Record<string, string> = {
  pdf: "PDF",
  video: "Video",
  image: "Image",
  audio: "Audio",
};

function titled(value: string): string {
  return value.replaceAll("_", " ");
}

export function releaseLabel(release: number | string): string {
  const n = typeof release === "number" ? release : Number(release);
  if (!Number.isInteger(n)) return String(release);
  return `Release ${String(n).padStart(2, "0")}`;
}

export function processingStateLabel(state: string | null | undefined): string {
  if (!state) return "Not recorded";
  return PROCESSING_STATE_LABELS[state] ?? titled(state);
}

export function documentClassLabel(value: string | null | undefined): string {
  if (!value) return "Type not recorded";
  return DOCUMENT_CLASS_LABELS[value] ?? titled(value);
}

export function sourceRoleLabel(role: string | null | undefined): string {
  if (!role) return "Related file";
  return ROLE_LABELS[role] ?? titled(role);
}

export function sourceRolePhrase(role: string | null | undefined): string {
  if (!role) return "Related file";
  return ROLE_PHRASES[role] ?? sourceRoleLabel(role);
}

export function datePrecisionLabel(value: string | null | undefined): string | null {
  if (!value) return null;
  return PRECISION_LABELS[value] ?? titled(value);
}

export function recordTypeLabel(type: string | null | undefined): string {
  if (!type) return "Not recorded";
  return TYPE_LABELS[type] ?? titled(type);
}

export function sightingLabel(label: string | null | undefined): string {
  if (!label) return "Untitled sighting";
  const withoutEpisode = label.replace(/#ep\d+\b/gi, "").trim();
  const parts = withoutEpisode.split(" / ").map((part) => part.trim()).filter(Boolean);
  const last = parts[parts.length - 1] ?? "";
  if (parts.length >= 2 && /\.(pdf|mp4|mov|jpg|jpeg|png|wav|mp3)$/i.test(last)) {
    parts.pop();
  }
  return parts.join(" / ");
}
